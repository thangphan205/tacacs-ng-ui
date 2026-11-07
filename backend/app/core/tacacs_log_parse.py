"""Parse one tac_plus-ng log line into a TacacsLogEvent.

Shared by the TACACS Logs page (api/routes/tacacs_logs.py) and the real-time
SIEM shipper (crud/siem_tailer.py), so both read a line the same way.
"""

import re

from app.models import TacacsLogEvent

IP_REGEX = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{IP_REGEX})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?P<port>[\w/.-]+)\s+"  # tty / port field (e.g. vty14, tty0, ssh)
    rf"(?P<client_ip>{IP_REGEX})\s+"
    r"(?P<message>.*)$"
)

# Regex to strip the leading profile name from authorization messages:
# e.g. "tacacs_super_user_profile permit shell show ip route" → group(permit/deny/...) + command
_AUTHZ_CMD_REGEX = re.compile(
    r"^(?:[\w.-]+\s+)?"
    r"(?:permit|deny)\s+"
    r"(?:[\w.-]+\s+)?"  # optional service token (shell, junos-exec, …)
    r"(?P<command>.+?)\s*$",
    re.IGNORECASE,
)
_ACCT_CMD_REGEX = re.compile(
    r"(?:start|stop)\s+"
    r"(?:[\w.-]+\s+)?"  # optional service token
    r"(?P<command>.+?)\s*$",
    re.IGNORECASE,
)

_RESULT_MAPS: dict[str, dict[str, str]] = {
    "authentication": {"succeeded": "success", "failed": "failed", "denied": "failed"},
    "authorization": {"permit": "permit", "deny": "deny"},
    "accounting": {"start": "start", "stop": "stop"},
}


def classify_result(log_type: str, message: str) -> str:
    msg = message.lower()
    for kw, result in _RESULT_MAPS.get(log_type, {}).items():
        if kw in msg:
            return result
    return "unknown"


def extract_command(log_type: str, message: str) -> str | None:
    """Best-effort extraction of a human-readable command from the raw log message."""
    if log_type == "authorization":
        m = _AUTHZ_CMD_REGEX.match(message.strip())
        if m:
            cmd = m.group("command").strip()
            # Strip trailing <cr> artifact common in TACACS+ authz messages
            return cmd.removesuffix("<cr>").strip() or None
    if log_type == "accounting":
        m = _ACCT_CMD_REGEX.search(message.strip())
        if m:
            cmd = m.group("command").strip()
            return cmd.removesuffix("<cr>").strip() or None
    return None


def parse_log_line(log_type: str, line: str) -> TacacsLogEvent | None:
    """One structured event, or None when the line is not in the expected shape."""
    m = LOG_REGEX.match(line.rstrip())
    if not m:
        return None
    d = m.groupdict()
    message = d["message"]
    port = d.get("port") or None
    # Session ID: deterministic grouping key (no DB needed)
    session_id = "|".join([d["username"], d["nas_ip"], d["client_ip"], port or ""])
    return TacacsLogEvent(
        timestamp=d["timestamp"],
        log_type=log_type,
        username=d["username"],
        nas_ip=d["nas_ip"],
        client_ip=d["client_ip"],
        result=classify_result(log_type, message),
        message=message,
        command=extract_command(log_type, message),
        port=port,
        session_id=session_id,
    )
