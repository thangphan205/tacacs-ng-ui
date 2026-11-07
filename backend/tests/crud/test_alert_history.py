"""Alert History keeps every fired alert, with or without channels (#357)."""

import json
import uuid
from collections.abc import Generator
from unittest.mock import patch

import pytest
from sqlmodel import Session, delete, select

from app.crud import alert_evaluator
from app.crud import alert_events as crud_alert_events
from app.crud import notification_channels as crud_channels
from app.models import AlertEvent, AlertRule, NotificationChannel

PAYLOAD = {"new_usernames": ["intruder"], "rule": "test"}


@pytest.fixture
def rule(db: Session) -> Generator[AlertRule, None, None]:
    r = AlertRule(
        name=f"history-{uuid.uuid4().hex[:8]}",
        log_type="auth",
        condition_field="username",
        condition_operator="new_value",
        severity="high",
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    yield r
    db.exec(delete(AlertEvent).where(AlertEvent.rule_id == r.id))  # type: ignore[call-overload]
    db.exec(delete(AlertRule).where(AlertRule.id == r.id))  # type: ignore[call-overload]
    db.commit()


@pytest.fixture
def channel(db: Session) -> Generator[NotificationChannel, None, None]:
    c = NotificationChannel(
        name=f"history-{uuid.uuid4().hex[:8]}", channel_type="webhook"
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    yield c
    db.exec(delete(NotificationChannel).where(NotificationChannel.id == c.id))  # type: ignore[call-overload]
    db.commit()


def _fire(
    db: Session, rule: AlertRule, channels: list[NotificationChannel]
) -> list[AlertEvent]:
    with (
        patch.object(
            alert_evaluator.crud_alert_rules,
            "get_rules_due_evaluation",
            return_value=[rule],
        ),
        patch.object(alert_evaluator, "_enabled_channels", return_value=channels),
        patch.object(alert_evaluator, "_evaluate_rule", return_value=(True, PAYLOAD)),
        patch.object(
            alert_evaluator, "dispatch_notification", return_value=(True, None)
        ),
    ):
        alert_evaluator.evaluate_all_rules(session=db)
    return list(db.exec(select(AlertEvent).where(AlertEvent.rule_id == rule.id)).all())


def test_fired_without_channels_is_recorded(db: Session, rule: AlertRule) -> None:
    events = _fire(db, rule, [])
    assert len(events) == 1
    ev = events[0]
    assert ev.status == "no_channel"
    assert ev.channel_id is None
    snapshot = json.loads(ev.payload_snapshot or "")
    assert snapshot.items() >= PAYLOAD.items()
    # context the notification shows is stored too
    assert snapshot["node"] and snapshot["fired_at"]
    db.refresh(rule)
    assert rule.last_fired_at is not None


def test_one_event_per_channel_when_channels_exist(
    db: Session, rule: AlertRule, channel: NotificationChannel
) -> None:
    events = _fire(db, rule, [channel])
    assert [(e.status, e.channel_id) for e in events] == [("sent", channel.id)]


def test_deleting_a_channel_keeps_its_events(
    db: Session, rule: AlertRule, channel: NotificationChannel
) -> None:
    _fire(db, rule, [channel])
    crud_channels.delete_notification_channel(session=db, db_channel=channel)
    db.expire_all()

    events = db.exec(select(AlertEvent).where(AlertEvent.rule_id == rule.id)).all()
    assert len(events) == 1
    assert events[0].status == "sent"
    assert events[0].channel_id is None


def test_history_and_statistics_with_no_channel_events(
    db: Session, rule: AlertRule
) -> None:
    before = crud_alert_events.get_alert_statistics(session=db)
    _fire(db, rule, [])
    after = crud_alert_events.get_alert_statistics(session=db)

    assert after.total == before.total + 1
    assert after.no_channel == before.no_channel + 1
    # failed used to be total - sent, which would count this as a failure
    assert after.failed == before.failed
    assert after.sent == before.sent

    listed, _ = crud_alert_events.get_alert_events(
        session=db, rule_id=rule.id, status="no_channel"
    )
    assert len(listed) == 1
    assert listed[0].channel_id is None
    assert listed[0].channel_name is None
    assert listed[0].rule_name == rule.name
