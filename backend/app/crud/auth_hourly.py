"""Hourly login counts per user: the baseline for the unusual-hour alert."""

from collections import Counter
from collections.abc import Iterable
from datetime import date
from typing import Any

from sqlmodel import Session, select

from app.models import AuthenticationHourlyStatistics


def counter_to_rows(hourly: Counter[tuple[str, int, str]]) -> list[dict[str, Any]]:
    """`(username, hour, "success"|"fail") -> n` as one row per (username, hour)."""
    cells = {(username, hour) for username, hour, _ in hourly}
    return [
        {
            "username": username,
            "hour": hour,
            "success_count": hourly.get((username, hour, "success"), 0),
            "fail_count": hourly.get((username, hour, "fail"), 0),
        }
        for username, hour in sorted(cells)
    ]


def upsert_hourly(
    session: Session,
    *,
    node_name: str,
    log_date: date,
    rows: Iterable[dict[str, Any]],
) -> None:
    """Insert or update one node's hourly counts for a log day. Caller commits."""
    for row in rows:
        hour = int(row["hour"])
        if not 0 <= hour <= 23:
            continue
        stat = session.exec(
            select(AuthenticationHourlyStatistics).where(
                AuthenticationHourlyStatistics.username == row["username"],
                AuthenticationHourlyStatistics.log_date == log_date,
                AuthenticationHourlyStatistics.hour == hour,
                AuthenticationHourlyStatistics.node_name == node_name,
            )
        ).first()
        if stat:
            stat.success_count = row["success_count"]
            stat.fail_count = row["fail_count"]
        else:
            stat = AuthenticationHourlyStatistics(
                node_name=node_name,
                username=row["username"],
                log_date=log_date,
                hour=hour,
                success_count=row["success_count"],
                fail_count=row["fail_count"],
            )
        session.add(stat)
