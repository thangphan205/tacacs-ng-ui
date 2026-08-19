import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.crud.alert_evaluator import _check_auth_stats, _format_body
from app.models import AlertRule


def _make_rule(**overrides) -> AlertRule:
    defaults = {
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


class TestClientIpFailThreshold:
    def test_triggers_and_includes_offending_ip(self) -> None:
        rule = _make_rule()
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=rule.time_window_minutes)

        fail_by_user = {"alice": 4, "bob": 1}
        fail_by_ip = {"10.0.0.5": 4, "10.0.0.9": 1}
        seen_usernames = {"alice", "bob"}
        seen_ips = {"10.0.0.5", "10.0.0.9"}

        with patch(
            "app.crud.alert_evaluator._parse_auth_log",
            return_value=(fail_by_user, fail_by_ip, seen_usernames, seen_ips),
        ):
            triggered, payload = _check_auth_stats(
                rule=rule, session=None, window_start=window_start, now=now
            )

        assert triggered is True
        assert payload["ip"] == "10.0.0.5"
        assert payload["fail_count"] == 4
        assert payload["triggered_ips"] == [{"ip": "10.0.0.5", "fail_count": 4}]

    def test_does_not_trigger_below_threshold(self) -> None:
        rule = _make_rule(threshold=10)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=rule.time_window_minutes)

        with patch(
            "app.crud.alert_evaluator._parse_auth_log",
            return_value=({}, {"10.0.0.5": 4}, set(), {"10.0.0.5"}),
        ):
            triggered, payload = _check_auth_stats(
                rule=rule, session=None, window_start=window_start, now=now
            )

        assert triggered is False
        assert payload == {}

    def test_multiple_offending_ips_sorted_by_fail_count(self) -> None:
        rule = _make_rule(threshold=2)
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(minutes=rule.time_window_minutes)

        fail_by_ip = {"10.0.0.1": 3, "10.0.0.2": 9, "10.0.0.3": 1}

        with patch(
            "app.crud.alert_evaluator._parse_auth_log",
            return_value=({}, fail_by_ip, set(), set(fail_by_ip)),
        ):
            triggered, payload = _check_auth_stats(
                rule=rule, session=None, window_start=window_start, now=now
            )

        assert triggered is True
        assert payload["ip"] == "10.0.0.2"
        assert [item["ip"] for item in payload["triggered_ips"]] == [
            "10.0.0.2",
            "10.0.0.1",
        ]

    def test_body_formats_offending_ips_and_omits_raw_ip_field(self) -> None:
        rule = _make_rule()
        payload = {
            "triggered_ips": [{"ip": "10.0.0.5", "fail_count": 4}],
            "ip": "10.0.0.5",
            "fail_count": 4,
            "window_minutes": 10,
            "rule": rule.name,
        }
        body = _format_body(rule=rule, payload=payload)
        assert "10.0.0.5 (4 fails)" in body
        # the raw "ip" field is webhook-only, not duplicated in the human-readable body
        assert body.count("10.0.0.5") == 1
