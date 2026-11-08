"""Parse one tac_plus-ng log line.

Shared by the TACACS Logs page (api/routes/tacacs_logs.py), the real-time
SIEM shipper (crud/siem_tailer.py), the statistics collectors
(scripts/_log_stats_base.py) and the alert evaluator, so all of them read a
line the same way.

tac_plus-ng's default file format (``tac_plus-ng/utils.c``) is the timestamp
and a space, then TAB-separated columns::

    ${TIMESTAMP} ${nas}<TAB>${user}<TAB>${port}<TAB>${nac}<TAB><type-specific rest>

``port`` and ``nac`` (the client address as the device reports it) are
frequently empty, and ``nac`` is free text — ``localhost``, ``console``,
``Unknown host - non-tty`` — not always an IP address (#400). So the line is
split on TABs by position rather than matched field by field: a regex that
requires a non-empty port and an IP-shaped client dropped most lines from
some devices, and whitespace matching between fields let an empty column
shift the rest.
"""

import ipaddress
import re
from dataclasses import dataclass

from app.models import TacacsLogEvent

_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4}")
_TIMESTAMP_LEN = len("2026-01-01 00:00:00 +0000")
# nas, user, port, nac, and everything after nac (kept whole: it is the message)
_COLUMNS = 5


def is_ip_address(value: str | None) -> bool:
    """True for an IPv4 or IPv6 address (a zone suffix such as ``%eth0`` is allowed)."""
    if not value:
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        return False
    return True


@dataclass(frozen=True, slots=True)
class LogFields:
    """The columns common to authentication, authorization and accounting lines."""

    timestamp: str
    nas_ip: str
    username: str
    port: str | None  # None when the column is empty
    client: str | None  # the nac column as logged; None when empty
    message: str  # the rest of the line, its TABs kept

    @property
    def source_ip(self) -> str:
        """
        The address statistics and alerts attribute the line to: the client
        when it is an IP address, otherwise the NAS. Authentication statistics
        and the alert evaluator always fell back to the NAS like this, so the
        stored history and the new-source-IP baseline keep their meaning.
        """
        if self.client is not None and is_ip_address(self.client):
            return self.client
        return self.nas_ip


def split_log_line(line: str) -> LogFields | None:
    """The columns of one line, or None when it is not in tac_plus-ng's default shape."""
    line = line.rstrip("\r\n")
    if not _TIMESTAMP.fullmatch(line[:_TIMESTAMP_LEN]):
        return None
    if line[_TIMESTAMP_LEN : _TIMESTAMP_LEN + 1] not in (" ", "\t"):
        return None
    columns = line[_TIMESTAMP_LEN + 1 :].split("\t", _COLUMNS - 1)
    if len(columns) != _COLUMNS:
        return None
    nas_ip, username, port, client = (c.strip() for c in columns[:4])
    # Only the end is stripped: a leading TAB is an empty first column
    # (an authorization line with no profile), and positions matter.
    message = columns[4].rstrip()
    if not nas_ip or not username:
        return None
    return LogFields(
        timestamp=line[:_TIMESTAMP_LEN],
        nas_ip=nas_ip,
        username=username,
        port=port or None,
        client=client or None,
        message=message,
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


def _column(message: str, index: int) -> str:
    """One TAB column of the part after nac, lowercased; "" when absent."""
    parts = message.split("\t")
    return parts[index].strip().lower() if index < len(parts) else ""


def authorization_result(message: str) -> str | None:
    """``permit`` or ``deny`` from an authorization line's result column.

    The message is ``${profile}<TAB>${result}<TAB>${service}<TAB>${cmd}``; reading the
    column keeps a profile named e.g. ``permit_all`` from deciding the result.
    """
    result = _column(message, 1)
    return result if result in ("permit", "deny") else None


def accounting_action(message: str) -> str | None:
    """``start`` or ``stop`` from an accounting line (``${accttype}<TAB>${service}<TAB>${cmd}``)."""
    # accttype is never empty, so the first token is it however it is separated
    first = message.split(None, 1)
    action = first[0].lower() if first else ""
    return action if action in ("start", "stop") else None


def classify_result(log_type: str, message: str) -> str:
    if log_type == "authorization" and (result := authorization_result(message)):
        return result
    if log_type == "accounting" and (action := accounting_action(message)):
        return action
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
    fields = split_log_line(line)
    if fields is None:
        return None
    message = fields.message
    # Session ID: deterministic grouping key (no DB needed)
    session_id = "|".join(
        [fields.username, fields.nas_ip, fields.client or "", fields.port or ""]
    )
    return TacacsLogEvent(
        timestamp=fields.timestamp,
        log_type=log_type,
        username=fields.username,
        nas_ip=fields.nas_ip,
        client_ip=fields.client,
        result=classify_result(log_type, message),
        message=message,
        command=extract_command(log_type, message),
        port=fields.port,
        session_id=session_id,
    )
