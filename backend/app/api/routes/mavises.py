from typing import Any
import uuid
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import (
    get_current_active_superuser,
    SessionDep,
    get_current_user,
)
from app.crud import mavises
from app.models import (
    Mavis,
    MavisCreate,
    MavisPublic,
    MavisPreviewPublic,
    MavisUpdate,
    MavisesPublic,
    Message,
)
from sqlmodel import func, select

router = APIRouter(prefix="/mavises", tags=["mavises"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=MavisesPublic,
)
def read_mavises(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve mavises.
    """

    count_statement = select(func.count()).select_from(Mavis)
    count = session.exec(count_statement).one()

    statement = select(Mavis).offset(skip).limit(limit)
    mavises = session.exec(statement).all()

    return MavisesPublic(data=mavises, count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=MavisPublic,
)
def create_mavis(*, session: SessionDep, mavis_in: MavisCreate) -> Any:
    """
    Create new mavis.
    """
    mavis = mavises.get_mavis_by_key(session=session, mavis_key=mavis_in.mavis_key)
    if mavis:
        raise HTTPException(
            status_code=400,
            detail="The mavis with this mavis key {} already exists in the system.".format(
                mavis_in.mavis_key
            ),
        )

    mavis = mavises.create_mavis(session=session, mavis_create=mavis_in)
    return mavis


@router.get(
    "/preview",
    dependencies=[Depends(get_current_user)],
    response_model=MavisPreviewPublic,
)
def preview_mavis(session: SessionDep) -> Any:
    """
    Preview mavis configuration.
    """
    statement = select(Mavis)
    mavises = session.exec(statement).all()

    if not mavises:
        return MavisPreviewPublic(data=None, created_at=None, updated_at=None)

    # Format the mavis data into key = "value" format
    data = "\n".join([f'setenv {m.mavis_key}="{m.mavis_value}"' for m in mavises])

    # Find the earliest created_at and latest updated_at
    created_at = min(m.created_at for m in mavises)
    updated_at = max(m.updated_at for m in mavises)

    return MavisPreviewPublic(
        data=data,
        created_at=created_at,
        updated_at=updated_at,
    )


@router.get(
    "/{id}", dependencies=[Depends(get_current_user)], response_model=MavisPublic
)
def read_mavis_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific mavis by id.
    """
    mavis = session.get(Mavis, id)
    if not mavis:
        raise HTTPException(status_code=404, detail="Mavis not found")
    return mavis


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=MavisPublic,
)
def update_mavis(
    *,
    session: SessionDep,
    id: uuid.UUID,
    mavis_in: MavisUpdate,
) -> Any:
    """
    Update a mavis.
    """
    db_mavis = session.get(Mavis, id)
    if not db_mavis:
        raise HTTPException(
            status_code=404,
            detail="The mavis with this id does not exist in the system",
        )
    db_mavis = mavises.update_mavis(
        session=session, db_mavis=db_mavis, mavis_in=mavis_in
    )
    return db_mavis


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_mavis(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete a mavis.
    """
    mavis = session.get(Mavis, id)
    if not mavis:
        raise HTTPException(status_code=404, detail="Mavis not found")

    session.delete(mavis)
    session.commit()
    return Message(message="Mavis deleted successfully")
