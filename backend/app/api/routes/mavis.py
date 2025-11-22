from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import (
    get_current_active_superuser,
    SessionDep,
    get_current_user,
)
from app.crud import mavis as mavis_crud
from app.models import (
    MavisPublic,
    MavisUpdate,
)

router = APIRouter(prefix="/mavis", tags=["mavis"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=MavisPublic,
)
def read_mavis_settings(
    session: SessionDep,
) -> Any:
    """
    Retrieve mavis settings.
    """
    mavis = mavis_crud.get_mavis(session=session)
    if not mavis:
        raise HTTPException(status_code=404, detail="Mavis settings not found")
    return mavis


@router.put(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=MavisPublic,
)
def update_mavis_settings(
    *,
    session: SessionDep,
    mavis_in: MavisUpdate,
) -> Any:
    """
    Update mavis settings.
    """

    db_mavis = mavis_crud.get_mavis(session=session)
    if not db_mavis:
        raise HTTPException(status_code=404, detail="Mavis settings not found")

    db_mavis = mavis_crud.update_mavis(
        session=session, db_mavis=db_mavis, mavis_in=mavis_in
    )
    return db_mavis
