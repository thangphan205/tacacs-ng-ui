from datetime import date, datetime, time as time_, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import asc, desc
from sqlmodel import func, select

from app.api.deps import SessionDep, get_current_user
from app.models import AuthorizationStatistics, AuthorizationStatisticsPublic

router = APIRouter(prefix="/authorization_statistics", tags=["authorization_statistics"])

_SORT_FIELDS = {
    "log_date": AuthorizationStatistics.log_date,
    "username": AuthorizationStatistics.username,
    "nas_ip": AuthorizationStatistics.nas_ip,
    "user_source_ip": AuthorizationStatistics.user_source_ip,
    "permit_count": AuthorizationStatistics.permit_count,
    "deny_count": AuthorizationStatistics.deny_count,
}


@router.get("/", dependencies=[Depends(get_current_user)], response_model=AuthorizationStatisticsPublic)
def read_authorization_statistics(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = "log_date",
    sort_order: str = "desc",
    node_name: str | None = None,
) -> Any:
    col = _SORT_FIELDS.get(sort_by, AuthorizationStatistics.log_date)
    order = desc(col) if sort_order == "desc" else asc(col)

    count_stmt = select(func.count()).select_from(AuthorizationStatistics)
    stmt = select(AuthorizationStatistics)

    if date_from:
        dt = datetime.combine(date_from, time_.min).replace(tzinfo=timezone.utc)
        count_stmt = count_stmt.where(AuthorizationStatistics.log_date >= dt)
        stmt = stmt.where(AuthorizationStatistics.log_date >= dt)
    if date_to:
        dt = datetime.combine(date_to, time_.max).replace(tzinfo=timezone.utc)
        count_stmt = count_stmt.where(AuthorizationStatistics.log_date <= dt)
        stmt = stmt.where(AuthorizationStatistics.log_date <= dt)
    if node_name:
        count_stmt = count_stmt.where(AuthorizationStatistics.node_name == node_name)
        stmt = stmt.where(AuthorizationStatistics.node_name == node_name)

    count = session.exec(count_stmt).one()
    rows = session.exec(stmt.order_by(order).offset(skip).limit(limit)).all()
    return AuthorizationStatisticsPublic(data=rows, count=count)
