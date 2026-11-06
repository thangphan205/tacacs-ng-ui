"""
One definition of "day" for AAA statistics: the log timezone (#356).

tac_plus-ng names its files and stamps its lines in local time. The read path
used the UTC date for "today", and log_date was stored as midnight UTC in a
`timestamp without time zone` column, which PostgreSQL shifted by the session
time zone. West of UTC that put every daily bar under the previous day and
zeroed the dashboard every evening.
"""

import importlib.util
import uuid
from collections.abc import Generator
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, delete, select

from app.api.routes.aaa_statistics import _upsert_peer_stats
from app.core.config import Settings, settings
from app.core.db import engine
from app.crud import aaa_statistics, alert_evaluator
from app.models import AuthenticationStatistics
from scripts import _log_stats_base
from scripts._log_stats_base import local_date, local_today, parse_log_date

SAO_PAULO = ZoneInfo("America/Sao_Paulo")  # UTC-3, no DST since 2019

VERSIONS = Path(__file__).resolve().parents[2] / "app/alembic/versions"
MIGRATION = VERSIONS / "d5e1b7a3c946_statistics_log_date_to_date.py"
TZ_MIGRATION = VERSIONS / "e7f2c4a8b153_seed_stats_timezone_from_tz.py"


@pytest.fixture
def log_tz(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    """Pin the log timezone to UTC-3 and clear its cache around the test."""
    monkeypatch.setattr(_log_stats_base, "_get_local_tz", lambda: SAO_PAULO)
    monkeypatch.setattr(_log_stats_base, "_local_tz_cache", None)
    yield
    _log_stats_base._local_tz_cache = None


@pytest.fixture
def sao_paulo_session() -> Generator[Session, None, None]:
    """
    A DB session whose PostgreSQL time zone is UTC-3, like the reporter's.

    Never committed: the rollback discards the rows and reverts the SET, so
    the pooled connection goes back with the server's own time zone.
    """
    with Session(engine) as session:
        session.exec(text("SET TIME ZONE 'America/Sao_Paulo'"))  # type: ignore[call-overload]
        try:
            yield session
        finally:
            session.rollback()


@pytest.mark.usefixtures("log_tz")
def test_local_today_is_the_log_timezone_day() -> None:
    assert local_today() == datetime.now(SAO_PAULO).date()


@pytest.mark.usefixtures("log_tz")
def test_local_date_maps_an_instant_to_its_log_day() -> None:
    # 22:26 on the 5th in Sao Paulo is already the 6th in UTC.
    assert local_date(datetime(2026, 11, 6, 1, 26, tzinfo=timezone.utc)) == date(
        2026, 11, 5
    )


@pytest.mark.parametrize(
    "value",
    ["2026-11-05", "2026-11-05T00:00:00+00:00", "2026-11-05T00:00:00"],
)
def test_parse_log_date_reads_old_and_new_peer_payloads(value: str) -> None:
    assert parse_log_date(value) == date(2026, 11, 5)


def test_log_date_round_trips_whatever_the_session_timezone(
    sao_paulo_session: Session,
) -> None:
    username = f"tz_{uuid.uuid4().hex[:8]}"
    sao_paulo_session.add(
        AuthenticationStatistics(
            node_name=settings.NODE_NAME,
            username=username,
            nas_ip="10.0.0.1",
            user_source_ip="10.0.0.2",
            success_count=1,
            log_date=date(2026, 11, 5),
        )
    )
    sao_paulo_session.flush()
    stored = sao_paulo_session.exec(
        select(AuthenticationStatistics.log_date).where(
            AuthenticationStatistics.username == username
        )
    ).one()
    assert stored == date(2026, 11, 5)


@pytest.mark.usefixtures("log_tz")
def test_daily_series_puts_rows_on_their_own_day(
    sao_paulo_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    username = f"tz_{uuid.uuid4().hex[:8]}"
    sao_paulo_session.add(
        AuthenticationStatistics(
            node_name="tz-test-node",
            username=username,
            nas_ip="10.0.0.1",
            user_source_ip="10.0.0.2",
            success_count=12877,
            log_date=date(2026, 11, 5),
        )
    )
    sao_paulo_session.flush()

    monkeypatch.setattr(aaa_statistics, "local_today", lambda: date(2026, 11, 6))
    result = aaa_statistics._get_range_statistics(
        sao_paulo_session,
        date(2026, 11, 4),
        date(2026, 11, 5),
        "r",
        node_name="tz-test-node",
    )
    assert result["r_authentication_success"] == [
        {"date": "2026-11-04", "count": 0},
        {"date": "2026-11-05", "count": 12877},
    ]


def test_peer_rows_from_an_old_peer_keep_their_day(db: Session) -> None:
    username = f"tz_{uuid.uuid4().hex[:8]}"
    row = {
        "username": username,
        "nas_ip": "10.0.0.1",
        "user_source_ip": "10.0.0.2",
        "success_count": 3,
        "fail_count": 0,
        # what a peer still on 0.6.5 sends
        "log_date": "2026-11-05T00:00:00+00:00",
    }
    try:
        _upsert_peer_stats(db, {"node_name": "old-peer", "authentication": [row]})
        stored = db.exec(
            select(AuthenticationStatistics).where(
                AuthenticationStatistics.username == username
            )
        ).one()
        assert stored.log_date == date(2026, 11, 5)
    finally:
        db.exec(
            delete(AuthenticationStatistics).where(
                AuthenticationStatistics.username == username
            )
        )  # type: ignore[call-overload]
        db.commit()


@pytest.mark.usefixtures("log_tz")
def test_alert_window_reads_the_local_days_log_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "TACACS_LOG_DIRECTORY", f"{tmp_path}/")
    for day in ("2026-11-05", "2026-11-06"):
        f = tmp_path / "2026" / "11" / f"authentication-{day}.log"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text("")

    # 22:26 local on the 5th: only the 5th's file exists in the real world, and
    # the UTC date (the 6th) is the wrong one to read.
    now = datetime(2026, 11, 6, 1, 26, tzinfo=timezone.utc)
    start = datetime(2026, 11, 6, 0, 26, tzinfo=timezone.utc)  # 21:26 local
    paths = alert_evaluator._log_paths_for_window(start, now, "authentication")
    assert [Path(p).name for p in paths] == ["authentication-2026-11-05.log"]

    # A window reaching back past local midnight also reads the previous day.
    now = datetime(2026, 11, 6, 3, 30, tzinfo=timezone.utc)  # 00:30 local, 6th
    start = datetime(2026, 11, 6, 2, 30, tzinfo=timezone.utc)  # 23:30 local, 5th
    paths = alert_evaluator._log_paths_for_window(start, now, "authentication")
    assert [Path(p).name for p in paths] == [
        "authentication-2026-11-06.log",
        "authentication-2026-11-05.log",
    ]


def test_events_accept_date_from_without_date_to(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    # A naive date_from was compared with an aware "today": TypeError, 500.
    r = client.get(
        f"{settings.API_V1_STR}/tacacs_logs/events?date_from=2026-11-01",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200


def _load(path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migration_log_day_sql() -> str:
    return _load(MIGRATION)._LOG_DAY


@pytest.mark.parametrize(
    ("session_tz", "stored", "day"),
    [
        # what 0.6.5 stored for day D: midnight UTC seen in the session zone
        ("America/Sao_Paulo", "2026-11-04 21:00:00", "2026-11-05"),
        ("Asia/Ho_Chi_Minh", "2026-11-05 07:00:00", "2026-11-05"),
        ("UTC", "2026-11-05 00:00:00", "2026-11-05"),
    ],
)
def test_migration_recovers_the_log_day(session_tz: str, stored: str, day: str) -> None:
    expr = _migration_log_day_sql().replace("log_date", "v.log_date")
    with engine.connect() as conn:
        try:
            conn.execute(text(f"SET TIME ZONE '{session_tz}'"))
            got = conn.execute(
                text(f"SELECT {expr} FROM (SELECT TIMESTAMP '{stored}' AS log_date) v")
            ).scalar_one()
        finally:
            conn.rollback()  # also reverts the SET
    assert got == date.fromisoformat(day)


@pytest.mark.parametrize(
    ("tz", "expected"),
    [
        ("America/Sao_Paulo", "America/Sao_Paulo"),
        ("Asia/Ho_Chi_Minh", "Asia/Ho_Chi_Minh"),
        ("Europe/London", "Europe/London"),  # UTC in winter only
        ("UTC", None),
        ("Etc/UTC", None),
        ("", None),
        (None, None),
        ("Not/AZone", None),
    ],
)
def test_tz_migration_only_takes_a_real_non_utc_zone(
    tz: str | None, expected: str | None
) -> None:
    assert _load(TZ_MIGRATION).zone_from_env(tz) == expected


def test_timezone_setting_is_seeded_from_tz(monkeypatch: pytest.MonkeyPatch) -> None:
    # The seed used a fixed "UTC", so a non-UTC TZ never reached the setting.
    monkeypatch.setenv("TZ", "America/Sao_Paulo")
    monkeypatch.delenv("TACACS_TIMEZONE", raising=False)
    assert Settings().TACACS_TIMEZONE == "America/Sao_Paulo"
