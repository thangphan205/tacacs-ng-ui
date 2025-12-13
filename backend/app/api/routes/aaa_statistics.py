import uuid
from datetime import datetime, time, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select


from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    AuthenticationStatistics,
    AuthorizationStatistics,
    AccountingStatistics,
    AaaStatisticsSummaryPublic,
)

router = APIRouter(prefix="/aaa_statistics", tags=["aaa_statistics"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=AaaStatisticsSummaryPublic,
)
def read_aaa_statistics(
    session: SessionDep, skip: int = 0, limit: int = 5, range_date: str = None
) -> Any:
    """
    Retrieve aaa_statistics.
    """

    if range_date:
        try:
            start_date_str, end_date_str = range_date.split(",")
            start_date = datetime.fromisoformat(start_date_str)
            # Combine end date with max time to include the whole day
            end_date = datetime.combine(
                datetime.fromisoformat(end_date_str).date(), time.max
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid range_date format. Expected 'YYYY-MM-DD,YYYY-MM-DD'.",
            )
    else:
        # Default to today if no range is provided
        today = datetime.now().date()
        start_date = datetime.combine(today, time.min)
        end_date = datetime.combine(today, time.max)

    # For the 7-day trend chart
    start_date_7_days = end_date - timedelta(days=6)

    auth_stmt = select(AuthenticationStatistics)
    authz_stmt = select(AuthorizationStatistics)
    acct_stmt = select(AccountingStatistics)
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

    # Queries for last 7 days statistics
    auth_success_daily_stmt = (
        select(
            func.date(AuthenticationStatistics.created_at).label("date"),
            func.sum(AuthenticationStatistics.success_count).label("count"),
        )
        .where(AuthenticationStatistics.created_at >= start_date_7_days)
        .group_by(func.date(AuthenticationStatistics.created_at))
        .order_by(func.date(AuthenticationStatistics.created_at))
    )
    auth_fail_daily_stmt = (
        select(
            func.date(AuthenticationStatistics.created_at).label("date"),
            func.sum(AuthenticationStatistics.fail_count).label("count"),
        )
        .where(AuthenticationStatistics.created_at >= start_date_7_days)
        .group_by(func.date(AuthenticationStatistics.created_at))
        .order_by(func.date(AuthenticationStatistics.created_at))
    )
    authz_permit_daily_stmt = (
        select(
            func.date(AuthorizationStatistics.created_at).label("date"),
            func.sum(AuthorizationStatistics.permit_count).label("count"),
        )
        .where(AuthorizationStatistics.created_at >= start_date_7_days)
        .group_by(func.date(AuthorizationStatistics.created_at))
        .order_by(func.date(AuthorizationStatistics.created_at))
    )
    authz_deny_daily_stmt = (
        select(
            func.date(AuthorizationStatistics.created_at).label("date"),
            func.sum(AuthorizationStatistics.deny_count).label("count"),
        )
        .where(AuthorizationStatistics.created_at >= start_date_7_days)
        .group_by(func.date(AuthorizationStatistics.created_at))
        .order_by(func.date(AuthorizationStatistics.created_at))
    )
    acct_daily_stmt = (
        select(
            func.date(AccountingStatistics.created_at).label("date"),
            func.sum(AccountingStatistics.start_count).label("start_count"),
            func.sum(AccountingStatistics.stop_count).label("stop_count"),
        )
        .where(AccountingStatistics.created_at >= start_date_7_days)
        .group_by(func.date(AccountingStatistics.created_at))
        .order_by(func.date(AccountingStatistics.created_at))
    )

    # Apply the date range filter to all queries
    auth_stmt = auth_stmt.where(
        AuthenticationStatistics.created_at.between(start_date, end_date)
    )
    authz_stmt = authz_stmt.where(
        AuthorizationStatistics.created_at.between(start_date, end_date)
    )
    acct_stmt = acct_stmt.where(
        AccountingStatistics.created_at.between(start_date, end_date)
    )
    failed_count_stmt = failed_count_stmt.where(
        AuthenticationStatistics.created_at.between(start_date, end_date)
    )
    success_count_stmt = success_count_stmt.where(
        AuthenticationStatistics.created_at.between(start_date, end_date)
    )
    authz_deny_count_stmt = authz_deny_count_stmt.where(
        AuthorizationStatistics.created_at.between(start_date, end_date)
    )
    success_count_by_ip_stmt = success_count_by_ip_stmt.where(
        AuthenticationStatistics.created_at.between(start_date, end_date)
    )

    authentication_statistics = session.exec(auth_stmt).all()
    authorization_statistics = session.exec(authz_stmt).all()
    accounting_statistics = session.exec(acct_stmt).all()

    # The result of this query is a list of Row objects, which are not directly JSON-serializable.
    # We need to convert them to a list of dicts.
    failed_count_results = session.exec(failed_count_stmt).all()
    # Convert the Row objects to a list of dicts
    authentication_failed_count_by_user = [
        {"username": r.username, "fail_count": r.fail_count}
        for r in failed_count_results
    ]

    success_count_results = session.exec(success_count_stmt).all()
    # Convert the Row objects to a list of dicts
    authentication_success_count_by_user = [
        {"username": r.username, "success_count": r.success_count}
        for r in success_count_results
    ]

    authz_deny_count_results = session.exec(authz_deny_count_stmt).all()
    # Convert the Row objects to a list of dicts
    authorization_deny_count_by_user = [
        {"username": r.username, "deny_count": r.deny_count}
        for r in authz_deny_count_results
    ]

    success_count_by_ip_results = session.exec(success_count_by_ip_stmt).all()
    # Convert the Row objects to a list of dicts
    authentication_success_count_by_user_source_ip = [
        {
            "user_source_ip": r.user_source_ip,
            "success_count": r.success_count,
        }
        for r in success_count_by_ip_results
    ]

    # Execute daily count queries
    auth_success_daily_results = session.exec(auth_success_daily_stmt).all()
    auth_fail_daily_results = session.exec(auth_fail_daily_stmt).all()
    authz_pass_daily_results = session.exec(authz_permit_daily_stmt).all()
    authz_deny_daily_results = session.exec(authz_deny_daily_stmt).all()
    acct_daily_results = session.exec(acct_daily_stmt).all()

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

    # Generate date range for the last 7 days to ensure all days are present
    all_dates = [(end_date.date() - timedelta(days=i)) for i in range(7)]
    all_dates.reverse()

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

    return {
        "authentication": authentication_statistics,
        "authentication_failed_count_by_user": authentication_failed_count_by_user[
            skip : skip + limit
        ],
        "authentication_success_count_by_user": authentication_success_count_by_user[
            skip : skip + limit
        ],
        "authentication_success_count_by_user_source_ip": authentication_success_count_by_user_source_ip[
            skip : skip + limit
        ],
        "authorization": authorization_statistics,
        "accounting": accounting_statistics,
        "authorization_deny_count_by_user": authorization_deny_count_by_user[
            skip : skip + limit
        ],
        "last_7_days_authentication_success": fill_missing_dates(
            format_daily_data(auth_success_daily_results), all_dates
        ),
        "last_7_days_authentication_fail": fill_missing_dates(
            format_daily_data(auth_fail_daily_results), all_dates
        ),
        "last_7_days_authorization_pass": fill_missing_dates(
            format_daily_data(authz_pass_daily_results), all_dates
        ),
        "last_7_days_authorization_deny": fill_missing_dates(
            format_daily_data(authz_deny_daily_results), all_dates
        ),
        "last_7_days_accounting": fill_missing_acct_dates(
            format_acct_daily_data(acct_daily_results), all_dates
        ),
    }
