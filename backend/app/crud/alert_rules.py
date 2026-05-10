import uuid
from datetime import datetime, timezone

from sqlmodel import Session, func, select

from app.models import AlertRule, AlertRuleCreate, AlertRuleUpdate


def create_alert_rule(*, session: Session, rule_in: AlertRuleCreate) -> AlertRule:
    rule = AlertRule.model_validate(rule_in)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    return rule


def get_alert_rules(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    enabled_only: bool = False,
) -> tuple[list[AlertRule], int]:
    query = select(AlertRule)
    count_query = select(func.count()).select_from(AlertRule)
    if enabled_only:
        query = query.where(AlertRule.enabled == True)  # noqa: E712
        count_query = count_query.where(AlertRule.enabled == True)  # noqa: E712
    count = session.exec(count_query).one()
    rules = session.exec(query.offset(skip).limit(limit)).all()
    return list(rules), count


def get_alert_rule(*, session: Session, rule_id: uuid.UUID) -> AlertRule | None:
    return session.get(AlertRule, rule_id)


def update_alert_rule(
    *, session: Session, db_rule: AlertRule, rule_in: AlertRuleUpdate
) -> AlertRule:
    update_data = rule_in.model_dump(exclude_unset=True)
    db_rule.sqlmodel_update(update_data)
    session.add(db_rule)
    session.commit()
    session.refresh(db_rule)
    return db_rule


def delete_alert_rule(*, session: Session, db_rule: AlertRule) -> None:
    session.delete(db_rule)
    session.commit()


def set_last_fired(
    *, session: Session, rule_id: uuid.UUID, fired_at: datetime
) -> None:
    rule = session.get(AlertRule, rule_id)
    if rule:
        rule.last_fired_at = fired_at
        session.add(rule)
        session.commit()


def get_rules_due_evaluation(*, session: Session) -> list[AlertRule]:
    """Return enabled rules where cooldown has expired or never fired."""
    now = datetime.now(timezone.utc)
    rules = session.exec(select(AlertRule).where(AlertRule.enabled == True)).all()  # noqa: E712
    due = []
    for rule in rules:
        if rule.last_fired_at is None:
            due.append(rule)
            continue
        last = rule.last_fired_at
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        elapsed = (now - last).total_seconds() / 60
        if elapsed >= rule.cooldown_minutes:
            due.append(rule)
    return due
