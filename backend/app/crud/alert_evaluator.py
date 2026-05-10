"""Core alert evaluation engine — called by the background worker every 5 minutes."""
import json
import logging
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, col, func, select

from app.crud import alert_events as crud_alert_events
from app.crud import alert_rules as crud_alert_rules
from app.crud.notification_dispatcher import dispatch_notification
from app.models import (
    AlertRule,
    AuditLog,
    AuthenticationStatistics,
    AuthorizationStatistics,
    NotificationChannel,
)

logger = logging.getLogger(__name__)


def evaluate_all_rules(*, session: Session) -> None:
    """Evaluate all alert rules that are due. Fire notifications for triggered rules."""
    rules = crud_alert_rules.get_rules_due_evaluation(session=session)
    if not rules:
        return

    channels = session.exec(
        select(NotificationChannel).where(NotificationChannel.enabled == True)  # noqa: E712
    ).all()

    for rule in rules:
        try:
            triggered, payload = _evaluate_rule(rule=rule, session=session)
        except Exception:
            logger.exception("Error evaluating rule %s (%s)", rule.id, rule.name)
            continue

        if not triggered:
            continue

        now = datetime.now(timezone.utc)
        payload_str = json.dumps(payload)

        for channel in channels:
            subject = f"[{rule.severity.upper()}] TACACS Alert: {rule.name}"
            body = _format_body(rule=rule, payload=payload)
            success, error_msg = dispatch_notification(
                channel=channel, subject=subject, body=body
            )
            crud_alert_events.create_alert_event(
                session=session,
                rule_id=rule.id,
                channel_id=channel.id,
                payload_snapshot=payload_str,
                status="sent" if success else "failed",
                error_message=error_msg,
            )
            if not success:
                logger.warning(
                    "Failed to dispatch alert to channel %s: %s", channel.id, error_msg
                )

        crud_alert_rules.set_last_fired(session=session, rule_id=rule.id, fired_at=now)


def _evaluate_rule(
    *, rule: AlertRule, session: Session
) -> tuple[bool, dict]:
    """Return (triggered, payload_dict)."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=rule.time_window_minutes)

    if rule.log_type in ("auth", "all"):
        triggered, payload = _check_auth_stats(
            rule=rule, session=session, window_start=window_start
        )
        if triggered:
            return True, payload

    if rule.log_type in ("authz", "all"):
        triggered, payload = _check_authz_stats(
            rule=rule, session=session, window_start=window_start
        )
        if triggered:
            return True, payload

    if rule.log_type in ("config", "all"):
        triggered, payload = _check_audit_logs(
            rule=rule, session=session, window_start=window_start
        )
        if triggered:
            return True, payload

    return False, {}


def _check_auth_stats(
    *, rule: AlertRule, session: Session, window_start: datetime
) -> tuple[bool, dict]:
    field = rule.condition_field
    operator = rule.condition_operator
    threshold = rule.threshold or 0

    if field == "username" and operator == "new_value":
        # Detect usernames that appear in last window but not in prior 30 days
        baseline_start = window_start - timedelta(days=30)
        recent = set(
            session.exec(
                select(AuthenticationStatistics.username)
                .where(AuthenticationStatistics.log_date >= window_start)
                .distinct()
            ).all()
        )
        baseline = set(
            session.exec(
                select(AuthenticationStatistics.username)
                .where(AuthenticationStatistics.log_date >= baseline_start)
                .where(AuthenticationStatistics.log_date < window_start)
                .distinct()
            ).all()
        )
        new_usernames = recent - baseline
        if new_usernames:
            return True, {"new_usernames": list(new_usernames), "rule": rule.name}
        return False, {}

    if field == "client_ip" and operator == "new_value":
        baseline_start = window_start - timedelta(days=30)
        recent_ips = set(
            session.exec(
                select(AuthenticationStatistics.user_source_ip)
                .where(AuthenticationStatistics.log_date >= window_start)
                .distinct()
            ).all()
        )
        baseline_ips = set(
            session.exec(
                select(AuthenticationStatistics.user_source_ip)
                .where(AuthenticationStatistics.log_date >= baseline_start)
                .where(AuthenticationStatistics.log_date < window_start)
                .distinct()
            ).all()
        )
        new_ips = recent_ips - baseline_ips
        if new_ips:
            return True, {"new_source_ips": list(new_ips), "rule": rule.name}
        return False, {}

    # Numeric: sum fail_count or success_count in window
    if field in ("fail_count", "result") and operator in ("gt", "lt", "eq"):
        total_fail = session.exec(
            select(func.sum(AuthenticationStatistics.fail_count))
            .where(AuthenticationStatistics.log_date >= window_start)
        ).one() or 0
        return _compare(value=float(total_fail), operator=operator, threshold=threshold), {
            "fail_count": total_fail,
            "window_minutes": rule.time_window_minutes,
            "rule": rule.name,
        }

    return False, {}


def _check_authz_stats(
    *, rule: AlertRule, session: Session, window_start: datetime
) -> tuple[bool, dict]:
    operator = rule.condition_operator
    threshold = rule.threshold or 0

    if operator in ("gt", "lt", "eq"):
        total_deny = session.exec(
            select(func.sum(AuthorizationStatistics.deny_count))
            .where(AuthorizationStatistics.log_date >= window_start)
        ).one() or 0
        return _compare(value=float(total_deny), operator=operator, threshold=threshold), {
            "deny_count": total_deny,
            "window_minutes": rule.time_window_minutes,
            "rule": rule.name,
        }

    return False, {}


_CONFIG_ACTION_MAP: dict[str, list[str]] = {
    "any_change": ["CREATE", "UPDATE", "DELETE", "ACTIVATE"],
    "created":    ["CREATE"],
    "updated":    ["UPDATE"],
    "deleted":    ["DELETE"],
    "activated":  ["ACTIVATE"],
}


def _check_audit_logs(
    *, rule: AlertRule, session: Session, window_start: datetime
) -> tuple[bool, dict]:
    actions = _CONFIG_ACTION_MAP.get(rule.condition_operator, ["CREATE", "UPDATE", "DELETE", "ACTIVATE"])
    count = session.exec(
        select(func.count()).where(
            AuditLog.entity_type == "TacacsConfig",
            col(AuditLog.action).in_(actions),
            AuditLog.created_at >= window_start,
        )
    ).one() or 0
    threshold = int(rule.threshold or 1)
    triggered = count >= threshold
    return triggered, {
        "config_change_count": count,
        "actions_checked": actions,
        "window_minutes": rule.time_window_minutes,
        "rule": rule.name,
    }


def _compare(*, value: float, operator: str, threshold: float) -> bool:
    if operator == "gt":
        return value > threshold
    if operator == "lt":
        return value < threshold
    if operator == "eq":
        return value == threshold
    return False


def _format_body(*, rule: AlertRule, payload: dict) -> str:
    lines = [
        f"Rule: {rule.name}",
        f"Severity: {rule.severity}",
        f"Log type: {rule.log_type}",
        f"Condition: {rule.condition_field} {rule.condition_operator} {rule.threshold}",
        f"Window: {rule.time_window_minutes} min",
        "",
        "Details:",
    ]
    for k, v in payload.items():
        if k != "rule":
            lines.append(f"  {k}: {v}")
    return "\n".join(lines)
