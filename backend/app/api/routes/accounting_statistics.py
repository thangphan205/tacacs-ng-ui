import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select


from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    AccountingStatistics,
    AccountingStatisticsPublic,
)

router = APIRouter(prefix="/accounting_statistics", tags=["accounting_statistics"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=AccountingStatisticsPublic,
)
def read_accounting_statistics(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve accounting_statistics.
    """

    count_statement = select(func.count()).select_from(AccountingStatistics)
    count = session.exec(count_statement).one()

    statement = select(AccountingStatistics).offset(skip).limit(limit)
    accounting_statistics = session.exec(statement).all()

    return AccountingStatisticsPublic(data=accounting_statistics, count=count)
