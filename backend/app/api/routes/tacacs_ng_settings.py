from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import (
    get_current_active_superuser,
    SessionDep,
    get_current_user,
)
from app.crud import tacacs_ng_settings
from app.models import (
    Message,
    TacacsNgSettingPublic,
    TacacsNgSettingUpdate,
)

router = APIRouter(prefix="/tacacs_ng_settings", tags=["tacacs_ng_settings"])


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
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TacacsNgSettingPublic,
)
def update_tacacs_ng_settings(
    *,
    session: SessionDep,
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
    db_tacacs_ng = tacacs_ng_settings.update_tacacs_ng(
        session=session, db_tacacs_ng=db_tacacs_ng, tacacs_ng_in=tacacs_ng_in
    )
    return db_tacacs_ng
