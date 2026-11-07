"""Timestamps are stored as timestamptz and read back as the same aware instant.

Before, every timestamp column was `timestamp without time zone`: an aware UTC
value was stored as the database session's local wall time and read back
naive, then treated as UTC, so alert cooldowns and API output were off by the
database server's UTC offset. CI's database runs in UTC, which hid it; these
tests set a non-UTC session zone themselves.
"""

import uuid
from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
import sqlalchemy as sa
from sqlalchemy import text
from sqlmodel import Session, SQLModel

import app.models  # noqa: F401  (registers every table)
from app.core.db import engine
from app.crud import alert_rules
from app.models import AlertRule


def test_every_timestamp_column_is_timestamptz() -> None:
    naive = [
        f"{t.name}.{c.name}"
        for t in SQLModel.metadata.sorted_tables
        for c in t.columns
        if isinstance(c.type, sa.DateTime) and not c.type.timezone
    ]
    assert naive == [], "use sa_type=TZ_DATETIME (models.py) for these columns"


def test_app_sessions_run_in_utc() -> None:
    with Session(engine) as session:
        assert session.exec(text("SHOW timezone")).scalar() == "UTC"  # type: ignore[call-overload]


@pytest.fixture()
def rule(db: Session) -> Generator[AlertRule, None, None]:
    r = AlertRule(
        name=f"tz-test-{uuid.uuid4()}",
        log_type="auth",
        condition_field="failed_count",
        condition_operator="gt",
        threshold=1,
        cooldown_minutes=30,
        enabled=True,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    yield r
    db.delete(r)
    db.commit()


@pytest.mark.parametrize("zone", ["Asia/Ho_Chi_Minh", "America/New_York"])
def test_round_trip_keeps_the_instant_in_any_session_zone(
    rule: AlertRule, zone: str
) -> None:
    """A database server in another zone (any HA node's) must not shift values."""
    fired = datetime(2026, 11, 7, 10, 46, 23, tzinfo=timezone.utc)
    # One dedicated connection, so the zone change cannot leak into the pool.
    with engine.connect() as conn:
        conn.execute(text(f"SET TIME ZONE '{zone}'"))
        try:
            with Session(bind=conn) as session:
                alert_rules.set_last_fired(
                    session=session, rule_id=rule.id, fired_at=fired
                )
                session.expire_all()
                back = session.get(AlertRule, rule.id)
                assert back is not None and back.last_fired_at is not None
                assert back.last_fired_at.tzinfo is not None
                assert back.last_fired_at == fired
        finally:
            conn.rollback()
            conn.execute(text("RESET TIME ZONE"))
            conn.commit()


def test_cooldown_counts_from_the_real_firing_time(
    db: Session, rule: AlertRule
) -> None:
    now = datetime.now(timezone.utc)
    alert_rules.set_last_fired(session=db, rule_id=rule.id, fired_at=now)
    due = {r.id for r in alert_rules.get_rules_due_evaluation(session=db)}
    assert rule.id not in due  # inside its 30 min cooldown

    alert_rules.set_last_fired(
        session=db, rule_id=rule.id, fired_at=now - timedelta(minutes=31)
    )
    due = {r.id for r in alert_rules.get_rules_due_evaluation(session=db)}
    assert rule.id in due  # not held back by the server's UTC offset
