import ast
from collections.abc import Generator
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session, delete, select

from app.api.routes import tacacs_logs
from app.core.config import settings
from app.crud import aaa_statistics, stats_exclusions
from app.models import (
    AuditLog,
    AuthenticationStatistics,
    AuthorizationStatistics,
    StatsExcludedUser,
    StatsExcludedUserCreate,
    TacacsLogEvent,
)
from tests.utils.utils import random_lower_string

BASE = f"{settings.API_V1_STR}/stats_exclusions"
BACKEND = Path(__file__).resolve().parents[3]


@pytest.fixture
def prefix(db: Session) -> Generator[str, None, None]:
    """Unique username prefix; removes every stats row and exclusion using it."""
    p = random_lower_string()[:12]
    yield p
    like = f"{p}%"
    db.exec(
        delete(AuthenticationStatistics).where(
            AuthenticationStatistics.username.like(like)
        )
    )  # type: ignore[call-overload]
    db.exec(
        delete(AuthorizationStatistics).where(
            AuthorizationStatistics.username.like(like)
        )
    )  # type: ignore[call-overload]
    db.exec(delete(StatsExcludedUser).where(StatsExcludedUser.pattern.like(like)))  # type: ignore[call-overload]
    db.commit()


def _yesterday() -> datetime:
    d = datetime.now(timezone.utc).date() - timedelta(days=1)
    return datetime.combine(d, time.min).replace(tzinfo=timezone.utc)


def _add_auth(db: Session, username: str, success: int, fail: int = 0) -> None:
    db.add(
        AuthenticationStatistics(
            node_name=settings.NODE_NAME,
            username=username,
            nas_ip="10.0.0.1",
            user_source_ip="10.0.0.99",
            success_count=success,
            fail_count=fail,
            log_date=_yesterday(),
        )
    )
    db.commit()


def _exclude(db: Session, pattern: str) -> None:
    stats_exclusions.create_excluded_user(
        session=db, excluded_user_in=StatsExcludedUserCreate(pattern=pattern)
    )


# --- pattern validation / matching -------------------------------------------


def test_pattern_is_normalized_to_lower_case() -> None:
    assert (
        StatsExcludedUserCreate(pattern="  Data_Collector ").pattern == "data_collector"
    )


@pytest.mark.parametrize("bad", ["", "   ", "*", "**", "bad user", "svc?", "a/b"])
def test_invalid_patterns_are_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        StatsExcludedUserCreate(pattern=bad)


def test_is_excluded_glob_and_case() -> None:
    patterns = ["data_collector", "svc_*"]
    assert stats_exclusions.is_excluded("DATA_COLLECTOR", patterns)
    assert stats_exclusions.is_excluded("svc_backup", patterns)
    assert not stats_exclusions.is_excluded("svcxbackup", patterns)
    assert not stats_exclusions.is_excluded("alice", patterns)
    assert not stats_exclusions.is_excluded("alice", [])


def test_sql_clause_escapes_underscore(db: Session, prefix: str) -> None:
    # `_` is a LIKE wildcard; `{p}_*` must not swallow `{p}xbot`.
    _add_auth(db, f"{prefix}_bot", 1)
    _add_auth(db, f"{prefix}xbot", 1)
    clause = stats_exclusions.not_excluded_clause(
        AuthenticationStatistics.username, [f"{prefix}_*"]
    )
    names = db.exec(
        select(AuthenticationStatistics.username).where(
            AuthenticationStatistics.username.like(f"{prefix}%"),  # type: ignore[attr-defined]
            clause,
        )
    ).all()
    assert names == [f"{prefix}xbot"]


# --- CRUD routes ---------------------------------------------------------------


def test_create_list_delete_exclusion(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    prefix: str,
) -> None:
    pattern = f"{prefix}_collector"
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"pattern": pattern.upper(), "note": "inventory job"},
    )
    assert r.status_code == 200, r.text
    created = r.json()
    assert created["pattern"] == pattern

    dup = client.post(
        f"{BASE}/", headers=superuser_token_headers, json={"pattern": pattern}
    )
    assert dup.status_code == 409

    listed = client.get(f"{BASE}/", headers=superuser_token_headers).json()
    assert pattern in [row["pattern"] for row in listed["data"]]

    audit = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "StatsExcludedUser",
            AuditLog.entity_id == created["id"],
        )
    ).all()
    assert [a.action for a in audit] == ["CREATE"]

    r = client.delete(f"{BASE}/{created['id']}", headers=superuser_token_headers)
    assert r.status_code == 200
    assert (
        client.delete(
            f"{BASE}/{created['id']}", headers=superuser_token_headers
        ).status_code
        == 404
    )


def test_normal_user_can_read_but_not_write(
    client: TestClient, normal_user_token_headers: dict[str, str], prefix: str
) -> None:
    assert client.get(f"{BASE}/", headers=normal_user_token_headers).status_code == 200
    r = client.post(
        f"{BASE}/", headers=normal_user_token_headers, json={"pattern": f"{prefix}_x"}
    )
    assert r.status_code == 403


# --- statistics filtering --------------------------------------------------------


def _yesterday_success(body: dict, key: str) -> int:
    day = _yesterday().date().isoformat()
    return next(i["count"] for i in body[key] if i["date"] == day)


def test_range_statistics_exclude_and_include(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    prefix: str,
) -> None:
    collector, human = f"{prefix}_collector", f"{prefix}alice"
    _add_auth(db, collector, success=500, fail=3)
    _add_auth(db, human, success=4, fail=1)
    _exclude(db, collector)

    day = _yesterday().date().isoformat()
    url = (
        f"{settings.API_V1_STR}/aaa_statistics/range/?range_date={day},{day}&limit=1000"
    )

    filtered = client.get(url, headers=superuser_token_headers).json()
    unfiltered = client.get(
        f"{url}&include_excluded=true", headers=superuser_token_headers
    ).json()

    assert collector in filtered["excluded_users"]
    assert unfiltered["excluded_users"] == []

    users = [r["username"] for r in filtered["authentication_success_count_by_user"]]
    assert human in users and collector not in users
    fails = [r["username"] for r in filtered["authentication_failed_count_by_user"]]
    assert collector not in fails
    assert collector in [
        r["username"] for r in unfiltered["authentication_success_count_by_user"]
    ]

    key = "last_range_days_authentication_success"
    assert (
        _yesterday_success(unfiltered, key) - _yesterday_success(filtered, key) == 500
    )


def test_per_row_list_endpoint_filters(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    prefix: str,
) -> None:
    collector = f"{prefix}_collector"
    _add_auth(db, collector, success=10)
    _exclude(db, f"{prefix}_*")

    url = f"{settings.API_V1_STR}/authentication_statistics/?limit=1000"
    rows = client.get(url, headers=superuser_token_headers).json()["data"]
    assert collector not in [r["username"] for r in rows]
    rows = client.get(
        f"{url}&include_excluded=true", headers=superuser_token_headers
    ).json()["data"]
    assert collector in [r["username"] for r in rows]


def test_today_counts_filter_after_cache(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = 0

    def fake_rows() -> list[dict]:
        nonlocal calls
        calls += 1
        return [
            {
                "username": "data_collector",
                "nas_ip": "n",
                "user_source_ip": "c",
                "permit_count": 90,
                "deny_count": 0,
            },
            {
                "username": "alice",
                "nas_ip": "n",
                "user_source_ip": "c",
                "permit_count": 3,
                "deny_count": 2,
            },
        ]

    monkeypatch.setattr(aaa_statistics, "_local_today_authz_rows", fake_rows)
    monkeypatch.setattr(aaa_statistics, "_today_rows_cache", {})

    node = settings.NODE_NAME
    assert aaa_statistics.get_today_authz_counts(db, node) == (93, 2)
    # Same cache entry, different exclusion list: no stale totals, no re-parse.
    assert aaa_statistics.get_today_authz_counts(db, node, ["data_collector"]) == (3, 2)
    assert calls == 1


def test_daily_summary_filters_events(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    prefix: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    collector = f"{prefix}_collector"
    _exclude(db, collector)

    def fake_parse(log_type: str, _path: str) -> list[TacacsLogEvent]:
        if log_type != "authentication":
            return []
        return [
            TacacsLogEvent(
                timestamp="t",
                log_type=log_type,
                username=u,
                nas_ip="n",
                client_ip="c",
                result="success",
                message="login succeeded",
            )
            for u in (collector, collector, "alice")
        ]

    monkeypatch.setattr(tacacs_logs, "_parse_log_file", fake_parse)
    url = f"{settings.API_V1_STR}/tacacs_logs/events/summary"

    body = client.get(url, headers=superuser_token_headers).json()
    assert body["authentication"]["success"] == 1
    assert collector in body["excluded_users"]
    body = client.get(
        f"{url}?include_excluded=true", headers=superuser_token_headers
    ).json()
    assert body["authentication"]["success"] == 3


# --- guard: exclusion stays read-side ----------------------------------------------


@pytest.mark.parametrize(
    "module",
    [
        "app/crud/alert_evaluator.py",
        "app/crud/anomaly_detection.py",
        "app/crud/ml_anomaly_scorer.py",
        "app/crud/tacacs_siem.py",
        "app/api/routes/sync.py",
        "scripts/_log_stats_base.py",
        "scripts/tacacs_logs_authentication.py",
        "scripts/tacacs_logs_authorization.py",
        "scripts/tacacs_logs_accounting.py",
    ],
)
def test_ingest_and_alerting_never_apply_exclusions(module: str) -> None:
    """Exclusions must not reach collection, peer collect-stats, alerting,
    anomaly scoring or SIEM — an excluded account must still trigger alerts."""
    tree = ast.parse((BACKEND / module).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            names = [node.module or ""] + [a.name for a in node.names]
        elif isinstance(node, ast.Import):
            names = [a.name for a in node.names]
        else:
            continue
        assert not any("stats_exclusions" in n for n in names), module
