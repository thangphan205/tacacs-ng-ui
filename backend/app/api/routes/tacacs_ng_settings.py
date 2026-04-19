from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import (
    SessionDep,
    SuperUser,
    get_client_ip,
    get_current_user,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import tacacs_ng_settings
from app.models import (
    TacacsNgSettingPublic,
    TacacsNgSettingUpdate,
)

router = APIRouter(prefix="/tacacs_ng_settings", tags=["tacacs_ng_settings"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsNgSettingPublic,
)
def read_tacacs_ng_settings(
    session: SessionDep,
) -> Any:
    """
    Retrieve tacacs_ng settings.
    """
    tacacs_ng = tacacs_ng_settings.get_tacacs_ng(session=session)
    if not tacacs_ng:
        raise HTTPException(
            status_code=404, detail="TacacsNgSetting settings not found"
        )
    return tacacs_ng


@router.put(
    "/",
    response_model=TacacsNgSettingPublic,
)
def update_tacacs_ng_settings(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    tacacs_ng_in: TacacsNgSettingUpdate,
) -> Any:
    """
    Update tacacs_ng settings.
    """

    db_tacacs_ng = tacacs_ng_settings.get_tacacs_ng(session=session)
    if not db_tacacs_ng:
        raise HTTPException(
            status_code=404, detail="TacacsNgSetting settings not found"
        )
    old_values = db_tacacs_ng.model_dump_json(exclude=_SENSITIVE)
    db_tacacs_ng = tacacs_ng_settings.update_tacacs_ng(
        session=session, db_tacacs_ng=db_tacacs_ng, tacacs_ng_in=tacacs_ng_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="TacacsNgSetting",
        entity_id=str(db_tacacs_ng.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_tacacs_ng.model_dump_json(exclude=_SENSITIVE),
    )
    return db_tacacs_ng
