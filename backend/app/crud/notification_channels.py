import logging

from sqlmodel import Session, func, select

from app.crud.notification_dispatcher import dispatch_notification
from app.models import (
    NotificationChannel,
    NotificationChannelCreate,
    NotificationChannelUpdate,
)

logger = logging.getLogger(__name__)


def create_notification_channel(
    *, session: Session, channel_in: NotificationChannelCreate
) -> NotificationChannel:
    channel = NotificationChannel.model_validate(channel_in)
    session.add(channel)
    session.commit()
    session.refresh(channel)
    return channel


def get_notification_channels(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    enabled_only: bool = False,
) -> tuple[list[NotificationChannel], int]:
    query = select(NotificationChannel)
    count_query = select(func.count()).select_from(NotificationChannel)
    if enabled_only:
        query = query.where(NotificationChannel.enabled == True)  # noqa: E712
        count_query = count_query.where(NotificationChannel.enabled == True)  # noqa: E712
    count = session.exec(count_query).one()
    channels = session.exec(query.offset(skip).limit(limit)).all()
    return list(channels), count


def get_notification_channel(
    *, session: Session, channel_id: object
) -> NotificationChannel | None:
    return session.get(NotificationChannel, channel_id)


def update_notification_channel(
    *,
    session: Session,
    db_channel: NotificationChannel,
    channel_in: NotificationChannelUpdate,
) -> NotificationChannel:
    update_data = channel_in.model_dump(exclude_unset=True)
    db_channel.sqlmodel_update(update_data)
    session.add(db_channel)
    session.commit()
    session.refresh(db_channel)
    return db_channel


def delete_notification_channel(
    *, session: Session, db_channel: NotificationChannel
) -> None:
    session.delete(db_channel)
    session.commit()


def test_notification_channel(
    *, channel: NotificationChannel
) -> tuple[bool, str | None]:
    return dispatch_notification(
        channel=channel,
        subject="TACACS-NG Test Notification",
        body="This is a test notification from TACACS-NG UI. If you see this, the channel is configured correctly.",
    )
