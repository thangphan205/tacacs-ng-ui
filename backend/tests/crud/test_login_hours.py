"""
"Login at Unusual Hour": the hourly baseline and the rule that reads it.

Hours are the ones tac_plus-ng stamps on its lines, i.e. the log timezone; the
tests pin that to UTC+7 so a 03:xx login is 20:xx the day before in UTC.
"""

import uuid
from collections import Counter
from collections.abc import Callable, Generator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from sqlmodel import Session, col, delete, select

from app.api.routes.aaa_statistics import _upsert_peer_stats
from app.core import db as db_module
from app.crud import login_hours
from app.crud.alert_evaluator import AuthWindow, _Activity, _check_auth_stats
from app.crud.alert_formatter import (
    _hour_ranges,
    build_alert_message,
    render_text,
)
from app.crud.auth_hourly import counter_to_rows, upsert_hourly
from app.models import AlertEvent, AlertRule
from app.models import AuthenticationHourlyStatistics as Hourly
from scripts import _log_stats_base
from scripts._log_stats_base import build_log_file_path, parse_authentication_logs

HCM = ZoneInfo("Asia/Ho_Chi_Minh")  # UTC+7, no DST
NAS = "10.1.1.1"
SRC = "10.0.0.5"


@pytest.fixture(autouse=True)
def log_tz(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setattr(_log_stats_base, "_get_local_tz", lambda: HCM)
    monkeypatch.setattr(_log_stats_base, "_local_tz_cache", None)
    monkeypatch.setattr("app.crud.alert_formatter.local_tz", lambda: HCM)
    yield
    _log_stats_base._local_tz_cache = None


# --- collector ----------------------------------------------------------------------


def _log_line(ts: str, user: str, outcome: str) -> str:
    return f"{ts} +0700\t{NAS}\t{user}\ttty0\t{SRC}\tshell login {outcome}\n"


def test_parser_counts_logins_per_user_and_hour(tmp_path: Path) -> None:
    day = date(2026, 11, 5)
    path = Path(build_log_file_path(day, "authentication", f"{tmp_path}/"))
    path.parent.mkdir(parents=True)
    path.write_text(
        _log_line("2026-11-05 03:12:44", "alice", "succeeded")
        + _log_line("2026-11-05 03:59:59", "alice", "succeeded")
        + _log_line("2026-11-05 03:30:00", "alice", "failed")
        + _log_line("2026-11-05 14:00:00", "alice", "succeeded")
        + _log_line("2026-11-05 14:01:00", "bob", "failed")
        # another day's line in the same file is not this day's login
        + _log_line("2026-11-04 23:59:00", "alice", "succeeded")
    )

    hourly: Counter[tuple[str, int, str]] = Counter()
    ok, failed = parse_authentication_logs(day, f"{tmp_path}/", hourly)

    assert hourly == {
        ("alice", 3, "success"): 2,
        ("alice", 3, "fail"): 1,
        ("alice", 14, "success"): 1,
        ("bob", 14, "fail"): 1,
    }
    # the daily counters are unchanged by asking for the hourly ones
    assert sum(ok.values()) == 3 and sum(failed.values()) == 2
    assert counter_to_rows(hourly) == [
        {"username": "alice", "hour": 3, "success_count": 2, "fail_count": 1},
        {"username": "alice", "hour": 14, "success_count": 1, "fail_count": 0},
        {"username": "bob", "hour": 14, "success_count": 0, "fail_count": 1},
    ]


def test_parser_without_hourly_is_unchanged(tmp_path: Path) -> None:
    day = date(2026, 11, 5)
    path = Path(build_log_file_path(day, "authentication", f"{tmp_path}/"))
    path.parent.mkdir(parents=True)
    path.write_text(_log_line("2026-11-05 03:12:44", "alice", "succeeded"))
    ok, failed = parse_authentication_logs(day, f"{tmp_path}/")
    assert sum(ok.values()) == 1 and not failed


# --- profile maths ------------------------------------------------------------------


def test_share_around_wraps_midnight_and_counts_neighbours() -> None:
    profile = login_hours.HourProfile(by_hour={23: 10, 0: 10, 12: 80}, days=30)
    assert profile.share_around(0) == 20.0  # 23, 0 (1 is empty)
    assert profile.share_around(23) == 20.0  # 22, 23, 0
    assert profile.share_around(12) == 80.0
    assert profile.share_around(5) == 0.0
    assert login_hours.HourProfile().share_around(3) == 0.0


def test_usual_hours_need_a_real_share() -> None:
    by_hour = dict.fromkeys(range(8, 18), 10) | {3: 1}  # 1 of 101 logins at 03
    assert login_hours.HourProfile(by_hour=by_hour).usual_hours() == list(range(8, 18))


def test_baseline_leaves_out_the_window_days() -> None:
    window_start = datetime(2026, 11, 6, 20, 5, tzinfo=timezone.utc)  # 03:05 on 7th
    assert login_hours.baseline_days(window_start) == (
        date(2026, 10, 8),
        date(2026, 11, 6),
    )


def test_hour_ranges_text() -> None:
    assert _hour_ranges([8, 9, 10, 11, 13, 14]) == "08–12, 13–15"
    assert _hour_ranges([22, 23]) == "22–00"
    assert _hour_ranges(list(range(24))) == "all hours"
    assert _hour_ranges([]) == "none yet"


# --- database -----------------------------------------------------------------------


@pytest.fixture
def history(db: Session) -> Generator[Callable[..., str], None, None]:
    """`history(days, hours, ...)` adds a user's login history and returns the name."""
    users: list[str] = []

    def add(
        *,
        days: int,
        hours: range | list[int],
        username: str | None = None,
        first_day: date = date(2026, 10, 15),
        node_name: str = "primary",
        per_hour: int = 1,
    ) -> str:
        name = username or f"hrs_{uuid.uuid4().hex[:8]}"
        users.append(name)
        for offset in range(days):
            for hour in hours:
                db.add(
                    Hourly(
                        node_name=node_name,
                        username=name,
                        log_date=first_day + timedelta(days=offset),
                        hour=hour,
                        success_count=per_hour,
                    )
                )
        db.commit()
        return name

    yield add
    db.rollback()
    db.exec(delete(Hourly).where(Hourly.username.in_(users)))  # type: ignore[attr-defined,call-overload]
    db.commit()


def test_profiles_sum_nodes_and_count_days_once(
    db: Session, history: Callable[..., str]
) -> None:
    name = history(days=3, hours=[9], node_name="a")
    history(days=3, hours=[9], node_name="b", username=name)
    # a day with only failures says nothing about when the user logs in
    db.add(
        Hourly(
            username=name,
            log_date=date(2026, 10, 25),
            hour=2,
            success_count=0,
            fail_count=9,
        )
    )
    db.commit()

    profile = login_hours.load_profiles(
        db, [name], date(2026, 10, 8), date(2026, 11, 6)
    )[name]
    assert profile.by_hour == {9: 6}
    assert profile.days == 3
    assert login_hours.load_profiles(db, [], date(2026, 10, 8), date(2026, 11, 6)) == {}


def _rule(**overrides: Any) -> AlertRule:
    values: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "[System] Login at Unusual Hour",
        "log_type": "auth",
        "condition_field": "login_hour",
        "condition_operator": "unusual",
        "threshold": 2.0,
        "time_window_minutes": 10,
        "severity": "medium",
        "cooldown_minutes": 5,
    }
    values.update(overrides)
    return AlertRule(**values)


NOW = datetime(2026, 11, 7, 3, 15, tzinfo=HCM)


def _check(
    db: Session,
    rule: AlertRule,
    logins: dict[str, list[tuple[int, int]]],
) -> tuple[bool, dict[str, Any]]:
    """Run the rule; `logins` maps user -> [(hour, minute)] on 2026-11-07, local."""
    window = AuthWindow(
        by_user={
            user: _Activity(
                success=len(times),
                logins=[
                    (datetime(2026, 11, 7, h, m, tzinfo=HCM), SRC, NAS)
                    for h, m in times
                ],
            )
            for user, times in logins.items()
        }
    )
    with (
        patch("app.crud.alert_evaluator._parse_auth_log", return_value=window),
        patch(
            "app.crud.alert_evaluator._device_labels",
            return_value={NAS: f"core-sw1 ({NAS})"},
        ),
    ):
        return _check_auth_stats(
            rule=rule,
            session=db,
            window_start=NOW - timedelta(minutes=rule.time_window_minutes),
            now=NOW,
        )


def test_night_login_of_a_daytime_user_fires(
    db: Session, history: Callable[..., str]
) -> None:
    name = history(days=10, hours=range(8, 18))
    triggered, payload = _check(db, _rule(), {name: [(3, 12)]})

    assert triggered is True
    (row,) = payload["unusual_logins"]
    assert row["username"] == name
    assert row["hour"] == 3 and row["share"] == 0.0
    assert row["login_at"] == "2026-11-07T03:12:00+07:00"
    assert row["usual_hours"] == list(range(8, 18))
    assert row["total_logins"] == 100
    assert row["source_ips"] == [SRC]
    assert row["devices"] == [f"core-sw1 ({NAS})"]
    assert "nas_ips" not in row  # a helper for naming devices, not payload
    assert payload["rule"] == "[System] Login at Unusual Hour"


def test_usual_hour_and_neighbouring_hour_do_not_fire(
    db: Session, history: Callable[..., str]
) -> None:
    name = history(days=10, hours=range(8, 18))
    # 07:xx is one hour before the earliest usual hour: still "around" it
    triggered, payload = _check(db, _rule(), {name: [(7, 59), (12, 0)]})
    assert (triggered, payload) == (False, {})


def test_thin_history_is_skipped(db: Session, history: Callable[..., str]) -> None:
    name = history(days=6, hours=range(8, 18))  # one day short of MIN_HISTORY_DAYS
    stranger = f"hrs_{uuid.uuid4().hex[:8]}"  # no history at all
    triggered, _ = _check(db, _rule(), {name: [(3, 12)], stranger: [(3, 12)]})
    assert triggered is False


def test_the_windows_own_day_is_not_part_of_the_baseline(
    db: Session, history: Callable[..., str]
) -> None:
    name = history(days=10, hours=range(8, 18))
    # The stats run already counted this very login (and more) for today.
    history(days=1, hours=[3], username=name, first_day=date(2026, 11, 7), per_hour=50)

    triggered, payload = _check(db, _rule(), {name: [(3, 12)]})
    assert triggered is True and payload["unusual_logins"][0]["share"] == 0.0


def test_threshold_is_the_share_in_percent(
    db: Session, history: Callable[..., str]
) -> None:
    name = history(days=10, hours=range(8, 18))
    # 3 of 103 logins fall around 03: 2.9 %
    history(days=3, hours=[3], username=name, first_day=date(2026, 10, 10))

    assert _check(db, _rule(threshold=2.0), {name: [(3, 12)]})[0] is False
    triggered, payload = _check(db, _rule(threshold=5.0), {name: [(3, 12)]})
    assert triggered is True
    assert payload["unusual_logins"][0]["share"] == 2.9


def test_already_reported_logins_are_not_repeated(
    db: Session, history: Callable[..., str]
) -> None:
    name = history(days=10, hours=range(8, 18))
    rule = _rule(last_fired_at=datetime(2026, 11, 7, 3, 12, 30, tzinfo=HCM))

    # 03:12 was reported by the previous firing; 03:14 is new
    assert _check(db, rule, {name: [(3, 12)]})[0] is False
    triggered, payload = _check(db, rule, {name: [(3, 12), (3, 14)]})
    assert triggered is True
    assert payload["unusual_logins"][0]["logins"] == 1
    assert payload["unusual_logins"][0]["login_at"] == "2026-11-07T03:14:00+07:00"


def test_rarest_user_first_and_all_logins_counted(
    db: Session, history: Callable[..., str]
) -> None:
    a = history(days=10, hours=range(8, 18))
    b = history(days=10, hours=range(8, 18))
    history(days=1, hours=[3], username=b, first_day=date(2026, 10, 10))  # b: 1 of 101

    triggered, payload = _check(db, _rule(), {b: [(3, 12), (3, 13)], a: [(3, 11)]})
    assert triggered is True
    # a has no login near 03 at all (0.0 %), b has one in 101 (1.0 %)
    assert [r["username"] for r in payload["unusual_logins"]] == [a, b]
    by_name = {r["username"]: r for r in payload["unusual_logins"]}
    assert by_name[b]["logins"] == 2
    assert by_name[a]["logins"] == 1


def test_login_at_an_unusual_hour_reads_as_a_sentence(
    db: Session, history: Callable[..., str]
) -> None:
    name = history(days=10, hours=range(8, 18))
    _, payload = _check(db, _rule(), {name: [(3, 12)]})
    payload = {**payload, "node": "primary", "fired_at": "2026-11-07T03:15:00+07:00"}

    msg = build_alert_message(rule=_rule(), payload=payload)
    text = render_text(msg)

    assert msg.subject == "[MEDIUM] Login at Unusual Hour"
    assert (
        "1 user logged in at an hour they rarely use (based on their last 30 days)."
        in text
    )
    assert f"👤 {name} — logged in at 2026-11-07 03:12:00 +07" in text
    assert (
        "Only 0.0% of their 100 logins fall around 03:00 (usual hours: 08–18)" in text
    )
    assert f"Source: {SRC}" in text
    assert f"Device: core-sw1 ({NAS})" in text
    assert "{'" not in text and "['" not in text


# --- peers and idempotence ----------------------------------------------------------


def test_upsert_hourly_updates_in_place(db: Session) -> None:
    name = f"hrs_{uuid.uuid4().hex[:8]}"
    day = date(2026, 10, 20)
    try:
        for count in (1, 5):
            upsert_hourly(
                db,
                node_name="n1",
                log_date=day,
                rows=[
                    {
                        "username": name,
                        "hour": 9,
                        "success_count": count,
                        "fail_count": 0,
                    },
                    {"username": name, "hour": 99, "success_count": 1, "fail_count": 0},
                ],
            )
            db.commit()
        rows = db.exec(select(Hourly).where(Hourly.username == name)).all()
        assert [(r.hour, r.success_count) for r in rows] == [(9, 5)]  # 99: not an hour
    finally:
        db.exec(delete(Hourly).where(Hourly.username == name))  # type: ignore[call-overload]
        db.commit()


def test_peer_stats_carry_hourly_rows_and_old_peers_do_not(db: Session) -> None:
    name = f"hrs_{uuid.uuid4().hex[:8]}"
    try:
        _upsert_peer_stats(db, {"node_name": "old-peer", "date": "2026-11-05"})
        _upsert_peer_stats(
            db,
            {
                "node_name": "standby-1",
                "date": "2026-11-05",
                "authentication_hourly": [
                    {"username": name, "hour": 3, "success_count": 2, "fail_count": 1}
                ],
            },
        )
        db.commit()
        (row,) = db.exec(select(Hourly).where(Hourly.username == name)).all()
        assert (row.node_name, row.log_date, row.hour, row.success_count) == (
            "standby-1",
            date(2026, 11, 5),
            3,
            2,
        )
    finally:
        db.exec(delete(Hourly).where(Hourly.username == name))  # type: ignore[call-overload]
        db.commit()


# --- the rule is created off, and stays however the admin sets it --------------------

RULE_NAME = "[System] Login at Unusual Hour"


@pytest.fixture
def fresh_rule(db: Session) -> Generator[None, None, None]:
    def clear() -> None:
        for rule in db.exec(select(AlertRule).where(AlertRule.name == RULE_NAME)).all():
            db.exec(delete(AlertEvent).where(AlertEvent.rule_id == rule.id))  # type: ignore[call-overload]
            db.delete(rule)
        db.commit()

    clear()
    yield
    clear()
    db_module._seed_system_alert_rules(db)  # leave the dev DB as init_db would
    db.commit()


def _stored(db: Session) -> AlertRule:
    db.expire_all()
    return db.exec(select(AlertRule).where(AlertRule.name == RULE_NAME)).one()


@pytest.mark.usefixtures("fresh_rule")
def test_system_rule_is_created_disabled_and_admin_choice_survives(db: Session) -> None:
    db_module._seed_system_alert_rules(db)
    db.commit()
    rule = _stored(db)
    assert rule.enabled is False
    assert rule.is_system is True
    assert (rule.condition_field, rule.condition_operator, rule.threshold) == (
        "login_hour",
        "unusual",
        2.0,
    )

    rule.enabled = True
    rule.threshold = 5.0
    db.add(rule)
    db.commit()

    db_module._seed_system_alert_rules(db)  # every primary start
    db.commit()
    rule = _stored(db)
    assert rule.enabled is True
    assert rule.threshold == 5.0


def test_a_rule_definition_without_enabled_starts_enabled(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    suffix = uuid.uuid4().hex[:8]
    base = {
        "log_type": "auth",
        "condition_field": "fail_count",
        "condition_operator": "gt",
        "threshold": 1.0,
    }
    on, off = f"[System] on {suffix}", f"[System] off {suffix}"
    monkeypatch.setattr(
        db_module,
        "_SYSTEM_ALERT_RULES",
        [{"name": on, **base}, {"name": off, "enabled": False, **base}],
    )
    try:
        db_module._seed_system_alert_rules(db)
        db.commit()
        state = {
            r.name: r.enabled
            for r in db.exec(
                select(AlertRule).where(col(AlertRule.name).in_([on, off]))
            )
        }
        assert state == {on: True, off: False}
    finally:
        db.exec(delete(AlertRule).where(col(AlertRule.name).in_([on, off])))  # type: ignore[call-overload]
        db.commit()
