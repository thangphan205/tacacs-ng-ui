"""Core alert evaluation engine — called by the background worker every 5 minutes."""

import ipaddress
import json
import logging
import os
import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlmodel import Session, col, select

from app.core.config import settings
from app.crud import alert_events as crud_alert_events
from app.crud import alert_rules as crud_alert_rules
from app.crud.alert_formatter import build_alert_message, render_text
from app.crud.notification_dispatcher import dispatch_notification
from app.models import (
    AlertRule,
    AuditLog,
    AuthenticationStatistics,
    Host,
    NotificationChannel,
)
from scripts._log_stats_base import build_log_file_path, local_date, local_tz

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
    """
    Return the log file paths covering the time window, newest first.

    tac_plus-ng names its files by local day, so the window's instants are
    mapped to local days: with the UTC date, a zone west of UTC looked for a
    file that did not exist yet every evening and evaluated nothing.
    """
    day = local_date(now)
    first_day = local_date(window_start)
    paths: list[str] = []
    while day >= first_day:
        paths.append(build_log_file_path(day, log_type, settings.TACACS_LOG_DIRECTORY))
        day -= timedelta(days=1)
    return [p for p in paths if os.path.exists(p)]


@dataclass
class _Activity:
    """What one username or one source IP did inside the window."""

    success: int = 0
    fail: int = 0
    peers: set[str] = field(default_factory=set)  # source IPs, or usernames
    nas_ips: set[str] = field(default_factory=set)
    first: datetime | None = None
    last: datetime | None = None

    def add(
        self, *, ts: datetime, ok: bool, failed: bool, peer: str, nas_ip: str
    ) -> None:
        self.success += ok
        self.fail += failed
        self.peers.add(peer)
        self.nas_ips.add(nas_ip)
        self.first = ts if self.first is None else min(self.first, ts)
        self.last = ts if self.last is None else max(self.last, ts)


@dataclass
class AuthWindow:
    """Authentication activity parsed from the live log for one window."""

    fail_by_user: dict[str, int] = field(default_factory=dict)
    fail_by_ip: dict[str, int] = field(default_factory=dict)
    fail_by_nas: dict[str, int] = field(default_factory=dict)
    by_user: dict[str, _Activity] = field(default_factory=dict)
    by_ip: dict[str, _Activity] = field(default_factory=dict)

    @property
    def seen_usernames(self) -> set[str]:
        return set(self.by_user)

    @property
    def seen_ips(self) -> set[str]:
        return set(self.by_ip)


def _parse_auth_log(window_start: datetime, now: datetime) -> AuthWindow:
    """
    Parse the auth log for the time window.

    Success follows the stats collector (`succeeded` in the message); a
    failure is a `failed` or `denied` message, as before.
    """
    fail_by_user: dict[str, int] = defaultdict(int)
    fail_by_ip: dict[str, int] = defaultdict(int)
    fail_by_nas: dict[str, int] = defaultdict(int)
    by_user: dict[str, _Activity] = defaultdict(_Activity)
    by_ip: dict[str, _Activity] = defaultdict(_Activity)

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
                    nas_ip = m.group("nas_ip")
                    client_ip = m.group("client_ip") or nas_ip
                    ok = "succeeded" in msg
                    failed = "failed" in msg or "denied" in msg
                    by_user[username].add(
                        ts=ts, ok=ok, failed=failed, peer=client_ip, nas_ip=nas_ip
                    )
                    by_ip[client_ip].add(
                        ts=ts, ok=ok, failed=failed, peer=username, nas_ip=nas_ip
                    )
                    if failed:
                        fail_by_user[username] += 1
                        fail_by_ip[client_ip] += 1
                        fail_by_nas[nas_ip] += 1
        except OSError:
            pass

    return AuthWindow(
        fail_by_user=dict(fail_by_user),
        fail_by_ip=dict(fail_by_ip),
        fail_by_nas=dict(fail_by_nas),
        by_user=dict(by_user),
        by_ip=dict(by_ip),
    )


def _parse_authz_log(
    window_start: datetime, now: datetime
) -> tuple[dict[str, int], dict[str, int]]:
    """Parse authz log for the time window. Returns (deny_by_user, deny_by_nas)."""
    deny_by_user: dict[str, int] = defaultdict(int)
    deny_by_nas: dict[str, int] = defaultdict(int)

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
                        deny_by_nas[m.group("nas_ip")] += 1
        except OSError:
            pass

    return dict(deny_by_user), dict(deny_by_nas)


def _device_labels(session: Session, ips: Iterable[str]) -> dict[str, str]:
    """
    Best-effort NAS IP → `"<host name> (<ip>)"` from the Hosts table.

    A host address may be a single IP or a network; the most specific match
    wins. A /0 catch-all says nothing about which device it is, so it is
    ignored. IPs without a match are left out (shown as the bare IP).
    """
    wanted: dict[str, ipaddress.IPv4Address | ipaddress.IPv6Address] = {}
    for ip in ips:
        try:
            wanted[ip] = ipaddress.ip_address(ip)
        except ValueError:
            continue
    if not wanted:
        return {}

    networks: list[tuple[ipaddress.IPv4Network | ipaddress.IPv6Network, str]] = []
    for name, v4, v6 in session.exec(
        select(Host.name, Host.ipv4_address, Host.ipv6_address)
    ).all():
        for raw in (v4, v6):
            if not raw:
                continue
            try:
                network = ipaddress.ip_network(raw.strip(), strict=False)
            except ValueError:
                continue
            if network.prefixlen:
                networks.append((network, name))

    labels: dict[str, str] = {}
    for ip, addr in wanted.items():
        best: tuple[int, str] | None = None
        for network, name in networks:
            if network.version != addr.version or addr not in network:
                continue
            if best is None or network.prefixlen > best[0]:
                best = (network.prefixlen, name)
        if best:
            labels[ip] = f"{best[1]} ({ip})"
    return labels


def _iso_local(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(local_tz()).isoformat(timespec="seconds")


def _top(
    counts: dict[str, int], labels: dict[str, str] | None = None, limit: int = 10
) -> list[dict[str, Any]]:
    """`[{name, count}]`, highest count first."""
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit]
    return [
        {"name": (labels or {}).get(key, key), "count": count} for key, count in ordered
    ]


def _activity_rows(
    keys: Iterable[str],
    activity: dict[str, _Activity],
    *,
    key_field: str,
    peers_field: str,
    labels: dict[str, str],
) -> list[dict[str, Any]]:
    """Detail rows for new/offending users or IPs; successes first."""
    rows: list[dict[str, Any]] = []
    for key in keys:
        act = activity.get(key) or _Activity()
        rows.append(
            {
                key_field: key,
                "success": act.success,
                "fail": act.fail,
                peers_field: sorted(act.peers),
                "devices": [labels.get(ip, ip) for ip in sorted(act.nas_ips)],
                "first_seen": _iso_local(act.first),
                "last_seen": _iso_local(act.last),
            }
        )
    rows.sort(
        key=lambda r: (r["success"] == 0, -(r["success"] + r["fail"]), r[key_field])
    )
    return rows


def _nas_ips(activity: dict[str, _Activity], keys: Iterable[str]) -> set[str]:
    return {ip for key in keys if key in activity for ip in activity[key].nas_ips}


def _baseline_days(window_start: datetime) -> tuple[date, date]:
    """
    The log days of the 30-day baseline before `window_start`.

    Stats rows carry the day of their log file, so the bounds are the local
    days the instants fall on. The last day is the window's own day, which
    the periodic stats run has already partly collected, as the old midnight-timestamp
    `log_date < window_start` comparison also included.
    """
    return (
        local_date(window_start - timedelta(days=30)),
        local_date(window_start),
    )


def _baseline_usernames(window_start: datetime, session: Session) -> set[str]:
    """Usernames seen in the 30-day baseline period (from DB — historical data is fine for baseline)."""
    first_day, last_day = _baseline_days(window_start)
    return set(
        session.exec(
            select(AuthenticationStatistics.username)
            .where(AuthenticationStatistics.log_date >= first_day)
            .where(AuthenticationStatistics.log_date <= last_day)
            .distinct()
        ).all()
    )


def _baseline_ips(window_start: datetime, session: Session) -> set[str]:
    """Source IPs seen in the 30-day baseline period."""
    first_day, last_day = _baseline_days(window_start)
    return set(
        session.exec(
            select(AuthenticationStatistics.user_source_ip)
            .where(AuthenticationStatistics.log_date >= first_day)
            .where(AuthenticationStatistics.log_date <= last_day)
            .distinct()
        ).all()
    )


# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------


def _enabled_channels(session: Session) -> list[NotificationChannel]:
    return list(
        session.exec(
            select(NotificationChannel).where(NotificationChannel.enabled == True)  # noqa: E712
        ).all()
    )


def evaluate_all_rules(*, session: Session) -> None:
    """Evaluate all alert rules that are due. Fire notifications for triggered rules."""
    rules = crud_alert_rules.get_rules_due_evaluation(session=session)
    if not rules:
        return

    channels = _enabled_channels(session)

    for rule in rules:
        # One instant per rule: the window ends here and last_fired_at is set
        # to it, so the next window of a config rule starts where this ended.
        now = datetime.now(timezone.utc)
        try:
            triggered, payload = _evaluate_rule(rule=rule, session=session, now=now)
        except Exception:
            logger.exception("Error evaluating rule %s (%s)", rule.id, rule.name)
            continue

        if not triggered:
            continue

        payload = {**payload, "node": settings.NODE_NAME, "fired_at": _iso_local(now)}
        payload_str = json.dumps(payload)

        if not channels:
            # Still recorded, so Alert History shows what fired and why
            # before any channel is set up (#357).
            crud_alert_events.create_alert_event(
                session=session,
                rule_id=rule.id,
                channel_id=None,
                payload_snapshot=payload_str,
                status="no_channel",
            )

        message = build_alert_message(rule=rule, payload=payload)
        body = render_text(message)
        for channel in channels:
            success, error_msg = dispatch_notification(
                channel=channel,
                subject=message.subject,
                body=body,
                payload=payload,
                message=message,
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
    *, rule: AlertRule, session: Session, now: datetime | None = None
) -> tuple[bool, dict]:
    """Return (triggered, payload_dict)."""
    now = now or datetime.now(timezone.utc)
    window_start = now - timedelta(minutes=rule.time_window_minutes)

    if rule.log_type in ("auth", "all"):
        triggered, payload = _check_auth_stats(
            rule=rule, session=session, window_start=window_start, now=now
        )
        if triggered:
            return True, payload

    if rule.log_type in ("authz", "all"):
        triggered, payload = _check_authz_stats(
            rule=rule, session=session, window_start=window_start, now=now
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
    window = _parse_auth_log(window_start, now)
    common = {"window_minutes": rule.time_window_minutes, "rule": rule.name}

    if field == "username" and operator == "new_value":
        baseline = _baseline_usernames(window_start, session)
        new_usernames = sorted(window.seen_usernames - baseline)
        if not new_usernames:
            return False, {}
        labels = _device_labels(session, _nas_ips(window.by_user, new_usernames))
        return True, {
            "new_usernames": new_usernames,
            "users": _activity_rows(
                new_usernames,
                window.by_user,
                key_field="username",
                peers_field="source_ips",
                labels=labels,
            ),
            **common,
        }

    if field == "client_ip" and operator == "new_value":
        baseline = _baseline_ips(window_start, session)
        new_ips = sorted(window.seen_ips - baseline)
        if not new_ips:
            return False, {}
        labels = _device_labels(session, _nas_ips(window.by_ip, new_ips))
        return True, {
            "new_source_ips": new_ips,
            "sources": _activity_rows(
                new_ips,
                window.by_ip,
                key_field="ip",
                peers_field="usernames",
                labels=labels,
            ),
            **common,
        }

    if field == "client_ip" and operator in ("gt", "lt", "eq"):
        matches = [
            (ip, count)
            for ip, count in window.fail_by_ip.items()
            if _compare(value=float(count), operator=operator, threshold=threshold)
        ]
        matches.sort(key=lambda pair: (-pair[1], pair[0]))
        if not matches:
            return False, {}
        ips = [ip for ip, _ in matches]
        labels = _device_labels(session, _nas_ips(window.by_ip, ips))
        sources = _activity_rows(
            ips, window.by_ip, key_field="ip", peers_field="usernames", labels=labels
        )
        # Offending IPs stay in fail-count order, not successes-first.
        sources.sort(key=lambda r: (-r["fail"], r["ip"]))
        return True, {
            "triggered_ips": [{"ip": ip, "fail_count": count} for ip, count in matches],
            "ip": matches[0][0],
            "fail_count": matches[0][1],
            "sources": sources,
            **common,
        }

    if field in ("fail_count", "result") and operator in ("gt", "lt", "eq"):
        total_fail = sum(window.fail_by_user.values())
        if not _compare(
            value=float(total_fail), operator=operator, threshold=threshold
        ):
            return False, {}
        labels = _device_labels(session, window.fail_by_nas)
        return True, {
            "fail_count": total_fail,
            "top_users": _top(window.fail_by_user),
            "top_sources": _top(window.fail_by_ip),
            "top_devices": _top(window.fail_by_nas, labels),
            **common,
        }

    return False, {}


def _check_authz_stats(
    *, rule: AlertRule, session: Session, window_start: datetime, now: datetime
) -> tuple[bool, dict]:
    operator = rule.condition_operator
    threshold = rule.threshold or 0

    if operator in ("gt", "lt", "eq"):
        deny_by_user, deny_by_nas = _parse_authz_log(window_start, now)
        total_deny = sum(deny_by_user.values())
        if not _compare(
            value=float(total_deny), operator=operator, threshold=threshold
        ):
            return False, {}
        labels = _device_labels(session, deny_by_nas)
        return True, {
            "deny_count": total_deny,
            "top_users": _top(deny_by_user),
            "top_devices": _top(deny_by_nas, labels),
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

_MAX_CHANGES = 10


def _as_utc(moment: datetime) -> datetime:
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def _config_filename(row: AuditLog) -> str | None:
    """The config's filename from the audit snapshot (old_values for DELETE)."""
    for raw in (row.new_values, row.old_values):
        if not raw:
            continue
        try:
            filename = json.loads(raw).get("filename")
        except (ValueError, AttributeError):
            continue
        if filename:
            return str(filename)
    return None


def _check_audit_logs(
    *, rule: AlertRule, session: Session, window_start: datetime
) -> tuple[bool, dict]:
    actions = _CONFIG_ACTION_MAP.get(
        rule.condition_operator, ["CREATE", "UPDATE", "DELETE"]
    )
    # Rows the previous firing already reported are not reported again: with
    # a cooldown no longer than the window, consecutive windows overlap.
    since = window_start
    if rule.last_fired_at is not None:
        since = max(since, _as_utc(rule.last_fired_at))
    rows = session.exec(
        select(AuditLog)
        .where(
            AuditLog.entity_type == "TacacsConfig",
            col(AuditLog.action).in_(actions),
            AuditLog.created_at >= since,
        )
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).all()
    count = len(rows)
    threshold = int(rule.threshold or 1)
    triggered = count >= threshold
    changes = [
        {
            "action": r.action,
            "filename": _config_filename(r),
            "entity_id": r.entity_id,
            "by": r.user_email,
            "ip_address": r.ip_address,
            "at": _iso_local(r.created_at),
        }
        for r in rows[:_MAX_CHANGES]
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
