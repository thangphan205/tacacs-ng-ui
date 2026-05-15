import re
import sys
from datetime import date, datetime, time as time_, timedelta, timezone

# IPv4 or IPv6 — requires dots or colons so plain port/session numbers (e.g. "39001") don't match.
# Supported log formats (tab-separated after timestamp+nas_ip):
#   with client IP:    nas_ip\tuser\t[tty]\tclient_ip\tmessage
#   without client IP: nas_ip\tuser\tport\tflag\tmessage  (e.g. PAP where client IP absent)
_IP = r"(?:[0-9]{1,3}\.){3}[0-9]{1,3}|[a-fA-F0-9]{0,4}(?::[a-fA-F0-9]{0,4})+"

# Optional non-IP field (tty/port/flag) — skipped only when it is NOT a valid IP.
_NON_IP_FIELD = rf"(?:\t(?!(?:{_IP})(?:\t|$))[^\t]*)?"

AUTH_LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{_IP})\t"
    r"(?P<username>[\w.-]+)"
    + _NON_IP_FIELD                          # optional tty / port / flag (not an IP)
    + rf"(?:\t(?P<client_ip>{_IP}))?"        # optional real client IP
    + r"\t(?P<message>[^\n]+)$"
)


def get_target_date() -> date:
    """Return date from argv[1] (YYYY-MM-DD) or yesterday UTC."""
    if len(sys.argv) > 1:
        try:
            return datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date argument '{sys.argv[1]}'. Expected YYYY-MM-DD. Using yesterday.")
    return (datetime.now(timezone.utc) - timedelta(days=1)).date()


def to_log_datetime(d: date) -> datetime:
    """Convert a date to midnight UTC datetime for DB storage."""
    return datetime.combine(d, time_.min).replace(tzinfo=timezone.utc)


def build_log_file_path(target_date: date, log_type: str, log_directory: str) -> str:
    """Construct log file path: {log_directory}/{YYYY}/{MM}/{log_type}-YYYY-MM-DD.log"""
    return target_date.strftime(f"{log_directory}%Y/%m/{log_type}-%Y-%m-%d.log")
