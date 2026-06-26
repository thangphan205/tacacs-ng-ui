import uuid
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, col, func, select

from app.models import (
    AlertEvent,
    AlertEventPublic,
    AlertRule,
    AlertStatistics,
    AlertStatisticsRuleItem,
    AlertStatisticsSeverityItem,
    NotificationChannel,
)


def create_alert_event(
    *,
    session: Session,
    rule_id: uuid.UUID,
    channel_id: uuid.UUID,
    payload_snapshot: str | None = None,
    status: str = "sent",
    error_message: str | None = None,
) -> AlertEvent:
    event = AlertEvent(
        rule_id=rule_id,
        channel_id=channel_id,
        triggered_at=datetime.now(timezone.utc),
        payload_snapshot=payload_snapshot,
        status=status,
        error_message=error_message,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def get_alert_events(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    rule_id: uuid.UUID | None = None,
    status: str | None = None,
) -> tuple[list[AlertEventPublic], int]:
    query = select(AlertEvent)
    count_query = select(func.count()).select_from(AlertEvent)

    if rule_id is not None:
        query = query.where(AlertEvent.rule_id == rule_id)
        count_query = count_query.where(AlertEvent.rule_id == rule_id)
    if status is not None:
        query = query.where(AlertEvent.status == status)
        count_query = count_query.where(AlertEvent.status == status)

    count = session.exec(count_query).one()
    events = session.exec(
        query.order_by(AlertEvent.triggered_at.desc()).offset(skip).limit(limit)
    ).all()  # type: ignore[attr-defined]

    result: list[AlertEventPublic] = []
    for event in events:
        rule = session.get(AlertRule, event.rule_id)
        channel = session.get(NotificationChannel, event.channel_id)
        result.append(
            AlertEventPublic(
                id=event.id,
                rule_id=event.rule_id,
                channel_id=event.channel_id,
                triggered_at=event.triggered_at,
                payload_snapshot=event.payload_snapshot,
                status=event.status,
                error_message=event.error_message,
                rule_name=rule.name if rule else None,
                channel_name=channel.name if channel else None,
                rule_severity=rule.severity if rule else None,
                created_at=event.created_at,
            )
        )
    return result, count


def get_alert_statistics(*, session: Session) -> AlertStatistics:
    now = datetime.now(timezone.utc)

    total = session.exec(select(func.count()).select_from(AlertEvent)).one() or 0
    sent = (
        session.exec(
            select(func.count())
            .select_from(AlertEvent)
            .where(AlertEvent.status == "sent")
        ).one()
        or 0
    )
    failed = total - sent

    last_24h = (
        session.exec(
            select(func.count())
            .select_from(AlertEvent)
            .where(AlertEvent.triggered_at >= now - timedelta(hours=24))
        ).one()
        or 0
    )
    last_7d = (
        session.exec(
            select(func.count())
            .select_from(AlertEvent)
            .where(AlertEvent.triggered_at >= now - timedelta(days=7))
        ).one()
        or 0
    )

    # count by severity via join to AlertRule
    sev_rows = session.exec(
        select(AlertRule.severity, func.count(col(AlertEvent.id)))
        .join(AlertRule, col(AlertEvent.rule_id) == col(AlertRule.id))
        .group_by(AlertRule.severity)
        .order_by(func.count(col(AlertEvent.id)).desc())
    ).all()
    by_severity = [
        AlertStatisticsSeverityItem(severity=sev, count=cnt) for sev, cnt in sev_rows
    ]

    rule_rows = session.exec(
        select(AlertRule.name, func.count(col(AlertEvent.id)))
        .join(AlertRule, col(AlertEvent.rule_id) == col(AlertRule.id))
        .group_by(AlertRule.name)
        .order_by(func.count(col(AlertEvent.id)).desc())
        .limit(10)
    ).all()
    by_rule = [
        AlertStatisticsRuleItem(rule_name=name, count=cnt) for name, cnt in rule_rows
    ]

    return AlertStatistics(
        total=total,
        sent=sent,
        failed=failed,
        by_severity=by_severity,
        by_rule=by_rule,
        last_24h=last_24h,
        last_7d=last_7d,
    )


def get_last_fired_for_rule(*, session: Session, rule_id: uuid.UUID) -> datetime | None:
    event = session.exec(
        select(AlertEvent)
        .where(AlertEvent.rule_id == rule_id)
        .order_by(AlertEvent.triggered_at.desc())  # type: ignore[attr-defined]
        .limit(1)
    ).first()
    return event.triggered_at if event else None
