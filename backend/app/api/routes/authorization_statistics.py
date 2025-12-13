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
    AuthorizationStatistics,
    AuthorizationStatisticsPublic,
)

router = APIRouter(
    prefix="/authorization_statistics", tags=["authorization_statistics"]
)


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=AuthorizationStatisticsPublic,
)
def read_authorization_statistics(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve authorization_statistics.
    """

    count_statement = select(func.count()).select_from(AuthorizationStatistics)
    count = session.exec(count_statement).one()

    statement = select(AuthorizationStatistics).offset(skip).limit(limit)
    authorization_statistics = session.exec(statement).all()

    return AuthorizationStatisticsPublic(data=authorization_statistics, count=count)
