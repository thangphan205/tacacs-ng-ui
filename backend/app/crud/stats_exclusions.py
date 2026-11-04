"""Usernames excluded from the AAA statistics.

Exclusion is applied when statistics are *read*, never when logs are parsed or
stored: the statistics tables keep every user, so the alert evaluator's
new-user/new-IP baseline, anomaly scoring and SIEM forwarding are unaffected,
adding a pattern also cleans up historical charts, and `include_excluded`
can show the unfiltered numbers again.

Patterns are lower-cased usernames, optionally with `*` as a wildcard, and match
case-insensitively.
"""

import uuid
from collections.abc import Iterable
from fnmatch import fnmatchcase
from typing import Any

from sqlalchemy import and_, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.elements import ColumnElement
from sqlmodel import Session, select

from app.models import StatsExcludedUser, StatsExcludedUserCreate


def list_excluded_users(*, session: Session) -> list[StatsExcludedUser]:
    return list(
        session.exec(select(StatsExcludedUser).order_by(StatsExcludedUser.pattern))
    )


def get_excluded_user_by_id(
    *, session: Session, id: uuid.UUID
) -> StatsExcludedUser | None:
    return session.get(StatsExcludedUser, id)


def create_excluded_user(
    *, session: Session, excluded_user_in: StatsExcludedUserCreate
) -> StatsExcludedUser | None:
    """Create an exclusion; None when the pattern already exists (unique index),
    which also covers two concurrent creates racing past the caller's check."""
    db_obj = StatsExcludedUser.model_validate(excluded_user_in)
    session.add(db_obj)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        return None
    session.refresh(db_obj)
    return db_obj


def delete_excluded_user(*, session: Session, db_obj: StatsExcludedUser) -> None:
    session.delete(db_obj)
    session.commit()


def get_patterns(*, session: Session) -> list[str]:
    """All configured patterns, sorted."""
    return list(
        session.exec(
            select(StatsExcludedUser.pattern).order_by(StatsExcludedUser.pattern)
        )
    )


def resolve_patterns(*, session: Session, include_excluded: bool) -> list[str]:
    """Patterns to apply for a request — none when the caller opted out."""
    if include_excluded:
        return []
    return get_patterns(session=session)


def is_excluded(username: str | None, patterns: Iterable[str]) -> bool:
    if not username:
        return False
    name = username.lower()
    return any(fnmatchcase(name, p) for p in patterns)


def filter_rows(
    rows: Iterable[dict[str, Any]], patterns: list[str]
) -> list[dict[str, Any]]:
    """Drop rows whose `username` matches a pattern."""
    if not patterns:
        return list(rows)
    return [r for r in rows if not is_excluded(r.get("username"), patterns)]


def _glob_to_like(pattern: str) -> str:
    escaped = pattern.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return escaped.replace("*", "%")


def not_excluded_clause(column: Any, patterns: list[str]) -> ColumnElement[bool] | None:
    """SQL condition keeping only rows whose `column` matches no pattern.

    Returns None when there is nothing to exclude, so callers can skip `.where()`.
    """
    if not patterns:
        return None
    lowered = func.lower(column)
    return and_(*(~lowered.like(_glob_to_like(p), escape="\\") for p in patterns))
