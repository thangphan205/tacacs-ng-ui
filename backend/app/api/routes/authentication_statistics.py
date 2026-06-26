from datetime import date, datetime, timezone
from datetime import time as time_
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import asc, desc
from sqlmodel import func, select

from app.api.deps import SessionDep, get_current_user
from app.models import AuthenticationStatistics, AuthenticationStatisticsPublic

router = APIRouter(
    prefix="/authentication_statistics", tags=["authentication_statistics"]
)

_SORT_FIELDS = {
    "log_date": AuthenticationStatistics.log_date,
    "username": AuthenticationStatistics.username,
    "nas_ip": AuthenticationStatistics.nas_ip,
    "user_source_ip": AuthenticationStatistics.user_source_ip,
    "success_count": AuthenticationStatistics.success_count,
    "fail_count": AuthenticationStatistics.fail_count,
}


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=AuthenticationStatisticsPublic,
)
def read_authentication_statistics(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = "log_date",
    sort_order: str = "desc",
    node_name: str | None = None,
) -> Any:
    col = _SORT_FIELDS.get(sort_by, AuthenticationStatistics.log_date)
    order = desc(col) if sort_order == "desc" else asc(col)

    count_stmt = select(func.count()).select_from(AuthenticationStatistics)
    stmt = select(AuthenticationStatistics)

    if date_from:
        dt = datetime.combine(date_from, time_.min).replace(tzinfo=timezone.utc)
        count_stmt = count_stmt.where(AuthenticationStatistics.log_date >= dt)
        stmt = stmt.where(AuthenticationStatistics.log_date >= dt)
    if date_to:
        dt = datetime.combine(date_to, time_.max).replace(tzinfo=timezone.utc)
        count_stmt = count_stmt.where(AuthenticationStatistics.log_date <= dt)
        stmt = stmt.where(AuthenticationStatistics.log_date <= dt)
    if node_name:
        count_stmt = count_stmt.where(AuthenticationStatistics.node_name == node_name)
        stmt = stmt.where(AuthenticationStatistics.node_name == node_name)

    count = session.exec(count_stmt).one()
    rows = session.exec(stmt.order_by(order).offset(skip).limit(limit)).all()
    return AuthenticationStatisticsPublic(data=rows, count=count)
