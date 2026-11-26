import json
import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import (
    CurrentUser,
    SessionDep,
    SuperUser,
    get_client_ip,
    require_primary_node,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import notification_channels as crud_channels
from app.mcp_server.redact import REDACTED
from app.models import (
    NotificationChannel,
    NotificationChannelCreate,
    NotificationChannelPublic,
    NotificationChannelsPublic,
    NotificationChannelUpdate,
)

router = APIRouter(prefix="/notification_channels", tags=["notification_channels"])

_SENSITIVE = set(audit_logs_crud._SENSITIVE)
_SECRET_CONFIG_KEY = re.compile(
    r"PASS|SECRET|TOKEN|PRIVATE|CREDENTIAL|WEBHOOK|AUTH|(^|_)(PW|KEY)($|_)",
    re.IGNORECASE,
)


def _redact_config_json(raw: str) -> str:
    """Mask secret keys (bot_token, webhook_url, token, smtp_password, ...) in config_json."""
    if not raw:
        return raw
    try:
        parsed = json.loads(raw)
    except ValueError:
        return REDACTED
    if not isinstance(parsed, dict):
        return REDACTED
    redacted: dict[str, Any] = {}
    for k, v in parsed.items():
        if _SECRET_CONFIG_KEY.search(str(k)) and v not in (None, ""):
            redacted[k] = REDACTED
        else:
            redacted[k] = v
    return json.dumps(redacted, indent=2, ensure_ascii=False)


def _channel_for_user(
    channel: NotificationChannel, current_user: CurrentUser
) -> NotificationChannelPublic:
    pub = NotificationChannelPublic.model_validate(channel)
    if not current_user.is_superuser and pub.config_json:
        pub.config_json = _redact_config_json(pub.config_json)
    return pub


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
    return NotificationChannelsPublic(
        data=[_channel_for_user(ch, current_user) for ch in channels],
        count=count,
    )


@router.post(
    "/",
    dependencies=[Depends(require_primary_node)],
    response_model=NotificationChannelPublic,
)
def create_notification_channel(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    channel_in: NotificationChannelCreate,
) -> Any:
    channel = crud_channels.create_notification_channel(
        session=session, channel_in=channel_in
    )
    audit_logs_crud.log_entity_action(
        session=session,
        action="CREATE",
        entity_type="NotificationChannel",
        entity_id=str(channel.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=channel.model_dump_json(exclude=_SENSITIVE),
    )
    return channel


@router.get("/{id}", response_model=NotificationChannelPublic)
def read_notification_channel_by_id(
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    channel = crud_channels.get_notification_channel(session=session, channel_id=id)
    if not channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    return _channel_for_user(channel, current_user)


@router.patch(
    "/{id}",
    dependencies=[Depends(require_primary_node)],
    response_model=NotificationChannelPublic,
)
def update_notification_channel(
    *,
    id: uuid.UUID,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    channel_in: NotificationChannelUpdate,
) -> Any:
    db_channel = crud_channels.get_notification_channel(session=session, channel_id=id)
    if not db_channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    old_values = db_channel.model_dump_json(exclude=_SENSITIVE)
    updated = crud_channels.update_notification_channel(
        session=session, db_channel=db_channel, channel_in=channel_in
    )
    audit_logs_crud.log_entity_action(
        session=session,
        action="UPDATE",
        entity_type="NotificationChannel",
        entity_id=str(updated.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=updated.model_dump_json(exclude=_SENSITIVE),
    )
    return updated


@router.delete("/{id}", dependencies=[Depends(require_primary_node)])
def delete_notification_channel(
    *,
    id: uuid.UUID,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
) -> dict[str, str]:
    db_channel = crud_channels.get_notification_channel(session=session, channel_id=id)
    if not db_channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    old_values = db_channel.model_dump_json(exclude=_SENSITIVE)
    crud_channels.delete_notification_channel(session=session, db_channel=db_channel)
    audit_logs_crud.log_entity_action(
        session=session,
        action="DELETE",
        entity_type="NotificationChannel",
        entity_id=str(id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return {"message": "Notification channel deleted"}


@router.post("/{id}/test")
def test_notification_channel(
    *,
    id: uuid.UUID,
    session: SessionDep,
    _: SuperUser,
) -> dict[str, str]:
    db_channel = crud_channels.get_notification_channel(session=session, channel_id=id)
    if not db_channel:
        raise HTTPException(status_code=404, detail="Notification channel not found")
    success, error_msg = crud_channels.test_notification_channel(channel=db_channel)
    if not success:
        raise HTTPException(status_code=502, detail=f"Test failed: {error_msg}")
    return {"message": "Test notification sent successfully"}
