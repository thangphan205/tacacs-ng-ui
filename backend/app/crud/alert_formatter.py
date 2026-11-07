"""
Turn a fired alert into a message a person can act on.

The evaluator produces a structured payload (counts, usernames, source IPs,
devices, audit rows). This module builds one `AlertMessage` from it, answering
what happened, who, from where, on which device, when and on which node, and
renders that message for each channel type.

Text that comes from logs or the database (usernames, IPs, filenames, emails)
is carried as `Code` parts, so each renderer escapes or code-formats it for its
own markup and a crafted username can never inject formatting or HTML.
"""

import html
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings
from app.models import AlertRule
from scripts._log_stats_base import local_tz

MAX_ENTRIES = 10  # users / IPs / config changes listed per message
MAX_VALUES = 5  # values listed inside one entry (source IPs, devices, …)

SEVERITY_ICON = {"low": "🟡", "medium": "🟠", "high": "🔴", "critical": "🚨"}

_OPERATOR_SYMBOL = {"gt": ">", "lt": "<", "eq": "="}

_ACTION_ICON = {"CREATE": "➕", "UPDATE": "✏️", "DELETE": "🗑", "ACTIVATE": "🚀"}

_CONFIG_NOUN = {
    "activated": "activation",
    "created": "creation",
    "updated": "update",
    "deleted": "deletion",
}

_SYSTEM_PREFIX = "[System] "

# Payload keys that are context for the message, not details of the event.
_GENERIC_SKIP = {"rule", "node", "fired_at", "window_minutes", "ip"}


@dataclass(frozen=True)
class Code:
    """An identifier from the logs or the database."""

    text: str


@dataclass(frozen=True)
class Bold:
    text: str


Part = str | Code | Bold
Line = list[Part]


@dataclass
class AlertMessage:
    severity: str
    title: str
    body: list[Line] = field(default_factory=list)
    footer: list[Line] = field(default_factory=list)
    link: str | None = None

    @property
    def subject(self) -> str:
        return f"[{self.severity.upper()}] {self.title}"

    @property
    def heading(self) -> str:
        icon = SEVERITY_ICON.get(self.severity, "⚠️")
        return f"{icon} {self.severity.upper()} · {self.title}"


# ---------------------------------------------------------------------------
# Small formatting helpers
# ---------------------------------------------------------------------------


def _plural(count: int, noun: str) -> str:
    return f"{count} {noun}" if count == 1 else f"{count} {noun}s"


def _num(value: float | int | None) -> str:
    if value is None:
        return "—"
    return str(int(value)) if float(value).is_integer() else str(value)


def _parse_time(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value:
        try:
            moment = datetime.fromisoformat(value)
        except ValueError:
            return None
    else:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(local_tz())


def format_time(value: Any) -> str:
    """A timestamp in the log timezone, e.g. `2026-11-07 21:00:25 +07`."""
    moment = _parse_time(value)
    if moment is None:
        return str(value) if value else "—"
    return moment.strftime("%Y-%m-%d %H:%M:%S %Z")


def _span(first: Any, last: Any) -> str:
    start, end = _parse_time(first), _parse_time(last)
    if start is None or end is None:
        return format_time(first or last)
    if start == end:
        return format_time(start)
    if start.date() == end.date():
        return f"{format_time(start)} → {end.strftime('%H:%M:%S')}"
    return f"{format_time(start)} → {format_time(end)}"


def _codes(values: Sequence[Any], limit: int = MAX_VALUES) -> list[Part]:
    """`a, b, c +2 more` with every value code-formatted."""
    if not values:
        return ["—"]
    parts: list[Part] = []
    for i, value in enumerate(values[:limit]):
        if i:
            parts.append(", ")
        parts.append(Code(str(value)))
    if len(values) > limit:
        parts.append(f" +{len(values) - limit} more")
    return parts


def _counts(rows: Sequence[dict[str, Any]], limit: int = MAX_VALUES) -> list[Part]:
    """`alice 8 · bob 6` from `[{name, count}]`."""
    parts: list[Part] = []
    for i, row in enumerate(rows[:limit]):
        if i:
            parts.append(" · ")
        parts.extend([Code(str(row.get("name", "?"))), f" {row.get('count', 0)}"])
    if len(rows) > limit:
        parts.append(f" +{len(rows) - limit} more")
    return parts


def _more(lines: list[Line], total: int, shown: int) -> None:
    if total > shown:
        lines.append([f"… +{total - shown} more"])


def _title(rule_name: str) -> str:
    if rule_name.startswith(_SYSTEM_PREFIX):
        return rule_name[len(_SYSTEM_PREFIX) :]
    return rule_name


def _threshold(rule: AlertRule) -> str:
    symbol = _OPERATOR_SYMBOL.get(rule.condition_operator, rule.condition_operator)
    return f"threshold {symbol} {_num(rule.threshold)}"


# ---------------------------------------------------------------------------
# Builders, one per kind of alert
# ---------------------------------------------------------------------------


def _activity_entry(
    icon: str, key: str, row: dict[str, Any], peers_label: str, peers_key: str
) -> list[Line]:
    """One user or source IP: totals, then where it came from and when."""
    ok, fail = row.get("success"), row.get("fail")
    head: Line = [f"{icon} ", Code(key)]
    if ok is not None or fail is not None:
        head.append(f" — ✅ {ok or 0} ok · ❌ {fail or 0} failed")
    lines: list[Line] = [head]
    if peers_key in row:
        lines.append([f"   {peers_label}: ", *_codes(row.get(peers_key) or [])])
    if "devices" in row:
        lines.append(["   Device: ", *_codes(row.get("devices") or [])])
    if row.get("first_seen") or row.get("last_seen"):
        lines.append([f"   Seen: {_span(row.get('first_seen'), row.get('last_seen'))}"])
    return lines


def _activity_section(
    msg: AlertMessage,
    rows: list[dict[str, Any]],
    *,
    icon: str,
    key_field: str,
    peers_label: str,
    peers_key: str,
) -> None:
    for row in rows[:MAX_ENTRIES]:
        msg.body.append([])
        msg.body.extend(
            _activity_entry(icon, str(row[key_field]), row, peers_label, peers_key)
        )
    _more(msg.body, len(rows), min(len(rows), MAX_ENTRIES))


def _successes(rows: list[dict[str, Any]], key_field: str) -> list[str]:
    return [str(r[key_field]) for r in rows if r.get("success")]


def _new_usernames(msg: AlertMessage, payload: dict[str, Any], window: int) -> None:
    names = payload.get("new_usernames") or []
    rows = payload.get("users") or [{"username": n} for n in names]
    msg.body.append(
        [
            f"{_plural(len(names), 'username')} not seen in the past 30 days "
            f"appeared in the last {window} min."
        ]
    )
    ok = _successes(rows, "username")
    if ok:
        msg.body.append([Bold("⚠️ Logged in successfully: "), *_codes(ok)])
    _activity_section(
        msg,
        rows,
        icon="👤",
        key_field="username",
        peers_label="Source",
        peers_key="source_ips",
    )


def _new_source_ips(msg: AlertMessage, payload: dict[str, Any], window: int) -> None:
    ips = payload.get("new_source_ips") or []
    rows = payload.get("sources") or [{"ip": ip} for ip in ips]
    msg.body.append(
        [
            f"{_plural(len(ips), 'source IP')} not seen in the past 30 days "
            f"appeared in the last {window} min."
        ]
    )
    ok = _successes(rows, "ip")
    if ok:
        msg.body.append([Bold("⚠️ Successful logins from: "), *_codes(ok)])
    _activity_section(
        msg, rows, icon="🌐", key_field="ip", peers_label="Users", peers_key="usernames"
    )


def _ip_threshold(
    msg: AlertMessage, rule: AlertRule, payload: dict[str, Any], window: int
) -> None:
    matches = payload.get("triggered_ips") or []
    rows = payload.get("sources") or [
        {"ip": m.get("ip"), "fail": m.get("fail_count")} for m in matches
    ]
    msg.body.append(
        [
            f"{_plural(len(matches), 'source IP')} with failed logins in the last "
            f"{window} min ({_threshold(rule)} per IP)."
        ]
    )
    _activity_section(
        msg, rows, icon="🌐", key_field="ip", peers_label="Users", peers_key="usernames"
    )


def _top_lines(msg: AlertMessage, payload: dict[str, Any]) -> None:
    labels = (
        ("top_users", "Top users"),
        ("top_sources", "Top sources"),
        ("top_devices", "Top devices"),
    )
    lines = [
        [f"{label}: ", *_counts(payload[key])]
        for key, label in labels
        if payload.get(key)
    ]
    if lines:
        msg.body.append([])
        msg.body.extend(lines)


def _auth_failures(
    msg: AlertMessage, rule: AlertRule, payload: dict[str, Any], window: int
) -> None:
    total = int(payload.get("fail_count") or 0)
    msg.body.append(
        [
            f"{_plural(total, 'failed login')} in the last {window} min "
            f"({_threshold(rule)})."
        ]
    )
    _top_lines(msg, payload)


def _authz_denials(
    msg: AlertMessage, rule: AlertRule, payload: dict[str, Any], window: int
) -> None:
    total = int(payload.get("deny_count") or 0)
    msg.body.append(
        [
            f"{_plural(total, 'denied authorization')} in the last {window} min "
            f"({_threshold(rule)})."
        ]
    )
    _top_lines(msg, payload)


def _hour_ranges(hours: Sequence[int]) -> str:
    """`[8, 9, 10, 11, 13, 14]` -> `08–12, 13–15` (end hour exclusive)."""
    if not hours:
        return "none yet"
    if len(set(hours)) == 24:
        return "all hours"
    ranges: list[tuple[int, int]] = []
    for hour in sorted(set(hours)):
        if ranges and ranges[-1][1] == hour:
            ranges[-1] = (ranges[-1][0], hour + 1)
        else:
            ranges.append((hour, hour + 1))
    return ", ".join(f"{start:02d}–{end % 24:02d}" for start, end in ranges)


def _unusual_logins(msg: AlertMessage, payload: dict[str, Any]) -> None:
    rows = payload.get("unusual_logins") or []
    msg.body.append(
        [
            f"{_plural(len(rows), 'user')} logged in at an hour they rarely use "
            f"(based on their last 30 days)."
        ]
    )
    for row in rows[:MAX_ENTRIES]:
        extra = int(row.get("logins") or 1) - 1
        head: Line = [
            "👤 ",
            Code(str(row.get("username", "?"))),
            f" — logged in at {format_time(row.get('login_at'))}",
        ]
        if extra > 0:
            head.append(f" (+{extra} more unusual in this window)")
        msg.body.append([])
        msg.body.append(head)
        hour = int(row.get("hour") or 0)
        msg.body.append(
            [
                f"   Only {row.get('share', 0)}% of their {row.get('total_logins', 0)} "
                f"logins fall around {hour:02d}:00 "
                f"(usual hours: {_hour_ranges(row.get('usual_hours') or [])})"
            ]
        )
        msg.body.append(["   Source: ", *_codes(row.get("source_ips") or [])])
        msg.body.append(["   Device: ", *_codes(row.get("devices") or [])])
    _more(msg.body, len(rows), min(len(rows), MAX_ENTRIES))


def _config_changes(
    msg: AlertMessage, rule: AlertRule, payload: dict[str, Any], window: int
) -> None:
    changes = payload.get("changes") or []
    total = int(payload.get("config_change_count") or len(changes))
    noun = _CONFIG_NOUN.get(rule.condition_operator, "change")
    msg.body.append(
        [f"{_plural(total, f'TACACS config {noun}')} in the last {window} min."]
    )
    for i, change in enumerate(changes[:MAX_ENTRIES], start=1):
        action = str(change.get("action", "?"))
        target = change.get("filename") or change.get("entity_id") or "?"
        msg.body.append([])
        msg.body.append(
            [f"{i}. {_ACTION_ICON.get(action, '•')} {action} ", Code(str(target))]
        )
        by: Line = ["   By: ", Code(str(change.get("by") or "unknown"))]
        if change.get("ip_address"):
            by.extend([" from ", Code(str(change["ip_address"]))])
        msg.body.append(by)
        msg.body.append([f"   At: {format_time(change.get('at'))}"])
    _more(msg.body, total, min(len(changes), MAX_ENTRIES))


def _value_parts(value: Any) -> list[Part]:
    if isinstance(value, list):
        if all(isinstance(v, dict) for v in value):
            return _codes(
                [", ".join(f"{k}={v}" for k, v in item.items()) for item in value]
            )
        return _codes(value)
    if isinstance(value, dict):
        return [Code(", ".join(f"{k}={v}" for k, v in value.items()))]
    return [str(value)]


def _generic(msg: AlertMessage, payload: dict[str, Any]) -> None:
    for key, value in payload.items():
        if key in _GENERIC_SKIP:
            continue
        label = key.replace("_", " ").capitalize()
        msg.body.append([f"{label}: ", *_value_parts(value)])


def build_alert_message(*, rule: AlertRule, payload: dict[str, Any]) -> AlertMessage:
    """Build the human-readable message for a fired rule."""
    msg = AlertMessage(severity=rule.severity, title=_title(rule.name))
    window = int(payload.get("window_minutes") or rule.time_window_minutes)
    path = "/aaa_statistics"

    if "unusual_logins" in payload:
        _unusual_logins(msg, payload)
    elif "new_usernames" in payload:
        _new_usernames(msg, payload, window)
    elif "new_source_ips" in payload:
        _new_source_ips(msg, payload, window)
    elif "triggered_ips" in payload:
        _ip_threshold(msg, rule, payload, window)
    elif "changes" in payload:
        _config_changes(msg, rule, payload, window)
        path = "/audit_logs"
    elif "deny_count" in payload:
        _authz_denials(msg, rule, payload, window)
    elif "fail_count" in payload:
        _auth_failures(msg, rule, payload, window)
    else:
        _generic(msg, payload)
        path = "/alert_events"

    footer: Line = []
    if payload.get("node"):
        footer.extend(["Node ", Code(str(payload["node"])), " · "])
    footer.append(f"fired {format_time(payload.get('fired_at'))}")
    msg.footer.append(footer)
    msg.link = f"{settings.FRONTEND_HOST.rstrip('/')}{path}"
    return msg


# ---------------------------------------------------------------------------
# Renderers
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Style:
    esc: Callable[[str], str]
    code: Callable[[str], str]
    bold: Callable[[str], str]
    link: Callable[[str], str]


def _identity(text: str) -> str:
    return text


def _html_esc(text: str) -> str:
    return html.escape(text, quote=False)


def _slack_esc(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_DISCORD_SPECIAL = re.compile(r"([\\*_~`|>])")


def _discord_esc(text: str) -> str:
    return _DISCORD_SPECIAL.sub(r"\\\1", text)


def _backticked(esc: Callable[[str], str]) -> Callable[[str], str]:
    # A backtick inside an identifier would close the code span early.
    def code(text: str) -> str:
        return "`" + esc(text.replace("`", "'")) + "`"

    return code


TEXT = _Style(
    esc=_identity, code=_identity, bold=_identity, link=lambda u: f"Open: {u}"
)
HTML = _Style(
    esc=_html_esc,
    code=lambda t: f"<code>{_html_esc(t)}</code>",
    bold=lambda t: f"<b>{_html_esc(t)}</b>",
    link=lambda u: f'<a href="{html.escape(u)}">Open in tacacs-ng-ui</a>',
)
SLACK = _Style(
    esc=_slack_esc,
    code=_backticked(_slack_esc),
    bold=lambda t: f"*{_slack_esc(t)}*",
    link=lambda u: f"<{u}|Open in tacacs-ng-ui>",
)
DISCORD = _Style(
    esc=_discord_esc,
    code=_backticked(_identity),
    bold=lambda t: f"**{_discord_esc(t)}**",
    link=lambda u: f"[Open in tacacs-ng-ui]({u})",
)
GCHAT = _Style(
    esc=_identity,
    code=_backticked(_identity),
    bold=lambda t: f"*{t}*",
    link=lambda u: f"<{u}|Open in tacacs-ng-ui>",
)


def _render_line(line: Line, style: _Style) -> str:
    out: list[str] = []
    for part in line:
        if isinstance(part, Code):
            out.append(style.code(part.text))
        elif isinstance(part, Bold):
            out.append(style.bold(part.text))
        else:
            out.append(style.esc(part))
    return "".join(out)


def render(msg: AlertMessage, style: _Style, *, heading: bool = True) -> str:
    """Render the message; `heading=False` for channels that show it separately."""
    lines: list[str] = []
    if heading:
        lines.extend([style.bold(msg.heading), ""])
    lines.extend(_render_line(line, style) for line in msg.body)
    lines.append("")
    lines.extend(_render_line(line, style) for line in msg.footer)
    if msg.link:
        lines.append(style.link(msg.link))
    return "\n".join(lines)


def render_text(msg: AlertMessage) -> str:
    return render(msg, TEXT)
