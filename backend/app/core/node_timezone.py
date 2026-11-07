"""The time zone a node runs in, and whether two zones are the same.

HA nodes must all run in one time zone, the log time zone set under TACACS NG
Settings. tac_plus-ng names its log files and stamps its lines in the process
zone (the container's TZ), while "today", the statistics' log_date and the
alert windows use the one replicated TacacsNgSetting.timezone. A node in
another zone would look for the wrong day's file around midnight and its daily
statistics would cover a different 24 h than the other nodes'. This is not
supported; it is detected and reported (HA page, startup log) instead.
"""

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

_SAMPLE_DAYS = 15
_SAMPLE_SPAN_DAYS = 2 * 366  # covers every DST rule change a year ahead


def node_timezone() -> str:
    """This node's zone: TZ, else /etc/localtime's zone name, else UTC."""
    tz = os.environ.get("TZ", "").strip().lstrip(":")
    if tz:
        return tz
    try:
        target = os.path.realpath("/etc/localtime")
    except OSError:
        target = ""
    if "zoneinfo/" in target:
        return target.split("zoneinfo/", 1)[1]
    return "UTC"


def _zone(name: str | None) -> ZoneInfo | None:
    try:
        return ZoneInfo((name or "UTC").strip() or "UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return None


def same_zone(a: str | None, b: str | None, *, now: datetime | None = None) -> bool:
    """Whether two zone names keep the same UTC offset, now and for two years.

    Aliases count as the same zone (Asia/Saigon, Asia/Ho_Chi_Minh), as do UTC
    and Etc/UTC. An unknown name only matches the identical name.
    """
    za, zb = _zone(a), _zone(b)
    if za is None or zb is None:
        return (a or "UTC").strip() == (b or "UTC").strip()
    start = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    for day in range(0, _SAMPLE_SPAN_DAYS, _SAMPLE_DAYS):
        moment = start + timedelta(days=day)
        if moment.astimezone(za).utcoffset() != moment.astimezone(zb).utcoffset():
            return False
    return True
