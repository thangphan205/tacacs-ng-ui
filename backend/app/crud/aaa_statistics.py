import logging
import os
import time as _time
from collections import Counter, defaultdict
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta, timezone
from datetime import time as time_
from typing import Any

import httpx
from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import settings
from app.crud.stats_exclusions import filter_rows, not_excluded_clause
from app.models import (
    AccountingStatistics,
    AuthenticationStatistics,
    AuthorizationStatistics,
)
from scripts._log_stats_base import (
    AUTH_LOG_REGEX,
    parse_accounting_logs,
    parse_authorization_logs,
)

logger = logging.getLogger(__name__)

_LIVE_CACHE_TTL = 60

# Today's raw per-(username, nas_ip, user_source_ip) rows, cached *unfiltered*
# and keyed by (log kind, node_name or "all"). Exclusions are applied after the
# cache, so a change to the exclusion list is visible on the next request in
# every uvicorn worker instead of after the TTL in whichever worker served it.
_today_rows_cache: dict[tuple[str, str], dict[str, Any]] = {}

# (table, first count field, second count field) per log kind.
_KIND_SPEC: dict[str, tuple[Any, str, str]] = {
    "authentication": (AuthenticationStatistics, "success_count", "fail_count"),
    "authorization": (AuthorizationStatistics, "permit_count", "deny_count"),
    "accounting": (AccountingStatistics, "start_count", "stop_count"),
}


def _counters_to_rows(
    c1: Counter, c2: Counter, k1: str, k2: str
) -> list[dict[str, Any]]:
    keys = set(c1) | set(c2)
    return [
        {
            "username": u,
            "nas_ip": n,
            "user_source_ip": c,
            k1: c1.get((u, n, c), 0),
            k2: c2.get((u, n, c), 0),
        }
        for u, n, c in sorted(keys, key=lambda k: tuple(str(x) for x in k))
    ]


def _local_today_authz_rows() -> list[dict[str, Any]]:
    """Today's authorization rows from the local log, parsed like the nightly job."""
    today = datetime.now(timezone.utc).date()
    permit, deny = parse_authorization_logs(today, settings.TACACS_LOG_DIRECTORY)
    return _counters_to_rows(permit, deny, "permit_count", "deny_count")


def _local_today_acct_rows() -> list[dict[str, Any]]:
    """Today's accounting rows from the local log, parsed like the nightly job."""
    today = datetime.now(timezone.utc).date()
    start, stop = parse_accounting_logs(today, settings.TACACS_LOG_DIRECTORY)
    return _counters_to_rows(start, stop, "start_count", "stop_count")


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


def _db_today_rows(
    session: Session, kind: str, node_name: str, today_dt: datetime
) -> list[dict[str, Any]]:
    """Fallback: today's rows for a node from the database (e.g. an offline peer)."""
    table, k1, k2 = _KIND_SPEC[kind]
    db_rows = session.exec(
        select(table).where(table.log_date == today_dt, table.node_name == node_name)
    ).all()
    return [
        {
            "username": r.username,
            "nas_ip": r.nas_ip,
            "user_source_ip": r.user_source_ip,
            k1: getattr(r, k1),
            k2: getattr(r, k2),
        }
        for r in db_rows
    ]


def _peer_payloads(today_str: str) -> Iterator[dict[str, Any]]:
    """Yield each reachable peer's collect-stats payload for `today_str`."""
    if not settings.INTERNAL_SYNC_TOKEN:
        return
    for url in get_peer_urls():
        endpoint = f"{url.rstrip('/')}/api/v1/sync/internal/collect-stats"
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(
                    endpoint,
                    params={"date": today_str},
                    headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN},
                )
        except Exception as e:
            logger.warning("Failed to fetch live stats from peer %s: %s", url, e)
            continue
        if resp.status_code == 200:
            yield resp.json()


# Lambdas so the module-level functions are looked up at call time (patchable).
_LOCAL_PARSERS: dict[str, Callable[[], list[dict[str, Any]]]] = {
    "authentication": lambda: parse_local_today_authentication_details(),
    "authorization": lambda: _local_today_authz_rows(),
    "accounting": lambda: _local_today_acct_rows(),
}


def _today_rows(
    session: Session, kind: str, node_name: str | None = None
) -> list[dict[str, Any]]:
    """
    Today's unfiltered per-user rows of one log kind: parsed live for the local
    node, fetched live from peers, falling back to the database for peers that
    cannot be reached. Cached 60 s to absorb dashboard polling.
    """
    today = datetime.now(timezone.utc)
    today_str = today.strftime("%Y-%m-%d")
    today_dt = datetime.combine(today.date(), time_.min).replace(tzinfo=timezone.utc)
    now_ts = _time.monotonic()

    cache_key = (kind, node_name or "all")
    cached = _today_rows_cache.get(cache_key)
    if (
        cached
        and cached["date"] == today_str
        and now_ts - cached["ts"] < _LIVE_CACHE_TTL
    ):
        return cached["rows"]

    rows: list[dict[str, Any]] = []
    if node_name:
        if node_name == settings.NODE_NAME:
            rows = _LOCAL_PARSERS[kind]()
        else:
            fetched: list[dict[str, Any]] | None = None
            for data in _peer_payloads(today_str):
                if data.get("node_name") == node_name:
                    fetched = data.get(kind, [])
                    break
            rows = (
                fetched
                if fetched is not None
                else _db_today_rows(session, kind, node_name, today_dt)
            )
    else:
        rows.extend(_LOCAL_PARSERS[kind]())
        fetched_peer_nodes: set[str] = set()
        for data in _peer_payloads(today_str):
            peer_node_name = data.get("node_name")
            if peer_node_name:
                rows.extend(data.get(kind, []))
                fetched_peer_nodes.add(peer_node_name)
        for kn in get_distinct_node_names(session):
            if kn != settings.NODE_NAME and kn not in fetched_peer_nodes:
                rows.extend(_db_today_rows(session, kind, kn, today_dt))

    _today_rows_cache[cache_key] = {"date": today_str, "rows": rows, "ts": now_ts}
    return rows


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
    excluded: list[str] | None = None,
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

    excluded = excluded or []
    auth_excl = not_excluded_clause(AuthenticationStatistics.username, excluded)
    if auth_excl is not None:
        auth_daily_stmt = auth_daily_stmt.where(auth_excl)
    authz_excl = not_excluded_clause(AuthorizationStatistics.username, excluded)
    if authz_excl is not None:
        authz_daily_stmt = authz_daily_stmt.where(authz_excl)
    acct_excl = not_excluded_clause(AccountingStatistics.username, excluded)
    if acct_excl is not None:
        acct_daily_stmt = acct_daily_stmt.where(acct_excl)

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
            session, node_name=node_name, excluded=excluded
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
        permit, deny = get_today_authz_counts(
            session, node_name=node_name, excluded=excluded
        )
        _set_trend_today(
            result[f"{key_prefix}_authorization_permit"], today_iso, permit
        )
        _set_trend_today(result[f"{key_prefix}_authorization_deny"], today_iso, deny)
        start_c, stop_c = get_today_acct_counts(
            session, node_name=node_name, excluded=excluded
        )
        _set_trend_today(result[f"{key_prefix}_accounting_start"], today_iso, start_c)
        _set_trend_today(result[f"{key_prefix}_accounting_stop"], today_iso, stop_c)

    return result


def get_last_7_days_statistics(
    *,
    session: Session,
    node_name: str | None = None,
    excluded: list[str] | None = None,
) -> dict[str, Any]:
    """
    Retrieves statistics for the last 7 days from the database.
    """
    end_date = datetime.now(timezone.utc).date()
    start_date = end_date - timedelta(days=6)
    return _get_range_statistics(
        session, start_date, end_date, "last_7_days", node_name, excluded
    )


def get_date_range_statistics(
    *,
    session: Session,
    start_date: datetime,
    end_date: datetime,
    node_name: str | None = None,
    excluded: list[str] | None = None,
) -> dict[str, Any]:
    """
    Retrieves statistics for the range of days from the database.
    """
    return _get_range_statistics(
        session,
        start_date.date(),
        end_date.date(),
        "last_range_days",
        node_name,
        excluded,
    )


def process_authentication_statistics(
    session: Session,
    start_date: datetime,
    end_date: datetime,
    skip: int = 0,
    limit: int = 5,
    node_name: str | None = None,
    excluded: list[str] | None = None,
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

    auth_excl = not_excluded_clause(AuthenticationStatistics.username, excluded or [])
    if auth_excl is not None:
        failed_count_stmt = failed_count_stmt.where(auth_excl)
        success_count_stmt = success_count_stmt.where(auth_excl)
        success_count_by_ip_stmt = success_count_by_ip_stmt.where(auth_excl)
        success_count_by_nas_ip_stmt = success_count_by_nas_ip_stmt.where(auth_excl)

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
        ts = process_today_authentication_statistics(
            session, node_name=node_name, excluded=excluded
        )
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
    excluded: list[str] | None = None,
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

    authz_excl = not_excluded_clause(AuthorizationStatistics.username, excluded or [])
    if authz_excl is not None:
        authz_deny_count_stmt = authz_deny_count_stmt.where(authz_excl)

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


def get_today_authz_counts(
    session: Session,
    node_name: str | None = None,
    excluded: list[str] | None = None,
) -> tuple[int, int]:
    """Today's authorization (permit, deny) for one node or all nodes."""
    rows = filter_rows(_today_rows(session, "authorization", node_name), excluded or [])
    return (
        sum(r.get("permit_count", 0) for r in rows),
        sum(r.get("deny_count", 0) for r in rows),
    )


def get_today_acct_counts(
    session: Session,
    node_name: str | None = None,
    excluded: list[str] | None = None,
) -> tuple[int, int]:
    """Today's accounting (start, stop) for one node or all nodes."""
    rows = filter_rows(_today_rows(session, "accounting", node_name), excluded or [])
    return (
        sum(r.get("start_count", 0) for r in rows),
        sum(r.get("stop_count", 0) for r in rows),
    )


def process_today_authentication_statistics(
    session: Session,
    node_name: str | None = None,
    excluded: list[str] | None = None,
) -> dict[str, Any]:
    """Today's aggregated authentication statistics for one node or all nodes."""
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    rows = filter_rows(
        _today_rows(session, "authentication", node_name), excluded or []
    )
    return aggregate_today_auth_details(rows, today_str)
