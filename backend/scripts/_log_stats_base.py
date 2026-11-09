import os
import sys
import time as _time
from collections import Counter
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.core.tacacs_log_parse import (
    accounting_action,
    authentication_outcome,
    authorization_result,
    split_log_line,
)


def _get_local_tz() -> ZoneInfo:
    """Read timezone from DB setting, fall back to TZ env var, then UTC."""
    try:
        from sqlmodel import Session, select

        from app.core.db import engine
        from app.models import TacacsNgSetting

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


_LOCAL_TZ_TTL = 60.0
_local_tz_cache: tuple[float, ZoneInfo] | None = None


def local_tz() -> ZoneInfo:
    """
    The timezone tac_plus-ng names its log files and stamps its lines in.

    Same lookup as _get_local_tz(), cached briefly because the read path asks
    for it on every dashboard request. The setting is editable in the UI, so
    the cache is short rather than process-long.
    """
    global _local_tz_cache
    now = _time.monotonic()
    if _local_tz_cache and now - _local_tz_cache[0] < _LOCAL_TZ_TTL:
        return _local_tz_cache[1]
    tz = _get_local_tz()
    _local_tz_cache = (now, tz)
    return tz


def local_today() -> date:
    """
    Today's date in the log timezone: the one definition of "today" for both
    the collectors and the read path. Using the UTC date here put the
    dashboard on tomorrow's (still empty) log file every evening west of UTC.
    """
    return datetime.now(local_tz()).date()


def local_date(moment: datetime) -> date:
    """The log-timezone calendar day an aware datetime falls on."""
    return moment.astimezone(local_tz()).date()


def get_target_date() -> date:
    """Return date from argv[1] (YYYY-MM-DD) or yesterday in the configured local timezone."""
    if len(sys.argv) > 1:
        try:
            return datetime.strptime(sys.argv[1], "%Y-%m-%d").date()
        except ValueError:
            print(
                f"Invalid date argument '{sys.argv[1]}'. Expected YYYY-MM-DD. Using yesterday."
            )
    return (datetime.now(_get_local_tz()) - timedelta(days=1)).date()


def parse_log_date(value: str) -> date:
    """
    Read a statistics row's log_date as sent by a peer's collect-stats.

    Current peers send "YYYY-MM-DD". Peers before the fix for #356 send midnight
    UTC of the same day ("YYYY-MM-DDT00:00:00+00:00"), so the leading date is
    the day in both formats and a mixed-version HA pair keeps syncing.
    """
    return date.fromisoformat(value[:10])


def build_log_file_path(target_date: date, log_type: str, log_directory: str) -> str:
    """Construct log file path: {log_directory}/{YYYY}/{MM}/{log_type}-YYYY-MM-DD.log"""
    return target_date.strftime(f"{log_directory}%Y/%m/{log_type}-%Y-%m-%d.log")


# ---------------------------------------------------------------------------
# Pure-parse functions — read log file, return Counters, NO DB access.
# Used by cron scripts and by the internal collect-stats API endpoint.
# ---------------------------------------------------------------------------


def parse_authentication_logs(
    target_date: date, log_directory: str, hourly: Counter | None = None
) -> tuple[Counter, Counter]:
    """Return (successful_logins, failed_logins) Counters keyed by (username, nas_ip, client_ip).

    When `hourly` is given it is filled in the same pass with
    `(username, hour, "success" | "fail")` counts, the hour being the one
    tac_plus-ng stamped on the line (the log timezone).
    """
    target_date_str = target_date.strftime("%Y-%m-%d")
    log_file_path = build_log_file_path(target_date, "authentication", log_directory)

    successful_logins: Counter = Counter()
    failed_logins: Counter = Counter()

    if not os.path.exists(log_file_path):
        return successful_logins, failed_logins

    try:
        with open(log_file_path, errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
                    continue
                fields = split_log_line(line)
                # per-user rows: a line without a username has no row to go in
                if fields is None or fields.username is None:
                    continue
                outcome = authentication_outcome(fields.message)
                if outcome is None:
                    continue
                username = fields.username
                key = (username, fields.nas_ip, fields.source_ip)
                if outcome == "success":
                    successful_logins[key] += 1
                else:
                    failed_logins[key] += 1
                if hourly is not None:
                    # "YYYY-MM-DD HH:MM:SS +ZZZZ": split_log_line checked the shape
                    hourly[(username, int(fields.timestamp[11:13]), outcome)] += 1
    except OSError:
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
        with open(log_file_path, errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
                    continue
                fields = split_log_line(line)
                # per-user rows: a line without a username has no row to go in
                if fields is None or fields.username is None:
                    continue
                result = authorization_result(fields.message)
                key = (fields.username, fields.nas_ip, fields.source_ip)
                if result == "permit":
                    permitted[key] += 1
                elif result == "deny":
                    denied[key] += 1
    except OSError:
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
        with open(log_file_path, errors="ignore") as f:
            for line in f:
                if not line.startswith(target_date_str):
                    continue
                fields = split_log_line(line)
                # per-user rows: a line without a username has no row to go in
                if fields is None or fields.username is None:
                    continue
                action = accounting_action(fields.message)
                key = (fields.username, fields.nas_ip, fields.source_ip)
                if action == "start":
                    start_events[key] += 1
                elif action == "stop":
                    stop_events[key] += 1
    except OSError:
        pass

    return start_events, stop_events
