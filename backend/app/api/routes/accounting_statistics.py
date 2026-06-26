from datetime import date, datetime, time as time_, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import asc, desc
from sqlmodel import func, select

from app.api.deps import SessionDep, get_current_user
from app.models import AccountingStatistics, AccountingStatisticsPublic

router = APIRouter(prefix="/accounting_statistics", tags=["accounting_statistics"])

_SORT_FIELDS = {
    "log_date": AccountingStatistics.log_date,
    "username": AccountingStatistics.username,
    "nas_ip": AccountingStatistics.nas_ip,
    "user_source_ip": AccountingStatistics.user_source_ip,
    "start_count": AccountingStatistics.start_count,
    "stop_count": AccountingStatistics.stop_count,
}


@router.get("/", dependencies=[Depends(get_current_user)], response_model=AccountingStatisticsPublic)
def read_accounting_statistics(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    date_from: date | None = None,
    date_to: date | None = None,
    sort_by: str = "log_date",
    sort_order: str = "desc",
    node_name: str | None = None,
) -> Any:
    col = _SORT_FIELDS.get(sort_by, AccountingStatistics.log_date)
    order = desc(col) if sort_order == "desc" else asc(col)

    count_stmt = select(func.count()).select_from(AccountingStatistics)
    stmt = select(AccountingStatistics)

    if date_from:
        dt = datetime.combine(date_from, time_.min).replace(tzinfo=timezone.utc)
        count_stmt = count_stmt.where(AccountingStatistics.log_date >= dt)
        stmt = stmt.where(AccountingStatistics.log_date >= dt)
    if date_to:
        dt = datetime.combine(date_to, time_.max).replace(tzinfo=timezone.utc)
        count_stmt = count_stmt.where(AccountingStatistics.log_date <= dt)
        stmt = stmt.where(AccountingStatistics.log_date <= dt)
    if node_name:
        count_stmt = count_stmt.where(AccountingStatistics.node_name == node_name)
        stmt = stmt.where(AccountingStatistics.node_name == node_name)

    count = session.exec(count_stmt).one()
    rows = session.exec(stmt.order_by(order).offset(skip).limit(limit)).all()
    return AccountingStatisticsPublic(data=rows, count=count)
