import os
import re
import sys
from collections import Counter
from datetime import date, datetime, time as time_, timedelta, timezone
from zoneinfo import ZoneInfo

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

_AUTHZ_IP = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
AUTHZ_LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{_AUTHZ_IP})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?P<tty>[\w/.-]+)\s+"
    rf"(?P<client_ip>{_AUTHZ_IP})\s+"
    r"(?:(?P<profile>[\w.-]+)\s+)?(?P<message>.*)$"
)

ACCT_LOG_REGEX = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} [+-]\d{4})\s+"
    rf"(?P<nas_ip>{_AUTHZ_IP})\s+"
    r"(?P<username>[\w.-]+)\s+"
    r"(?P<tty>[\w/.-]+)\s+"
    rf"(?P<client_ip>{_AUTHZ_IP})\s+"
    r"(?P<action>start|stop)\s*(?P<message>.*)$"
)


def _get_local_tz() -> ZoneInfo:
    """Read timezone from DB setting, fall back to TZ env var, then UTC."""
    try:
        from app.core.db import engine
        from app.models import TacacsNgSetting
        from sqlmodel import Session, select
        with Session(engine) as session:
            setting = session.exec(select(TacacsNgSetting)).first()
            if setting and setting.timezone:
                return ZoneInfo(setting.timezone)
    except Exception:
        pass
    try:
        return ZoneInfo(os.environ.get("TZ", "UTC"))
    except Exception:
        return ZoneInfo("UTC")


def get_target_date() -> date:
    """Return date from argv[1] (YYYY-MM-DD) or yesterday in the configured local timezone."""
    if len(sys.argv) > 1:
        try:
            return datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(f"Invalid date argument '{sys.argv[1]}'. Expected YYYY-MM-DD. Using yesterday.")
    return (datetime.now(_get_local_tz()) - timedelta(days=1)).date()


def to_log_datetime(d: date) -> datetime:
    """Convert a date to midnight UTC datetime for DB storage."""
    return datetime.combine(d, time_.min).replace(tzinfo=timezone.utc)


def build_log_file_path(target_date: date, log_type: str, log_directory: str) -> str:
    """Construct log file path: {log_directory}/{YYYY}/{MM}/{log_type}-YYYY-MM-DD.log"""
    return target_date.strftime(f"{log_directory}%Y/%m/{log_type}-%Y-%m-%d.log")


# ---------------------------------------------------------------------------
# Pure-parse functions — read log file, return Counters, NO DB access.
# Used by cron scripts and by the internal collect-stats API endpoint.
# ---------------------------------------------------------------------------

def parse_authentication_logs(
    target_date: date, log_directory: str
) -> tuple[Counter, Counter]:
    """Return (successful_logins, failed_logins) Counters keyed by (username, nas_ip, client_ip)."""
    target_date_str = target_date.strftime("%Y-%m-%d")
    log_file_path = build_log_file_path(target_date, "authentication", log_directory)

    successful_logins: Counter = Counter()
    failed_logins: Counter = Counter()

    if not os.path.exists(log_file_path):
        return successful_logins, failed_logins

    try:
        with open(log_file_path, "r", errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
                    continue
                match = AUTH_LOG_REGEX.search(line)
                if not match:
                    continue
                log_data = match.groupdict()
                message = log_data["message"]
                if "login" not in message:
                    continue
                username = log_data["username"]
                nas_ip = log_data["nas_ip"]
                client_ip = log_data["client_ip"] or nas_ip
                key = (username, nas_ip, client_ip)
                if "succeeded" in message:
                    successful_logins[key] += 1
                else:
                    failed_logins[key] += 1
    except IOError:
        pass

    return successful_logins, failed_logins


def parse_authorization_logs(
    target_date: date, log_directory: str
) -> tuple[Counter, Counter]:
    """Return (permitted, denied) Counters keyed by (username, nas_ip, client_ip)."""
    target_date_str = target_date.strftime("%Y-%m-%d")
    log_file_path = build_log_file_path(target_date, "authorization", log_directory)

    permitted: Counter = Counter()
    denied: Counter = Counter()

    if not os.path.exists(log_file_path):
        return permitted, denied

    try:
        with open(log_file_path, "r", errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
                    continue
                match = AUTHZ_LOG_REGEX.search(line)
                if not match:
                    continue
                log_data = match.groupdict()
                message = log_data["message"].strip()
                if "permit" not in message and "deny" not in message:
                    continue
                username = log_data["username"]
                nas_ip = log_data["nas_ip"]
                client_ip = log_data["client_ip"]
                key = (username, nas_ip, client_ip)
                if "permit" in message:
                    permitted[key] += 1
                elif "deny" in message:
                    denied[key] += 1
    except IOError:
        pass

    return permitted, denied


def parse_accounting_logs(
    target_date: date, log_directory: str
) -> tuple[Counter, Counter]:
    """Return (start_events, stop_events) Counters keyed by (username, nas_ip, client_ip)."""
    target_date_str = target_date.strftime("%Y-%m-%d")
    log_file_path = build_log_file_path(target_date, "accounting", log_directory)

    start_events: Counter = Counter()
    stop_events: Counter = Counter()

    if not os.path.exists(log_file_path):
        return start_events, stop_events

    try:
        with open(log_file_path, "r", errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
                    continue
                match = ACCT_LOG_REGEX.search(line)
                if not match:
                    continue
                log_data = match.groupdict()
                action = log_data.get("action")
                if not action:
                    continue
                username = log_data["username"]
                nas_ip = log_data["nas_ip"]
                client_ip = log_data["client_ip"]
                key = (username, nas_ip, client_ip)
                if action == "start":
                    start_events[key] += 1
                elif action == "stop":
                    stop_events[key] += 1
    except IOError:
        pass

    return start_events, stop_events
