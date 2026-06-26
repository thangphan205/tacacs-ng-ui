import logging
import os
import time as _time
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from datetime import time as time_
from typing import Any

import httpx
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    AccountingStatistics,
    AuthenticationStatistics,
    AuthorizationStatistics,
)
from scripts._log_stats_base import AUTH_LOG_REGEX

logger = logging.getLogger(__name__)

_today_cache: dict = {}  # {node_name_or_all: {"date": str, "data": dict, "ts": float}}
_today_authz_cache: dict = {}  # {node_name_or_all: {"date": str, "permit": int, "deny": int, "ts": float}}
_today_acct_cache: dict = {}  # {node_name_or_all: {"date": str, "start": int, "stop": int, "ts": float}}
_LIVE_CACHE_TTL = 60


def _today_authz_counts() -> tuple[int, int]:
    """Return (permit, deny) for today from live authorization log. Cached 60 s."""
    global _today_authz_cache
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    ts = _time.monotonic()
    if (
        _today_authz_cache.get("date") == today_str
        and ts - _today_authz_cache.get("ts", 0.0) < _LIVE_CACHE_TTL
    ):
        return _today_authz_cache["permit"], _today_authz_cache["deny"]

    log_path = today.strftime(
        settings.TACACS_LOG_DIRECTORY + "%Y/%m/authorization-%Y-%m-%d.log"
    )
    permit = deny = 0
    if os.path.exists(log_path):
        try:
            with open(log_path, errors="ignore") as f:
                for line in f:
                    if not line.startswith(today_str):
                        continue
                    low = line.lower()
                    if "\tpermit\t" in low or "\tpermit " in low:
                        permit += 1
                    elif "\tdeny\t" in low or "\tdeny " in low:
                        deny += 1
        except OSError:
            pass

    _today_authz_cache.clear()
    _today_authz_cache.update(
        {"date": today_str, "permit": permit, "deny": deny, "ts": ts}
    )
    return permit, deny


def _today_acct_counts() -> tuple[int, int]:
    """Return (start, stop) for today from live accounting log. Cached 60 s."""
    global _today_acct_cache
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    ts = _time.monotonic()
    if (
        _today_acct_cache.get("date") == today_str
        and ts - _today_acct_cache.get("ts", 0.0) < _LIVE_CACHE_TTL
    ):
        return _today_acct_cache["start"], _today_acct_cache["stop"]

    log_path = today.strftime(
        settings.TACACS_LOG_DIRECTORY + "%Y/%m/accounting-%Y-%m-%d.log"
    )
    start = stop = 0
    if os.path.exists(log_path):
        try:
            with open(log_path, errors="ignore") as f:
                for line in f:
                    if not line.startswith(today_str):
                        continue
                    if "\tstart\t" in line or "\tstart " in line:
                        start += 1
                    elif "\tstop\t" in line or "\tstop " in line:
                        stop += 1
        except OSError:
            pass

    _today_acct_cache.clear()
    _today_acct_cache.update(
        {"date": today_str, "start": start, "stop": stop, "ts": ts}
    )
    return start, stop


def get_peer_urls() -> list[str]:
    """Parse peer nodes from PEER_NODES settings or fallback to PEER_BACKEND_URL."""
    peer_urls = [u.strip() for u in settings.PEER_NODES.split(",") if u.strip()]
    if not peer_urls and settings.PEER_BACKEND_URL:
        peer_urls = [settings.PEER_BACKEND_URL]
    return peer_urls


def parse_local_today_authentication_details() -> list[dict]:
    """Parse local authentication log files for today and return details list."""
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    log_file_path = today.strftime(
        settings.TACACS_LOG_DIRECTORY + "%Y/%m/authentication-%Y-%m-%d.log"
    )
    if not os.path.exists(log_file_path):
        return []

    successful_logins = Counter()
    failed_logins = Counter()
    try:
        with open(log_file_path, errors="ignore") as f:
            for line in f:
                if not line.startswith(today_str):
                    continue
                match = AUTH_LOG_REGEX.search(line)
                if not match:
                    continue
                log_data = match.groupdict()
                msg = log_data["message"].lower()
                username = log_data["username"]
                nas_ip = log_data["nas_ip"]
                client_ip = log_data["client_ip"]
                key = (username, nas_ip, client_ip)
                if "succeeded" in msg:
                    successful_logins[key] += 1
                elif "failed" in msg or "denied" in msg:
                    failed_logins[key] += 1
    except OSError as e:
        logger.error(f"Error reading file {log_file_path}: {e}")
        return []

    all_keys = set(successful_logins.keys()) | set(failed_logins.keys())
    list_authentication_details = []
    for username, nas_ip, user_source_ip in sorted(all_keys):
        key = (username, nas_ip, user_source_ip)
        list_authentication_details.append(
            {
                "username": username,
                "nas_ip": nas_ip,
                "user_source_ip": user_source_ip,
                "success_count": successful_logins.get(key, 0),
                "fail_count": failed_logins.get(key, 0),
            }
        )
    return list_authentication_details


def get_node_today_stats_from_db(
    session: Session, node_name: str, today_dt: datetime
) -> list[dict]:
    """Fetch today's statistics for a given node from the database."""
    stmt = select(AuthenticationStatistics).where(
        AuthenticationStatistics.log_date == today_dt,
        AuthenticationStatistics.node_name == node_name,
    )
    db_rows = session.exec(stmt).all()
    return [
        {
            "username": r.username,
            "nas_ip": r.nas_ip,
            "user_source_ip": r.user_source_ip,
            "success_count": r.success_count,
            "fail_count": r.fail_count,
        }
        for r in db_rows
    ]


def aggregate_today_auth_details(details: list[dict], today_str: str) -> dict[str, Any]:
    """Aggregate raw list of authentication details into summary statistics."""
    successful_auths = 0
    failed_auths = 0

    failed_count_by_user = defaultdict(int)
    success_count_by_user = defaultdict(int)
    success_count_by_ip = defaultdict(int)
    success_count_by_nas_ip = defaultdict(int)

    unique_user_source_ips = set()
    unique_nas_ips = set()

    for row in details:
        u = row["username"]
        n = row["nas_ip"]
        c = row["user_source_ip"]
        s = row.get("success_count", 0)
        f = row.get("fail_count", 0)

        successful_auths += s
        failed_auths += f

        if s > 0 or f > 0:
            unique_user_source_ips.add(c)
            unique_nas_ips.add(n)

        if s > 0:
            success_count_by_user[u] += s
            success_count_by_ip[c] += s
            success_count_by_nas_ip[n] += s
        if f > 0:
            failed_count_by_user[u] += f

    total_events = successful_auths + failed_auths

    authentication_failed_count_by_user = sorted(
        [
            {"username": u, "fail_count": count}
            for u, count in failed_count_by_user.items()
        ],
        key=lambda x: x["fail_count"],
        reverse=True,
    )
    authentication_success_count_by_user = sorted(
        [
            {"username": u, "success_count": count}
            for u, count in success_count_by_user.items()
        ],
        key=lambda x: x["success_count"],
        reverse=True,
    )
    authentication_success_count_by_user_source_ip = sorted(
        [
            {"user_source_ip": ip, "success_count": count}
            for ip, count in success_count_by_ip.items()
        ],
        key=lambda x: x["success_count"],
        reverse=True,
    )
    authentication_success_count_by_nas_ip = sorted(
        [
            {"nas_ip": ip, "success_count": count}
            for ip, count in success_count_by_nas_ip.items()
        ],
        key=lambda x: x["success_count"],
        reverse=True,
    )

    return {
        "today_total_authentication_events": total_events,
        "today": today_str,
        "today_list_authentication_details": details,
        "today_successful_logins": successful_auths,
        "today_failed_logins": failed_auths,
        "today_unique_user_source_ip_count": len(unique_user_source_ips),
        "today_unique_nas_ip_count": len(unique_nas_ips),
        "today_authentication_failed_count_by_user": authentication_failed_count_by_user,
        "today_authentication_success_count_by_user": authentication_success_count_by_user,
        "today_authentication_success_count_by_user_source_ip": authentication_success_count_by_user_source_ip,
        "today_authentication_success_count_by_nas_ip": authentication_success_count_by_nas_ip,
    }


def _set_trend_today(series: list[dict], today_iso: str, count: int) -> None:
    """Replace the count for today's entry in a fill_missing_dates result list."""
    for item in series:
        if item["date"] == today_iso:
            item["count"] = count
            return


def _merge_today_top(
    db_list: list[dict], today_list: list[dict], key_field: str, count_field: str
) -> list[dict]:
    """Merge today's live per-key counts into DB-aggregated list."""
    totals: dict[str, int] = {r[key_field]: r[count_field] for r in db_list}
    for entry in today_list:
        k = entry[key_field]
        totals[k] = totals.get(k, 0) + entry[count_field]
    return sorted(
        [{key_field: k, count_field: v} for k, v in totals.items()],
        key=lambda x: x[count_field],
        reverse=True,
    )


def fill_missing_dates(
    db_results: list[Any], date_range: list[date], count_field: str
) -> list[dict]:
    """Fills missing dates in a list of DB results with a count of 0."""
    data_map = {r.date.date(): getattr(r, count_field) for r in db_results}
    return [{"date": d.isoformat(), "count": data_map.get(d, 0)} for d in date_range]


def fill_missing_acct_dates(
    db_results: list[Any], date_range: list[date]
) -> list[dict]:
    """Fills missing accounting dates in a list of DB results with counts of 0."""
    data_map = {r.date.date(): (r.start_count, r.stop_count) for r in db_results}
    return [
        {
            "date": d.isoformat(),
            "start_count": data_map.get(d, (0, 0))[0],
            "stop_count": data_map.get(d, (0, 0))[1],
        }
        for d in date_range
    ]


def get_distinct_node_names(session: Session) -> list[str]:
    """Return sorted list of all known node_names across the three stats tables."""

    auth_nodes = session.exec(
        select(AuthenticationStatistics.node_name).distinct()
    ).all()
    authz_nodes = session.exec(
        select(AuthorizationStatistics.node_name).distinct()
    ).all()
    acct_nodes = session.exec(select(AccountingStatistics.node_name).distinct()).all()
    all_nodes = set(auth_nodes) | set(authz_nodes) | set(acct_nodes)
    return sorted(all_nodes)


def _get_range_statistics(
    session: Session,
    start_date: date,
    end_date: date,
    key_prefix: str,
    node_name: str | None = None,
) -> dict[str, Any]:
    """
    Retrieve and format statistics for a given date range.
    DB is queried up to yesterday; today's data injected from live log files.
    """
    today = datetime.now(timezone.utc).date()
    include_today = end_date >= today
    # DB never has today's data (cron runs at 1am for yesterday), so cap at yesterday
    db_end = min(end_date, today - timedelta(days=1))

    start_dt = datetime.combine(start_date, time_.min).replace(tzinfo=timezone.utc)
    db_end_dt = datetime.combine(db_end, time_.max).replace(tzinfo=timezone.utc)

    auth_daily_stmt = (
        select(
            AuthenticationStatistics.log_date.label("date"),
            func.sum(AuthenticationStatistics.success_count).label(
                "auth_success_count"
            ),
            func.sum(AuthenticationStatistics.fail_count).label("auth_fail_count"),
        )
        .where(AuthenticationStatistics.log_date.between(start_dt, db_end_dt))
        .group_by(AuthenticationStatistics.log_date)
        .order_by(AuthenticationStatistics.log_date)
    )

    authz_daily_stmt = (
        select(
            AuthorizationStatistics.log_date.label("date"),
            func.sum(AuthorizationStatistics.permit_count).label("authz_permit_count"),
            func.sum(AuthorizationStatistics.deny_count).label("authz_deny_count"),
        )
        .where(AuthorizationStatistics.log_date.between(start_dt, db_end_dt))
        .group_by(AuthorizationStatistics.log_date)
        .order_by(AuthorizationStatistics.log_date)
    )

    acct_daily_stmt = (
        select(
            AccountingStatistics.log_date.label("date"),
            func.sum(AccountingStatistics.start_count).label("acct_start_count"),
            func.sum(AccountingStatistics.stop_count).label("acct_stop_count"),
        )
        .where(AccountingStatistics.log_date.between(start_dt, db_end_dt))
        .group_by(AccountingStatistics.log_date)
        .order_by(AccountingStatistics.log_date)
    )

    if node_name:
        auth_daily_stmt = auth_daily_stmt.where(
            AuthenticationStatistics.node_name == node_name
        )
        authz_daily_stmt = authz_daily_stmt.where(
            AuthorizationStatistics.node_name == node_name
        )
        acct_daily_stmt = acct_daily_stmt.where(
            AccountingStatistics.node_name == node_name
        )

    auth_daily_results = session.exec(auth_daily_stmt).all()
    authz_daily_results = session.exec(authz_daily_stmt).all()
    acct_daily_results = session.exec(acct_daily_stmt).all()

    num_days = (end_date - start_date).days + 1
    all_dates = [(start_date + timedelta(days=i)) for i in range(num_days)]

    result = {
        f"{key_prefix}_authentication_success": fill_missing_dates(
            auth_daily_results, all_dates, "auth_success_count"
        ),
        f"{key_prefix}_authentication_fail": fill_missing_dates(
            auth_daily_results, all_dates, "auth_fail_count"
        ),
        f"{key_prefix}_authorization_permit": fill_missing_dates(
            authz_daily_results, all_dates, "authz_permit_count"
        ),
        f"{key_prefix}_authorization_deny": fill_missing_dates(
            authz_daily_results, all_dates, "authz_deny_count"
        ),
        f"{key_prefix}_accounting_start": fill_missing_dates(
            acct_daily_results, all_dates, "acct_start_count"
        ),
        f"{key_prefix}_accounting_stop": fill_missing_dates(
            acct_daily_results, all_dates, "acct_stop_count"
        ),
    }

    # Inject today's live data
    inject_live = include_today

    if inject_live:
        today_iso = today.isoformat()
        today_stats = process_today_authentication_statistics(
            session, node_name=node_name
        )
        _set_trend_today(
            result[f"{key_prefix}_authentication_success"],
            today_iso,
            today_stats.get("today_successful_logins", 0),
        )
        _set_trend_today(
            result[f"{key_prefix}_authentication_fail"],
            today_iso,
            today_stats.get("today_failed_logins", 0),
        )
        permit, deny = get_today_authz_counts(session, node_name=node_name)
        _set_trend_today(
            result[f"{key_prefix}_authorization_permit"], today_iso, permit
        )
        _set_trend_today(result[f"{key_prefix}_authorization_deny"], today_iso, deny)
        start_c, stop_c = get_today_acct_counts(session, node_name=node_name)
        _set_trend_today(result[f"{key_prefix}_accounting_start"], today_iso, start_c)
        _set_trend_today(result[f"{key_prefix}_accounting_stop"], today_iso, stop_c)

    return result


def get_last_7_days_statistics(
    *,
    session: Session,
    node_name: str | None = None,
) -> dict[str, Any]:
    """
    Retrieves statistics for the last 7 days from the database.
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=6)
    return _get_range_statistics(
        session, start_date, end_date, "last_7_days", node_name
    )


def get_date_range_statistics(
    *,
    session: Session,
    start_date: datetime,
    end_date: datetime,
    node_name: str | None = None,
) -> dict[str, Any]:
    """
    Retrieves statistics for the range of days from the database.
    """
    return _get_range_statistics(
        session, start_date.date(), end_date.date(), "last_range_days", node_name
    )


def process_authentication_statistics(
    session: Session,
    start_date: datetime,
    end_date: datetime,
    skip: int = 0,
    limit: int = 5,
    node_name: str | None = None,
) -> dict[str, Any]:
    """
    Processes authentication log files to extract statistics and save them to the database.
    """

    failed_count_stmt = (
        select(
            AuthenticationStatistics.username,
            func.sum(AuthenticationStatistics.fail_count).label("fail_count"),
        )
        .where(AuthenticationStatistics.fail_count > 0)
        .group_by(AuthenticationStatistics.username)
        .having(func.sum(AuthenticationStatistics.fail_count) > 0)
        .order_by(func.sum(AuthenticationStatistics.fail_count).desc())
    )
    success_count_stmt = (
        select(
            AuthenticationStatistics.username,
            func.sum(AuthenticationStatistics.success_count).label("success_count"),
        )
        .where(AuthenticationStatistics.success_count > 0)
        .group_by(AuthenticationStatistics.username)
        .having(func.sum(AuthenticationStatistics.success_count) > 0)
        .order_by(func.sum(AuthenticationStatistics.success_count).desc())
    )
    success_count_by_ip_stmt = (
        select(
            AuthenticationStatistics.user_source_ip,
            func.sum(AuthenticationStatistics.success_count).label("success_count"),
        )
        .where(AuthenticationStatistics.success_count > 0)
        .group_by(AuthenticationStatistics.user_source_ip)
        .having(func.sum(AuthenticationStatistics.success_count) > 0)
        .order_by(func.sum(AuthenticationStatistics.success_count).desc())
    )
    success_count_by_nas_ip_stmt = (
        select(
            AuthenticationStatistics.nas_ip,
            func.sum(AuthenticationStatistics.success_count).label("success_count"),
        )
        .where(AuthenticationStatistics.success_count > 0)
        .group_by(AuthenticationStatistics.nas_ip)
        .having(func.sum(AuthenticationStatistics.success_count) > 0)
        .order_by(func.sum(AuthenticationStatistics.success_count).desc())
    )
    # DB query capped at yesterday; today injected from live log below
    today = datetime.now(timezone.utc).date()
    include_today = end_date.date() >= today
    db_end = min(end_date.date(), today - timedelta(days=1))
    start_dt = datetime.combine(start_date.date(), time_.min).replace(
        tzinfo=timezone.utc
    )
    db_end_dt = datetime.combine(db_end, time_.max).replace(tzinfo=timezone.utc)

    failed_count_stmt = failed_count_stmt.where(
        AuthenticationStatistics.log_date.between(start_dt, db_end_dt)
    )
    success_count_stmt = success_count_stmt.where(
        AuthenticationStatistics.log_date.between(start_dt, db_end_dt)
    )
    success_count_by_ip_stmt = success_count_by_ip_stmt.where(
        AuthenticationStatistics.log_date.between(start_dt, db_end_dt)
    )
    success_count_by_nas_ip_stmt = success_count_by_nas_ip_stmt.where(
        AuthenticationStatistics.log_date.between(start_dt, db_end_dt)
    )

    if node_name:
        failed_count_stmt = failed_count_stmt.where(
            AuthenticationStatistics.node_name == node_name
        )
        success_count_stmt = success_count_stmt.where(
            AuthenticationStatistics.node_name == node_name
        )
        success_count_by_ip_stmt = success_count_by_ip_stmt.where(
            AuthenticationStatistics.node_name == node_name
        )
        success_count_by_nas_ip_stmt = success_count_by_nas_ip_stmt.where(
            AuthenticationStatistics.node_name == node_name
        )

    failed_count_results = session.exec(failed_count_stmt).all()
    authentication_failed_count_by_user = [
        {"username": r.username, "fail_count": r.fail_count}
        for r in failed_count_results
    ]
    success_count_results = session.exec(success_count_stmt).all()
    authentication_success_count_by_user = [
        {"username": r.username, "success_count": r.success_count}
        for r in success_count_results
    ]
    success_count_by_ip_results = session.exec(success_count_by_ip_stmt).all()
    authentication_success_count_by_user_source_ip = [
        {"user_source_ip": r.user_source_ip, "success_count": r.success_count}
        for r in success_count_by_ip_results
    ]
    success_count_by_nas_ip_results = session.exec(success_count_by_nas_ip_stmt).all()
    authentication_success_count_by_nas_ip = [
        {"nas_ip": r.nas_ip, "success_count": r.success_count}
        for r in success_count_by_nas_ip_results
    ]

    if include_today:
        ts = process_today_authentication_statistics(session, node_name=node_name)
        authentication_success_count_by_user = _merge_today_top(
            authentication_success_count_by_user,
            ts.get("today_authentication_success_count_by_user", []),
            "username",
            "success_count",
        )
        authentication_failed_count_by_user = _merge_today_top(
            authentication_failed_count_by_user,
            ts.get("today_authentication_failed_count_by_user", []),
            "username",
            "fail_count",
        )
        authentication_success_count_by_user_source_ip = _merge_today_top(
            authentication_success_count_by_user_source_ip,
            ts.get("today_authentication_success_count_by_user_source_ip", []),
            "user_source_ip",
            "success_count",
        )
        authentication_success_count_by_nas_ip = _merge_today_top(
            authentication_success_count_by_nas_ip,
            ts.get("today_authentication_success_count_by_nas_ip", []),
            "nas_ip",
            "success_count",
        )

    return {
        "authentication_failed_count_by_user": authentication_failed_count_by_user[
            skip : skip + limit
        ],
        "authentication_success_count_by_user": authentication_success_count_by_user[
            skip : skip + limit
        ],
        "authentication_success_count_by_user_source_ip": authentication_success_count_by_user_source_ip[
            skip : skip + limit
        ],
        "authentication_success_count_by_nas_ip": authentication_success_count_by_nas_ip[
            skip : skip + limit
        ],
    }


def process_authorization_statistics(
    session: Session,
    start_date: datetime,
    end_date: datetime,
    skip: int = 0,
    limit: int = 5,
    node_name: str | None = None,
) -> dict[str, Any]:
    """
    Processes authorization log files to extract statistics and save them to the database.
    """

    authz_deny_count_stmt = (
        select(
            AuthorizationStatistics.username,
            func.sum(AuthorizationStatistics.deny_count).label("deny_count"),
        )
        .where(AuthorizationStatistics.deny_count > 0)
        .group_by(AuthorizationStatistics.username)
        .having(func.sum(AuthorizationStatistics.deny_count) > 0)
        .order_by(func.sum(AuthorizationStatistics.deny_count).desc())
    )

    authz_start_dt = datetime.combine(start_date.date(), time_.min).replace(
        tzinfo=timezone.utc
    )
    authz_end_dt = datetime.combine(end_date.date(), time_.max).replace(
        tzinfo=timezone.utc
    )
    authz_deny_count_stmt = authz_deny_count_stmt.where(
        AuthorizationStatistics.log_date.between(authz_start_dt, authz_end_dt)
    )

    if node_name:
        authz_deny_count_stmt = authz_deny_count_stmt.where(
            AuthorizationStatistics.node_name == node_name
        )

    authz_deny_count_results = session.exec(authz_deny_count_stmt).all()
    # Convert the Row objects to a list of dicts
    authorization_deny_count_by_user = [
        {"username": r.username, "deny_count": r.deny_count}
        for r in authz_deny_count_results
    ]
    return {
        "authorization_deny_count_by_user": authorization_deny_count_by_user[
            skip : skip + limit
        ],
    }


def _get_node_today_authz_counts_from_db(
    session: Session, node_name: str, today_dt: datetime
) -> tuple[int, int]:
    stmt = select(
        func.sum(AuthorizationStatistics.permit_count).label("permit"),
        func.sum(AuthorizationStatistics.deny_count).label("deny"),
    ).where(
        AuthorizationStatistics.log_date == today_dt,
        AuthorizationStatistics.node_name == node_name,
    )
    res = session.exec(stmt).first()
    if res and (res.permit is not None or res.deny is not None):
        return res.permit or 0, res.deny or 0
    return 0, 0


def _get_node_today_acct_counts_from_db(
    session: Session, node_name: str, today_dt: datetime
) -> tuple[int, int]:
    stmt = select(
        func.sum(AccountingStatistics.start_count).label("start"),
        func.sum(AccountingStatistics.stop_count).label("stop"),
    ).where(
        AccountingStatistics.log_date == today_dt,
        AccountingStatistics.node_name == node_name,
    )
    res = session.exec(stmt).first()
    if res and (res.start is not None or res.stop is not None):
        return res.start or 0, res.stop or 0
    return 0, 0


def get_today_authz_counts(
    session: Session, node_name: str | None = None
) -> tuple[int, int]:
    """Get live today's authorization permit/deny counts for the selected node or all nodes."""
    global _today_authz_cache
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    today_dt = datetime.combine(today.date(), time_.min).replace(tzinfo=timezone.utc)
    now_ts = _time.monotonic()

    cache_key = node_name or "all"
    if (
        _today_authz_cache.get(cache_key, {}).get("date") == today_str
        and now_ts - _today_authz_cache.get(cache_key, {}).get("ts", 0.0) < 60
    ):
        return _today_authz_cache[cache_key]["permit"], _today_authz_cache[cache_key][
            "deny"
        ]

    permit = deny = 0

    if node_name:
        if node_name == settings.NODE_NAME:
            permit, deny = _today_authz_counts()
        else:
            fetched = False
            peer_urls = get_peer_urls()
            for url in peer_urls:
                try:
                    endpoint = f"{url.rstrip('/')}/api/v1/sync/internal/collect-stats"
                    if not settings.INTERNAL_SYNC_TOKEN:
                        continue
                    with httpx.Client(timeout=3.0) as client:
                        resp = client.post(
                            endpoint,
                            params={"date": today_str},
                            headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("node_name") == node_name:
                                authz = data.get("authorization", [])
                                permit = sum(r.get("permit_count", 0) for r in authz)
                                deny = sum(r.get("deny_count", 0) for r in authz)
                                fetched = True
                                break
                except Exception as e:
                    logger.warning(
                        "Failed to fetch live authz stats from peer %s for node %s: %s",
                        url,
                        node_name,
                        e,
                    )
            if not fetched:
                permit, deny = _get_node_today_authz_counts_from_db(
                    session, node_name, today_dt
                )
    else:
        # All nodes
        local_p, local_d = _today_authz_counts()
        permit += local_p
        deny += local_d

        peer_urls = get_peer_urls()
        fetched_peer_nodes = set()
        for url in peer_urls:
            try:
                endpoint = f"{url.rstrip('/')}/api/v1/sync/internal/collect-stats"
                if not settings.INTERNAL_SYNC_TOKEN:
                    continue
                with httpx.Client(timeout=3.0) as client:
                    resp = client.post(
                        endpoint,
                        params={"date": today_str},
                        headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        peer_node_name = data.get("node_name")
                        if peer_node_name:
                            authz = data.get("authorization", [])
                            permit += sum(r.get("permit_count", 0) for r in authz)
                            deny += sum(r.get("deny_count", 0) for r in authz)
                            fetched_peer_nodes.add(peer_node_name)
            except Exception as e:
                logger.warning(
                    "Failed to fetch live authz stats from peer %s: %s", url, e
                )

        all_known_nodes = get_distinct_node_names(session)
        for kn in all_known_nodes:
            if kn != settings.NODE_NAME and kn not in fetched_peer_nodes:
                p, d = _get_node_today_authz_counts_from_db(session, kn, today_dt)
                permit += p
                deny += d

    _today_authz_cache[cache_key] = {
        "date": today_str,
        "permit": permit,
        "deny": deny,
        "ts": now_ts,
    }
    return permit, deny


def get_today_acct_counts(
    session: Session, node_name: str | None = None
) -> tuple[int, int]:
    """Get live today's accounting start/stop counts for the selected node or all nodes."""
    global _today_acct_cache
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    today_dt = datetime.combine(today.date(), time_.min).replace(tzinfo=timezone.utc)
    now_ts = _time.monotonic()

    cache_key = node_name or "all"
    if (
        _today_acct_cache.get(cache_key, {}).get("date") == today_str
        and now_ts - _today_acct_cache.get(cache_key, {}).get("ts", 0.0) < 60
    ):
        return _today_acct_cache[cache_key]["start"], _today_acct_cache[cache_key][
            "stop"
        ]

    start = stop = 0

    if node_name:
        if node_name == settings.NODE_NAME:
            start, stop = _today_acct_counts()
        else:
            fetched = False
            peer_urls = get_peer_urls()
            for url in peer_urls:
                try:
                    endpoint = f"{url.rstrip('/')}/api/v1/sync/internal/collect-stats"
                    if not settings.INTERNAL_SYNC_TOKEN:
                        continue
                    with httpx.Client(timeout=3.0) as client:
                        resp = client.post(
                            endpoint,
                            params={"date": today_str},
                            headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("node_name") == node_name:
                                acct = data.get("accounting", [])
                                start = sum(r.get("start_count", 0) for r in acct)
                                stop = sum(r.get("stop_count", 0) for r in acct)
                                fetched = True
                                break
                except Exception as e:
                    logger.warning(
                        "Failed to fetch live acct stats from peer %s for node %s: %s",
                        url,
                        node_name,
                        e,
                    )
            if not fetched:
                start, stop = _get_node_today_acct_counts_from_db(
                    session, node_name, today_dt
                )
    else:
        # All nodes
        local_s, local_st = _today_acct_counts()
        start += local_s
        stop += local_st

        peer_urls = get_peer_urls()
        fetched_peer_nodes = set()
        for url in peer_urls:
            try:
                endpoint = f"{url.rstrip('/')}/api/v1/sync/internal/collect-stats"
                if not settings.INTERNAL_SYNC_TOKEN:
                    continue
                with httpx.Client(timeout=3.0) as client:
                    resp = client.post(
                        endpoint,
                        params={"date": today_str},
                        headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        peer_node_name = data.get("node_name")
                        if peer_node_name:
                            acct = data.get("accounting", [])
                            start += sum(r.get("start_count", 0) for r in acct)
                            stop += sum(r.get("stop_count", 0) for r in acct)
                            fetched_peer_nodes.add(peer_node_name)
            except Exception as e:
                logger.warning(
                    "Failed to fetch live acct stats from peer %s: %s", url, e
                )

        all_known_nodes = get_distinct_node_names(session)
        for kn in all_known_nodes:
            if kn != settings.NODE_NAME and kn not in fetched_peer_nodes:
                s, st = _get_node_today_acct_counts_from_db(session, kn, today_dt)
                start += s
                stop += st

    _today_acct_cache[cache_key] = {
        "date": today_str,
        "start": start,
        "stop": stop,
        "ts": now_ts,
    }
    return start, stop


def process_today_authentication_statistics(
    session: Session,
    node_name: str | None = None,
) -> dict[str, Any]:
    """
    Parses today's authentication log file live (for local node) or fetches from peer,
    falling back to database if needed, and returns aggregated stats.
    Result cached for 60 s to avoid repeated queries/file scans on dashboard polling.
    """
    global _today_cache
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    today_dt = datetime.combine(today.date(), time_.min).replace(tzinfo=timezone.utc)
    now_ts = _time.monotonic()

    cache_key = node_name or "all"
    if (
        _today_cache.get(cache_key, {}).get("date") == today_str
        and now_ts - _today_cache.get(cache_key, {}).get("ts", 0.0) < 60
    ):
        return _today_cache[cache_key]["data"]

    # Gather raw details
    details = []

    if node_name:
        if node_name == settings.NODE_NAME:
            details = parse_local_today_authentication_details()
        else:
            # Try peer URL
            fetched_details = None
            peer_urls = get_peer_urls()
            for url in peer_urls:
                try:
                    endpoint = f"{url.rstrip('/')}/api/v1/sync/internal/collect-stats"
                    if not settings.INTERNAL_SYNC_TOKEN:
                        continue
                    with httpx.Client(timeout=3.0) as client:
                        resp = client.post(
                            endpoint,
                            params={"date": today_str},
                            headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            if data.get("node_name") == node_name:
                                fetched_details = data.get("authentication", [])
                                break
                except Exception as e:
                    logger.warning(
                        "Failed to fetch live stats from peer %s for node %s: %s",
                        url,
                        node_name,
                        e,
                    )

            if fetched_details is not None:
                details = fetched_details
            else:
                details = get_node_today_stats_from_db(session, node_name, today_dt)
    else:
        # All nodes
        # 1. Local live stats
        details.extend(parse_local_today_authentication_details())

        # 2. Peer live stats
        peer_urls = get_peer_urls()
        fetched_peer_nodes = set()
        for url in peer_urls:
            try:
                endpoint = f"{url.rstrip('/')}/api/v1/sync/internal/collect-stats"
                if not settings.INTERNAL_SYNC_TOKEN:
                    continue
                with httpx.Client(timeout=3.0) as client:
                    resp = client.post(
                        endpoint,
                        params={"date": today_str},
                        headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN},
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        peer_node_name = data.get("node_name")
                        if peer_node_name:
                            details.extend(data.get("authentication", []))
                            fetched_peer_nodes.add(peer_node_name)
            except Exception as e:
                logger.warning("Failed to fetch live stats from peer %s: %s", url, e)

        # 3. Fallback for offline peers
        all_known_nodes = get_distinct_node_names(session)
        for kn in all_known_nodes:
            if kn != settings.NODE_NAME and kn not in fetched_peer_nodes:
                details.extend(get_node_today_stats_from_db(session, kn, today_dt))

    result = aggregate_today_auth_details(details, today_str)
    _today_cache[cache_key] = {"date": today_str, "data": result, "ts": now_ts}
    return result
