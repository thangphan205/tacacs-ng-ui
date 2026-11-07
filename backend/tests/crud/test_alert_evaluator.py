import json
import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import patch

import pytest
from sqlmodel import Session, delete

from app.crud.alert_evaluator import (
    AuthWindow,
    _Activity,
    _check_audit_logs,
    _check_auth_stats,
    _device_labels,
)
from app.models import AlertRule, AuditLog, Host


def _make_rule(**overrides: Any) -> AlertRule:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "Repeated auth reject from one IP",
        "log_type": "auth",
        "condition_field": "client_ip",
        "condition_operator": "gt",
        "threshold": 3,
        "time_window_minutes": 10,
        "severity": "high",
        "cooldown_minutes": 60,
    }
    defaults.update(overrides)
    return AlertRule(**defaults)


def _window(fail_by_ip: dict[str, int], **kwargs: Any) -> AuthWindow:
    by_ip = {
        ip: _Activity(fail=n, nas_ips={"10.1.1.1"}) for ip, n in fail_by_ip.items()
    }
    return AuthWindow(fail_by_ip=fail_by_ip, by_ip=by_ip, **kwargs)


def _check(
    rule: AlertRule, window: AuthWindow, **patches: set[str]
) -> tuple[bool, dict[str, Any]]:
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=rule.time_window_minutes)
    with (
        patch("app.crud.alert_evaluator._parse_auth_log", return_value=window),
        patch("app.crud.alert_evaluator._device_labels", return_value={}),
        patch(
            "app.crud.alert_evaluator._baseline_usernames",
            return_value=patches.get("baseline_users", set()),
        ),
        patch(
            "app.crud.alert_evaluator._baseline_ips",
            return_value=patches.get("baseline_ips", set()),
        ),
    ):
        return _check_auth_stats(
            rule=rule,
            session=None,  # type: ignore[arg-type]
            window_start=window_start,
            now=now,
        )


class TestClientIpFailThreshold:
    def test_triggers_and_includes_offending_ip(self) -> None:
        rule = _make_rule()
        triggered, payload = _check(rule, _window({"10.0.0.5": 4, "10.0.0.9": 1}))

        assert triggered is True
        assert payload["ip"] == "10.0.0.5"
        assert payload["fail_count"] == 4
        assert payload["triggered_ips"] == [{"ip": "10.0.0.5", "fail_count": 4}]
        assert [s["ip"] for s in payload["sources"]] == ["10.0.0.5"]

    def test_does_not_trigger_below_threshold(self) -> None:
        rule = _make_rule(threshold=10)
        triggered, payload = _check(rule, _window({"10.0.0.5": 4}))

        assert triggered is False
        assert payload == {}

    def test_multiple_offending_ips_sorted_by_fail_count(self) -> None:
        rule = _make_rule(threshold=2)
        triggered, payload = _check(
            rule, _window({"10.0.0.1": 3, "10.0.0.2": 9, "10.0.0.3": 1})
        )

        assert triggered is True
        assert payload["ip"] == "10.0.0.2"
        assert [item["ip"] for item in payload["triggered_ips"]] == [
            "10.0.0.2",
            "10.0.0.1",
        ]
        assert [s["ip"] for s in payload["sources"]] == ["10.0.0.2", "10.0.0.1"]


class TestNewValueDetails:
    def test_new_username_reports_outcome_source_and_device(self) -> None:
        rule = _make_rule(
            condition_field="username", condition_operator="new_value", threshold=None
        )
        t0 = datetime(2026, 11, 7, 14, 2, 11, tzinfo=timezone.utc)
        window = AuthWindow(
            by_user={
                "abc": _Activity(
                    success=2,
                    fail=3,
                    peers={"192.168.252.1"},
                    nas_ips={"10.1.1.1"},
                    first=t0,
                    last=t0 + timedelta(minutes=5),
                ),
                "known": _Activity(success=1, peers={"10.0.0.1"}),
                "zz": _Activity(fail=9, peers={"10.0.0.2"}),
            }
        )
        triggered, payload = _check(rule, window, baseline_users={"known"})

        assert triggered is True
        assert payload["new_usernames"] == ["abc", "zz"]
        # a new username that logged in is listed before one that only failed
        abc = payload["users"][0]
        assert abc["username"] == "abc"
        assert (abc["success"], abc["fail"]) == (2, 3)
        assert abc["source_ips"] == ["192.168.252.1"]
        assert abc["devices"] == ["10.1.1.1"]
        assert abc["first_seen"] and abc["last_seen"]
        json.dumps(payload)  # stored as payload_snapshot, so must serialise

    def test_new_source_ip_lists_usernames(self) -> None:
        rule = _make_rule(condition_operator="new_value", threshold=None)
        window = AuthWindow(
            by_ip={"192.168.252.1": _Activity(success=1, peers={"bob", "abc"})}
        )
        triggered, payload = _check(rule, window)

        assert triggered is True
        assert payload["new_source_ips"] == ["192.168.252.1"]
        assert payload["sources"][0]["usernames"] == ["abc", "bob"]

    def test_total_failures_include_top_breakdown(self) -> None:
        rule = _make_rule(condition_field="fail_count", threshold=3)
        window = AuthWindow(
            fail_by_user={"alice": 4, "bob": 1},
            fail_by_ip={"10.0.0.5": 5},
            fail_by_nas={"10.1.1.1": 5},
        )
        triggered, payload = _check(rule, window)

        assert triggered is True
        assert payload["fail_count"] == 5
        assert payload["top_users"] == [
            {"name": "alice", "count": 4},
            {"name": "bob", "count": 1},
        ]
        assert payload["top_devices"] == [{"name": "10.1.1.1", "count": 5}]


@pytest.fixture
def hosts(db: Session) -> Generator[None, None, None]:
    names = [f"alert-{uuid.uuid4().hex[:8]}" for _ in range(3)]
    db.add(Host(name=names[0], ipv4_address="10.9.0.0/16"))
    db.add(Host(name=names[1], ipv4_address="10.9.1.1"))
    db.add(Host(name=names[2], ipv4_address="0.0.0.0/0"))
    db.commit()
    yield
    db.exec(delete(Host).where(Host.name.in_(names)))  # type: ignore[attr-defined,call-overload]
    db.commit()


@pytest.mark.usefixtures("hosts")
def test_device_labels_prefers_most_specific_host(db: Session) -> None:
    labels = _device_labels(db, ["10.9.1.1", "10.9.7.7", "172.16.0.1", "junk"])
    assert labels["10.9.1.1"].endswith("(10.9.1.1)")
    assert labels["10.9.1.1"] != labels["10.9.7.7"]
    assert labels["10.9.7.7"].endswith("(10.9.7.7)")
    # the /0 catch-all names no device
    assert "172.16.0.1" not in labels
    assert "junk" not in labels


@pytest.fixture
def config_audit_rows(db: Session) -> Generator[list[AuditLog], None, None]:
    now = datetime.now(timezone.utc)
    rows = []
    for minutes_ago, filename in ((4, "old.cfg"), (1, "new.cfg")):
        row = AuditLog(
            action="ACTIVATE",
            entity_type="TacacsConfig",
            entity_id=str(uuid.uuid4()),
            user_email="admin@example.com",
            ip_address="10.0.0.4",
            new_values=json.dumps({"filename": filename, "active": True}),
        )
        row.created_at = now - timedelta(minutes=minutes_ago)
        db.add(row)
        rows.append(row)
    db.commit()
    yield rows
    db.exec(delete(AuditLog).where(AuditLog.id.in_([r.id for r in rows])))  # type: ignore[attr-defined,call-overload]
    db.commit()


@pytest.mark.usefixtures("config_audit_rows")
def test_config_changes_carry_filename_and_skip_reported_rows(db: Session) -> None:
    now = datetime.now(timezone.utc)
    rule = _make_rule(
        log_type="config",
        condition_field="config_action",
        condition_operator="activated",
        threshold=1,
        time_window_minutes=5,
    )
    window_start = now - timedelta(minutes=5)

    triggered, payload = _check_audit_logs(
        rule=rule, session=db, window_start=window_start
    )
    ours = [c for c in payload["changes"] if c["filename"] in ("old.cfg", "new.cfg")]
    assert triggered is True
    assert [c["filename"] for c in ours] == ["new.cfg", "old.cfg"]
    assert ours[0]["ip_address"] == "10.0.0.4"
    assert ours[0]["by"] == "admin@example.com"

    # The previous firing (2 min ago) already reported old.cfg.
    rule.last_fired_at = now - timedelta(minutes=2)
    _, payload = _check_audit_logs(rule=rule, session=db, window_start=window_start)
    filenames = [c["filename"] for c in payload["changes"]]
    assert "new.cfg" in filenames
    assert "old.cfg" not in filenames
