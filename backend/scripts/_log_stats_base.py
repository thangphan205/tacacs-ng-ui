import re
import sys
from datetime import date, datetime, time as time_, timedelta, timezone

# Shared authentication log regex — IPv4 and IPv6 support
# Example: "2025-11-23 11:39:08 +0000 103.161.38.106\tuser_admin\t\t10.3.13.20\tshell login failed"
_IP = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
AUTH_LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{_IP})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?:[\w.-]+\s+)?"
    rf"(?P<client_ip>{_IP})\s+"
    r"(?P<message>.*)$"
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
