import uuid
from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser, SessionDep
from app.crud import alert_events as crud_alert_events
from app.models import AlertEventsPublic, AlertStatistics

router = APIRouter(prefix="/alert_events", tags=["alert_events"])


@router.get("/statistics", response_model=AlertStatistics)
def read_alert_statistics(session: SessionDep, _: CurrentUser) -> Any:
    return crud_alert_events.get_alert_statistics(session=session)


@router.get("/", response_model=AlertEventsPublic)
def read_alert_events(
    session: SessionDep,
    _: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    rule_id: uuid.UUID | None = None,
    status: str | None = None,
) -> Any:
    events, count = crud_alert_events.get_alert_events(
        session=session,
        skip=skip,
        limit=limit,
        rule_id=rule_id,
        status=status,
    )
    return AlertEventsPublic(data=events, count=count)
