import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, SessionDep, require_primary_node
from app.crud import notification_channels as crud_channels
from app.models import (
    NotificationChannelCreate,
    NotificationChannelPublic,
    NotificationChannelsPublic,
    NotificationChannelUpdate,
)

router = APIRouter(prefix="/notification_channels", tags=["notification_channels"])


@router.get("/", response_model=NotificationChannelsPublic)
def read_notification_channels(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    channels, count = crud_channels.get_notification_channels(
        session=session, skip=skip, limit=limit
    )
    return NotificationChannelsPublic(data=channels, count=count)


@router.post(
    "/",
    dependencies=[Depends(require_primary_node)],
    response_model=NotificationChannelPublic,
)
def create_notification_channel(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    channel_in: NotificationChannelCreate,
) -> Any:
    return crud_channels.create_notification_channel(
        session=session, channel_in=channel_in
    )


@router.get("/{id}", response_model=NotificationChannelPublic)
def read_notification_channel_by_id(
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    channel = crud_channels.get_notification_channel(session=session, channel_id=id)
    if not channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    return channel


@router.patch(
    "/{id}",
    dependencies=[Depends(require_primary_node)],
    response_model=NotificationChannelPublic,
)
def update_notification_channel(
    *,
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    channel_in: NotificationChannelUpdate,
) -> Any:
    db_channel = crud_channels.get_notification_channel(session=session, channel_id=id)
    if not db_channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    return crud_channels.update_notification_channel(
        session=session, db_channel=db_channel, channel_in=channel_in
    )


@router.delete("/{id}", dependencies=[Depends(require_primary_node)])
def delete_notification_channel(
    *,
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    db_channel = crud_channels.get_notification_channel(session=session, channel_id=id)
    if not db_channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    crud_channels.delete_notification_channel(session=session, db_channel=db_channel)
    return {"message": "Notification channel deleted"}


@router.post("/{id}/test")
def test_notification_channel(
    *,
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    db_channel = crud_channels.get_notification_channel(session=session, channel_id=id)
    if not db_channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    success, error_msg = crud_channels.test_notification_channel(channel=db_channel)
    if not success:
        raise HTTPException(status_code=502, detail=f"Test failed: {error_msg}")
    return {"message": "Test notification sent successfully"}
