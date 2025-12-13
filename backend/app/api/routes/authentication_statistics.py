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
    AuthenticationStatistics,
    AuthenticationStatisticsPublic,
)

router = APIRouter(
    prefix="/authentication_statistics", tags=["authentication_statistics"]
)


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=AuthenticationStatisticsPublic,
)
def read_authentication_statistics(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve authentication_statistics.
    """

    count_statement = select(func.count()).select_from(AuthenticationStatistics)
    count = session.exec(count_statement).one()

    statement = select(AuthenticationStatistics).offset(skip).limit(limit)
    authentication_statistics = session.exec(statement).all()

    return AuthenticationStatisticsPublic(data=authentication_statistics, count=count)
