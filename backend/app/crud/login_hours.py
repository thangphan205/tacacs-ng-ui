"""
"Login at Unusual Hour": compare a login's hour with the user's own history.

The baseline is the user's successful logins per hour of day over the 30 days
before the window, from `AuthenticationHourlyStatistics`. A login is unusual
when the hour it happened in, plus one hour either side, holds less than a
set share of all of that user's logins. The neighbouring hours absorb daylight
saving shifts and logins near the edge of an hour, and a share (not "never
logged in at this hour") keeps one stray night login from making that hour
normal for the next 30 days.

Pure functions over plain data, plus one query; the evaluator does the log
parsing and the notification.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, col, select

from app.models import AuthenticationHourlyStatistics as Hourly
from scripts._log_stats_base import local_date, local_tz

BASELINE_DAYS = 30
# Fewer days of history than this and the user's pattern is not known yet. A
# brand-new account is the New Username rule's business.
MIN_HISTORY_DAYS = 7
NEIGHBOUR_HOURS = 1
DEFAULT_MAX_SHARE = 2.0  # percent of the user's logins
USUAL_HOUR_SHARE = 5.0  # an hour with at least this share counts as "usual"

# (time, client IP, NAS IP) of one successful login
Login = tuple[datetime, str, str]


@dataclass
class HourProfile:
    """One user's successful logins per hour of day, and how many days that spans."""

    by_hour: dict[int, int] = field(default_factory=dict)
    days: int = 0

    @property
    def total(self) -> int:
        return sum(self.by_hour.values())

    def share_around(self, hour: int) -> float:
        """Percent of all logins within NEIGHBOUR_HOURS of `hour` (wraps midnight)."""
        total = self.total
        if not total:
            return 0.0
        near = sum(
            self.by_hour.get((hour + d) % 24, 0)
            for d in range(-NEIGHBOUR_HOURS, NEIGHBOUR_HOURS + 1)
        )
        return near * 100 / total

    def usual_hours(self) -> list[int]:
        """Hours that each hold a real share of the user's logins."""
        total = self.total
        return sorted(
            h
            for h, n in self.by_hour.items()
            if total and n * 100 / total >= USUAL_HOUR_SHARE
        )


def baseline_days(window_start: datetime) -> tuple[date, date]:
    """
    The log days of the baseline: the 30 before the window's first day.

    The window's own days are left out because the periodic stats run has
    already partly collected them, so a login would be part of its own history.
    """
    first = local_date(window_start)
    return first - timedelta(days=BASELINE_DAYS), first - timedelta(days=1)


def load_profiles(
    session: Session, usernames: Iterable[str], first_day: date, last_day: date
) -> dict[str, HourProfile]:
    """Hour profiles for the given users; users with no history are absent."""
    names = sorted(set(usernames))
    if not names:
        return {}
    where = (
        col(Hourly.username).in_(names),
        Hourly.log_date >= first_day,
        Hourly.log_date <= last_day,
        Hourly.success_count > 0,
    )
    profiles: dict[str, HourProfile] = {}
    hourly_rows: Sequence[Any] = session.exec(
        select(col(Hourly.username), col(Hourly.hour), func.sum(Hourly.success_count))
        .where(*where)
        .group_by(col(Hourly.username), col(Hourly.hour))
    ).all()
    for username, hour, count in hourly_rows:
        profiles.setdefault(username, HourProfile()).by_hour[hour] = int(count)
    day_rows: Sequence[Any] = session.exec(
        select(col(Hourly.username), func.count(func.distinct(Hourly.log_date)))
        .where(*where)
        .group_by(col(Hourly.username))
    ).all()
    for username, days in day_rows:
        profiles.setdefault(username, HourProfile()).days = int(days)
    return profiles


def find_unusual(
    logins: Mapping[str, Sequence[Login]],
    profiles: Mapping[str, HourProfile],
    *,
    max_share: float,
) -> list[dict[str, Any]]:
    """
    One row per user with at least one unusual login, rarest first.

    `login_at` / `hour` / `share` describe the user's earliest unusual login;
    `logins` counts all of them. `nas_ips` is for the evaluator to name the
    devices and is not part of the stored payload.
    """
    tz = local_tz()
    rows: list[dict[str, Any]] = []
    for username, user_logins in logins.items():
        profile = profiles.get(username)
        if profile is None or profile.days < MIN_HISTORY_DAYS or not profile.total:
            continue
        unusual: list[tuple[datetime, int, float, str, str]] = []
        for ts, client_ip, nas_ip in user_logins:
            hour = ts.astimezone(tz).hour
            share = profile.share_around(hour)
            if share < max_share:
                unusual.append((ts, hour, share, client_ip, nas_ip))
        if not unusual:
            continue
        unusual.sort(key=lambda u: u[0])
        ts, hour, share, _, _ = unusual[0]
        rows.append(
            {
                "username": username,
                "login_at": ts.astimezone(tz).isoformat(timespec="seconds"),
                "hour": hour,
                "share": round(share, 1),
                "logins": len(unusual),
                "total_logins": profile.total,
                "usual_hours": profile.usual_hours(),
                "source_ips": sorted({u[3] for u in unusual}),
                "nas_ips": sorted({u[4] for u in unusual}),
            }
        )
    rows.sort(key=lambda r: (r["share"], r["username"]))
    return rows
