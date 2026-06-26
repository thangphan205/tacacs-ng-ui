"""Core alert evaluation engine — called by the background worker every 5 minutes."""

import json
import logging
import os
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from datetime import time as dt_time

from sqlmodel import Session, col, select

from app.core.config import settings
from app.crud import alert_events as crud_alert_events
from app.crud import alert_rules as crud_alert_rules
from app.crud.notification_dispatcher import dispatch_notification
from app.models import (
    AlertRule,
    AuditLog,
    AuthenticationStatistics,
    NotificationChannel,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Live log parsing — real-time (no dependency on daily cron)
# ---------------------------------------------------------------------------

_IP = r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}|[a-fA-F0-9]{0,4}(?::[a-fA-F0-9]{0,4})+"
_NON_IP_FIELD = rf"(?:\t(?!(?:{_IP})(?:\t|$))[^\t]*)?"
_AUTH_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{_IP})\t"
    r"(?P<username>[\w.-]+)"
    + _NON_IP_FIELD
    + rf"(?:\t(?P<client_ip>{_IP}))?"
    + r"\t(?P<message>[^\n]+)$"
)
_AUTHZ_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{_IP})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?P<tty>[\w/.-]+)\s+"
    rf"(?P<client_ip>{_IP})\s+"
    r"(?:(?P<profile>[\w.-]+)\s+)?(?P<message>.*)$"
)


def _log_paths_for_window(
    window_start: datetime, now: datetime, log_type: str
) -> list[str]:
    """Return log file paths needed to cover the time window (today + yesterday if spans midnight)."""
    today_path = now.strftime(
        f"{settings.TACACS_LOG_DIRECTORY}%Y/%m/{log_type}-%Y-%m-%d.log"
    )
    paths = [today_path]
    today_midnight = datetime.combine(now.date(), dt_time.min, tzinfo=timezone.utc)
    if window_start < today_midnight:
        yesterday_path = (now - timedelta(days=1)).strftime(
            f"{settings.TACACS_LOG_DIRECTORY}%Y/%m/{log_type}-%Y-%m-%d.log"
        )
        paths.append(yesterday_path)
    return [p for p in paths if os.path.exists(p)]


def _parse_auth_log(
    window_start: datetime, now: datetime
) -> tuple[dict[str, int], dict[str, int], set[str], set[str]]:
    """
    Parse auth log for the time window.
    Returns: (fail_counts_by_user, fail_counts_by_ip, recent_usernames, recent_ips)
    Actually returns (fail_by_user, fail_by_ip, recent_set_of_(user,ip))
    """
    fail_by_user: dict[str, int] = defaultdict(int)
    fail_by_ip: dict[str, int] = defaultdict(int)
    seen_usernames: set[str] = set()
    seen_ips: set[str] = set()

    for path in _log_paths_for_window(window_start, now, "authentication"):
        try:
            with open(path, errors="ignore") as f:
                for line in f:
                    m = _AUTH_REGEX.match(line)
                    if not m:
                        continue
                    try:
                        ts = datetime.strptime(
                            m.group("timestamp"), "%Y-%m-%d %H:%M:%S %z"
                        )
                    except ValueError:
                        continue
                    if ts < window_start or ts > now:
                        continue
                    msg = m.group("message").lower()
                    username = m.group("username")
                    client_ip = m.group("client_ip") or m.group("nas_ip")
                    seen_usernames.add(username)
                    seen_ips.add(client_ip)
                    if "failed" in msg or "denied" in msg:
                        fail_by_user[username] += 1
                        fail_by_ip[client_ip] += 1
        except OSError:
            pass

    return dict(fail_by_user), dict(fail_by_ip), seen_usernames, seen_ips


def _parse_authz_log(window_start: datetime, now: datetime) -> dict[str, int]:
    """Parse authz log for the time window. Returns deny_count_by_user."""
    deny_by_user: dict[str, int] = defaultdict(int)

    for path in _log_paths_for_window(window_start, now, "authorization"):
        try:
            with open(path, errors="ignore") as f:
                for line in f:
                    m = _AUTHZ_REGEX.match(line)
                    if not m:
                        continue
                    try:
                        ts = datetime.strptime(
                            m.group("timestamp"), "%Y-%m-%d %H:%M:%S %z"
                        )
                    except ValueError:
                        continue
                    if ts < window_start or ts > now:
                        continue
                    msg = m.group("message").lower()
                    if "deny" in msg:
                        deny_by_user[m.group("username")] += 1
        except OSError:
            pass

    return dict(deny_by_user)


def _baseline_usernames(window_start: datetime, session: Session) -> set[str]:
    """Usernames seen in the 30-day baseline period (from DB — historical data is fine for baseline)."""
    baseline_start = window_start - timedelta(days=30)
    return set(
        session.exec(
            select(AuthenticationStatistics.username)
            .where(AuthenticationStatistics.log_date >= baseline_start)
            .where(AuthenticationStatistics.log_date < window_start)
            .distinct()
        ).all()
    )


def _baseline_ips(window_start: datetime, session: Session) -> set[str]:
    """Source IPs seen in the 30-day baseline period."""
    baseline_start = window_start - timedelta(days=30)
    return set(
        session.exec(
            select(AuthenticationStatistics.user_source_ip)
            .where(AuthenticationStatistics.log_date >= baseline_start)
            .where(AuthenticationStatistics.log_date < window_start)
            .distinct()
        ).all()
    )


# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------


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


def _evaluate_rule(*, rule: AlertRule, session: Session) -> tuple[bool, dict]:
    """Return (triggered, payload_dict)."""
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=rule.time_window_minutes)

    if rule.log_type in ("auth", "all"):
        triggered, payload = _check_auth_stats(
            rule=rule, session=session, window_start=window_start, now=now
        )
        if triggered:
            return True, payload

    if rule.log_type in ("authz", "all"):
        triggered, payload = _check_authz_stats(
            rule=rule, window_start=window_start, now=now
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
    *, rule: AlertRule, session: Session, window_start: datetime, now: datetime
) -> tuple[bool, dict]:
    field = rule.condition_field
    operator = rule.condition_operator
    threshold = rule.threshold or 0

    fail_by_user, fail_by_ip, seen_usernames, seen_ips = _parse_auth_log(
        window_start, now
    )

    if field == "username" and operator == "new_value":
        baseline = _baseline_usernames(window_start, session)
        new_usernames = seen_usernames - baseline
        if new_usernames:
            return True, {"new_usernames": list(new_usernames), "rule": rule.name}
        return False, {}

    if field == "client_ip" and operator == "new_value":
        baseline = _baseline_ips(window_start, session)
        new_ips = seen_ips - baseline
        if new_ips:
            return True, {"new_source_ips": list(new_ips), "rule": rule.name}
        return False, {}

    if field in ("fail_count", "result") and operator in ("gt", "lt", "eq"):
        total_fail = sum(fail_by_user.values())
        return _compare(
            value=float(total_fail), operator=operator, threshold=threshold
        ), {
            "fail_count": total_fail,
            "window_minutes": rule.time_window_minutes,
            "rule": rule.name,
        }

    return False, {}


def _check_authz_stats(
    *, rule: AlertRule, window_start: datetime, now: datetime
) -> tuple[bool, dict]:
    operator = rule.condition_operator
    threshold = rule.threshold or 0

    if operator in ("gt", "lt", "eq"):
        deny_by_user = _parse_authz_log(window_start, now)
        total_deny = sum(deny_by_user.values())
        return _compare(
            value=float(total_deny), operator=operator, threshold=threshold
        ), {
            "deny_count": total_deny,
            "window_minutes": rule.time_window_minutes,
            "rule": rule.name,
        }

    return False, {}


_CONFIG_ACTION_MAP: dict[str, list[str]] = {
    "any_change": [
        "CREATE",
        "UPDATE",
        "DELETE",
    ],  # ACTIVATE excluded — has its own rule
    "created": ["CREATE"],
    "updated": ["UPDATE"],
    "deleted": ["DELETE"],
    "activated": ["ACTIVATE"],
}


def _check_audit_logs(
    *, rule: AlertRule, session: Session, window_start: datetime
) -> tuple[bool, dict]:
    actions = _CONFIG_ACTION_MAP.get(
        rule.condition_operator, ["CREATE", "UPDATE", "DELETE"]
    )
    rows = session.exec(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "TacacsConfig",
            col(AuditLog.action).in_(actions),
            AuditLog.created_at >= window_start,
        )
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    count = len(rows)
    threshold = int(rule.threshold or 1)
    triggered = count >= threshold
    changes = [
        {
            "action": r.action,
            "entity_id": r.entity_id,
            "by": r.user_email,
            "at": r.created_at.strftime("%Y-%m-%d %H:%M:%S UTC"),
        }
        for r in rows[:5]  # cap at 5 entries to keep message concise
    ]
    return triggered, {
        "config_change_count": count,
        "changes": changes,
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


_SEVERITY_EMOJI = {
    "low": "🟡",
    "medium": "🟠",
    "high": "🔴",
    "critical": "🚨",
}
_LOG_TYPE_EMOJI = {
    "auth": "🔐",
    "authz": "🛡️",
    "config": "⚙️",
    "all": "📋",
}
_PAYLOAD_LABELS: dict[str, str] = {
    "fail_count": "Auth failures",
    "deny_count": "Authz denials",
    "new_usernames": "New usernames",
    "new_source_ips": "New source IPs",
    "config_change_count": "Config changes",
    "actions_checked": "Actions",
    "window_minutes": "Window (min)",
}


def _format_body(*, rule: AlertRule, payload: dict) -> str:
    sev_icon = _SEVERITY_EMOJI.get(rule.severity, "⚠️")
    type_icon = _LOG_TYPE_EMOJI.get(rule.log_type, "📋")
    op_map = {
        "gt": ">",
        "lt": "<",
        "eq": "=",
        "new_value": "new",
        "any_change": "any change",
        "created": "created",
        "updated": "updated",
        "deleted": "deleted",
        "activated": "activated",
    }
    op = op_map.get(rule.condition_operator, rule.condition_operator)
    condition = (
        f"{rule.condition_field} {op} {rule.threshold}"
        if rule.threshold
        else f"{rule.condition_field} {op}"
    )
    lines = [
        f"{sev_icon} Severity: {rule.severity.upper()}",
        f"{type_icon} Log type: {rule.log_type}",
        f"⏱ Window: {rule.time_window_minutes} min",
        f"🎯 Condition: {condition}",
        "",
        "📊 Details:",
    ]
    for k, v in payload.items():
        if k in ("rule", "window_minutes"):
            continue
        label = _PAYLOAD_LABELS.get(k, k.replace("_", " ").title())
        lines.append(f"  • {label}: {v}")
    return "\n".join(lines)
