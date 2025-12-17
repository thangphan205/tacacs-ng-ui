import re
import os
from datetime import datetime, timedelta, date
from collections import Counter, defaultdict
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, select, col
from app.models import (
    AuthenticationStatistics,
    AuthorizationStatistics,
    AccountingStatistics,
)
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)
TACACS_LOG_DIRECTORY = "/var/log/tacacs/"


def fill_missing_dates(data, date_range):
    data_map = {item["date"]: item["count"] for item in data}
    return [
        {"date": d.isoformat(), "count": data_map.get(d.isoformat(), 0)}
        for d in date_range
    ]


def fill_missing_acct_dates(data, date_range):
    data_map = {
        item["date"]: (item["start_count"], item["stop_count"]) for item in data
    }
    return [
        {
            "date": d.isoformat(),
            "start_count": data_map.get(d.isoformat(), (0, 0))[0],
            "stop_count": data_map.get(d.isoformat(), (0, 0))[1],
        }
        for d in date_range
    ]


def format_daily_data(results):
    return [{"date": r.date.isoformat(), "count": r.count} for r in results]


def format_acct_daily_data(results):
    return [
        {
            "date": r.date.isoformat(),
            "start_count": r.start_count,
            "stop_count": r.stop_count,
        }
        for r in results
    ]


def _get_range_statistics(
    session: Session, start_date: date, end_date: date, key_prefix: str
) -> dict[str, Any]:
    """
    A helper function to retrieve and format statistics for a given date range.
    """
    auth_success_daily_stmt = (
        select(
            AuthenticationStatistics.log_date.label("date"),
            func.sum(AuthenticationStatistics.success_count).label("count"),
        )
        .where(AuthenticationStatistics.log_date.between(start_date, end_date))
        .group_by(AuthenticationStatistics.log_date)
        .order_by(AuthenticationStatistics.log_date)
    )
    auth_fail_daily_stmt = (
        select(
            AuthenticationStatistics.log_date.label("date"),
            func.sum(AuthenticationStatistics.fail_count).label("count"),
        )
        .where(AuthenticationStatistics.log_date.between(start_date, end_date))
        .group_by(AuthenticationStatistics.log_date)
        .order_by(AuthenticationStatistics.log_date)
    )
    authz_permit_daily_stmt = (
        select(
            AuthorizationStatistics.log_date.label("date"),
            func.sum(AuthorizationStatistics.permit_count).label("count"),
        )
        .where(AuthorizationStatistics.log_date.between(start_date, end_date))
        .group_by(AuthorizationStatistics.log_date)
        .order_by(AuthorizationStatistics.log_date)
    )
    authz_deny_daily_stmt = (
        select(
            AuthorizationStatistics.log_date.label("date"),
            func.sum(AuthorizationStatistics.deny_count).label("count"),
        )
        .where(AuthorizationStatistics.log_date.between(start_date, end_date))
        .group_by(AuthorizationStatistics.log_date)
        .order_by(AuthorizationStatistics.log_date)
    )
    acct_daily_stmt = (
        select(
            AccountingStatistics.log_date.label("date"),
            func.sum(AccountingStatistics.start_count).label("start_count"),
            func.sum(AccountingStatistics.stop_count).label("stop_count"),
        )
        .where(AccountingStatistics.log_date.between(start_date, end_date))
        .group_by(AccountingStatistics.log_date)
        .order_by(AccountingStatistics.log_date)
    )
    # Execute daily count queries
    auth_success_daily_results = session.exec(auth_success_daily_stmt).all()
    auth_fail_daily_results = session.exec(auth_fail_daily_stmt).all()
    authz_pass_daily_results = session.exec(authz_permit_daily_stmt).all()
    authz_deny_daily_results = session.exec(authz_deny_daily_stmt).all()
    acct_daily_results = session.exec(acct_daily_stmt).all()

    # Generate date range to ensure all days are present in the final output
    num_days = (end_date - start_date).days + 1
    all_dates = [(start_date + timedelta(days=i)) for i in range(num_days)]

    return {
        f"{key_prefix}_authentication_success": fill_missing_dates(
            format_daily_data(auth_success_daily_results), all_dates
        ),
        f"{key_prefix}_authentication_fail": fill_missing_dates(
            format_daily_data(auth_fail_daily_results), all_dates
        ),
        f"{key_prefix}_authorization_pass": fill_missing_dates(
            format_daily_data(authz_pass_daily_results), all_dates
        ),
        f"{key_prefix}_authorization_deny": fill_missing_dates(
            format_daily_data(authz_deny_daily_results), all_dates
        ),
        f"{key_prefix}_accounting": fill_missing_acct_dates(
            format_acct_daily_data(acct_daily_results), all_dates
        ),
    }


def get_last_7_days_statistics(
    *,
    session: Session,
) -> dict[str, Any]:
    """
    Retrieves statistics for the last 7 days from the database.
    """
    end_date = datetime.utcnow().date() - timedelta(days=1)
    start_date = end_date - timedelta(days=6)
    return _get_range_statistics(session, start_date, end_date, "last_7_days")


def get_date_range_statistics(
    *,
    session: Session,
    start_date: datetime,
    end_date: datetime,
) -> dict[str, Any]:
    """
    Retrieves statistics for the range of days from the database.
    """
    return _get_range_statistics(
        session, start_date.date(), end_date.date(), "last_range_days"
    )


def process_authentication_statistics(
    session: Session,
    start_date: datetime,
    end_date: datetime,
    skip: int = 0,
    limit: int = 5,
) -> None:
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
    # Apply the date range filter to all queries

    failed_count_stmt = failed_count_stmt.where(
        AuthenticationStatistics.log_date.between(start_date.date(), end_date.date())
    )
    success_count_stmt = success_count_stmt.where(
        AuthenticationStatistics.log_date.between(start_date.date(), end_date.date())
    )
    success_count_by_ip_stmt = success_count_by_ip_stmt.where(
        AuthenticationStatistics.log_date.between(start_date.date(), end_date.date())
    )
    success_count_by_nas_ip_stmt = success_count_by_nas_ip_stmt.where(
        AuthenticationStatistics.log_date.between(start_date.date(), end_date.date())
    )

    # The result of this query is a list of Row objects, which are not directly JSON-serializable.
    # We need to convert them to a list of dicts.
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
        {
            "user_source_ip": r.user_source_ip,
            "success_count": r.success_count,
        }
        for r in success_count_by_ip_results
    ]
    success_count_by_nas_ip_results = session.exec(success_count_by_nas_ip_stmt).all()
    authentication_success_count_by_nas_ip = [
        {
            "nas_ip": r.nas_ip,
            "success_count": r.success_count,
        }
        for r in success_count_by_nas_ip_results
    ]

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
) -> None:
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

    authz_deny_count_stmt = authz_deny_count_stmt.where(
        AuthorizationStatistics.log_date.between(start_date.date(), end_date.date())
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


def process_today_authentication_statistics(
    session: Session,
) -> dict[str, int]:
    """
    Parses authentication logs for a specific date, aggregates the data per
    user/IP, and stores the results in the AuthenticationStatistics table.
    """
    # Construct the log file path from settings for the target date
    # This uses the default format from the TacacsNgSetting model
    # The script will process all authentication-*.log files in the current directory.
    # It will filter for log entries on the specific date below.
    today = datetime.now()
    TARGET_DATE_STR = today.strftime("%Y-%m-%d")
    year_str = today.strftime("%Y")
    month_str = today.strftime("%m")
    day_str = today.strftime("%d")

    # --- REGEX CONFIGURATION ---
    # Regex for the provided log format.
    # Example: "2025-11-23 11:39:08 +0000 103.161.38.106	user_admin		10.3.13.20	shell login failed"
    # Now supports IPv4 and IPv6 addresses.

    IP_REGEX = r"([a-fA-F0-9:.]+|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})"
    LOG_REGEX = re.compile(
        r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \+\d{4})\s+"
        rf"(?P<nas_ip>{IP_REGEX})\s+"
        r"(?P<username>[\w.-]+)\s+"
        r"(?:[\w.-]+\s+)?"  # Optional non-capturing group for fields like 'ssh'
        rf"(?P<client_ip>{IP_REGEX})\s+"
        r"(?P<message>.*)$"
    )
    log_file_format = (
        TACACS_LOG_DIRECTORY
        + "{year}/{month}/authentication-{year}-{month}-{day}.log".format(
            year=year_str, month=month_str, day=day_str
        )
    )
    logger.info(f"Using log file format: {log_file_format}")

    log_file_path = datetime.now().strftime(log_file_format)
    list_authentication_details = {
        "today_total_authentication_events": 0,
        "today": datetime.now().date().isoformat(),
        "today_list_authentication_details": [],
        "today_successful_logins": 0,
        "today_failed_logins": 0,
        "today_unique_user_source_ip_count": 0,
        "today_unique_nas_ip_count": 0,
    }
    if not os.path.exists(log_file_path):
        logger.error(f"Log file not found for date {TARGET_DATE_STR}: {log_file_path}")
        return list_authentication_details

    logger.info(f"Processing log file for date {TARGET_DATE_STR}: {log_file_path}")

    successful_logins = Counter()
    failed_logins = Counter()

    try:
        with open(log_file_path, "r", errors="ignore") as f:
            for line in f:
                # Quick check to ensure the line is for the correct day
                if not line.startswith(TARGET_DATE_STR):
                    continue

                match = LOG_REGEX.search(line)
                if not match:
                    continue

                log_data = match.groupdict()
                message = log_data["message"]

                # We only care about authentication events for this script
                if "login" in message:
                    username = log_data["username"]
                    nas_ip = log_data["nas_ip"]
                    client_ip = log_data["client_ip"]
                    key = (username, nas_ip, client_ip)
                    if "succeeded" in message:
                        successful_logins[key] += 1
                    else:  # Covers "failed" and "denied"
                        failed_logins[key] += 1
    except IOError as e:
        logger.error(f"Error reading file {log_file_path}: {e}")
        return list_authentication_details

    successful_auths = sum(successful_logins.values())
    failed_auths = sum(failed_logins.values())
    total_events = successful_auths + failed_auths

    if total_events == 0:
        logger.info(
            f"\nNo authentication log entries found for date {TARGET_DATE_STR}."
        )
        return list_authentication_details

    all_keys = set(successful_logins.keys()) | set(failed_logins.keys())
    unique_user_source_ips = {key[2] for key in all_keys}
    unique_nas_ips = {key[1] for key in all_keys}
    unique_user_source_ip_count = len(unique_user_source_ips)
    unique_nas_ip_count = len(unique_nas_ips)
    summary_date = today.date()

    # --- Print Statistics ---
    print(f"\n--- Authentication Summary for {summary_date} ---")
    print(f"Total Authentication Events: {total_events}")
    print(f"Unique NAS IPs: {unique_nas_ip_count}")
    print(f"  - Successful: {successful_auths}")
    print(f"  - Failed:     {failed_auths}")
    print(f"Unique User Source IPs: {unique_user_source_ip_count}")
    print(f"Unique User/NAS/Client combinations: {len(all_keys)}")
    print("--------------------------------------------------")

    # --- Aggregate statistics ---
    failed_count_by_user = defaultdict(int)
    for (username, _, _), count in failed_logins.items():
        failed_count_by_user[username] += count

    success_count_by_user = defaultdict(int)
    for (username, _, _), count in successful_logins.items():
        success_count_by_user[username] += count

    success_count_by_ip = defaultdict(int)
    for (_, _, client_ip), count in successful_logins.items():
        success_count_by_ip[client_ip] += count

    success_count_by_nas_ip = defaultdict(int)
    for (_, nas_ip, _), count in successful_logins.items():
        success_count_by_nas_ip[nas_ip] += count

    # --- Format aggregated statistics ---
    authentication_failed_count_by_user = sorted(
        [
            {"username": username, "fail_count": count}
            for username, count in failed_count_by_user.items()
        ],
        key=lambda x: x["fail_count"],
        reverse=True,
    )
    authentication_success_count_by_user = sorted(
        [
            {"username": username, "success_count": count}
            for username, count in success_count_by_user.items()
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
    list_authentication_details = []

    for username, nas_ip, user_source_ip in sorted(all_keys):
        key = (username, nas_ip, user_source_ip)
        success_count = successful_logins.get(key, 0)
        fail_count = failed_logins.get(key, 0)
        logger.info(
            f"User: {username}, NAS IP: {nas_ip}, Client IP: {user_source_ip} "
            f"=> Success: {success_count}, Fail: {fail_count}"
        )
        list_authentication_details.append(
            {
                "username": username,
                "nas_ip": nas_ip,
                "user_source_ip": user_source_ip,
                "success_count": success_count,
                "fail_count": fail_count,
            }
        )

    """
    Sample output:
    --- Authentication Summary for 2025-12-12 ---
    Total Authentication Events: 4
    - Successful: 3
    - Failed:     1
    Unique User/NAS/Client combinations: 2
    --------------------------------------------------

    Saving authentication statistics to the database...
    Updating stats for user_admin on 151.101.192.223 from 172.20.20.1
    Updating stats for user_read_only on 151.101.192.223 from 172.20.20.1
    """

    return {
        "today_total_authentication_events": total_events,
        "today": today.date().isoformat(),
        "today_list_authentication_details": list_authentication_details,
        "today_successful_logins": successful_auths,
        "today_failed_logins": failed_auths,
        "today_unique_user_source_ip_count": unique_user_source_ip_count,
        "today_unique_nas_ip_count": unique_nas_ip_count,
        "today_authentication_failed_count_by_user": authentication_failed_count_by_user,
        "today_authentication_success_count_by_user": authentication_success_count_by_user,
        "today_authentication_success_count_by_user_source_ip": (
            authentication_success_count_by_user_source_ip
        ),
        "today_authentication_success_count_by_nas_ip": (
            authentication_success_count_by_nas_ip
        ),
    }
