import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import func, select

from app.api.deps import (
    SessionDep,
    SuperUser,
    get_client_ip,
    get_current_user,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import mavises
from app.models import (
    Mavis,
    MavisCreate,
    MavisesPublic,
    MavisPreviewPublic,
    MavisPublic,
    MavisUpdate,
    Message,
)

router = APIRouter(prefix="/mavises", tags=["mavises"])

_SENSITIVE = audit_logs_crud._SENSITIVE


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
    response_model=MavisPublic,
)
def create_mavis(
    *, session: SessionDep, current_user: SuperUser, request: Request, mavis_in: MavisCreate
) -> Any:
    """
    Create new mavis.
    """
    mavis = mavises.get_mavis_by_key(session=session, mavis_key=mavis_in.mavis_key)
    if mavis:
        raise HTTPException(
            status_code=400,
            detail=f"The mavis with this mavis key {mavis_in.mavis_key} already exists in the system.",
        )

    mavis = mavises.create_mavis(session=session, mavis_create=mavis_in)
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="Mavis",
        entity_id=str(mavis.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=mavis.model_dump_json(exclude=_SENSITIVE),
    )
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

    data = "\n".join([f'setenv {m.mavis_key}="{m.mavis_value}"' for m in mavises])

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
    response_model=MavisPublic,
)
def update_mavis(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
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
    old_values = db_mavis.model_dump_json(exclude=_SENSITIVE)
    db_mavis = mavises.update_mavis(
        session=session, db_mavis=db_mavis, mavis_in=mavis_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="Mavis",
        entity_id=str(db_mavis.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_mavis.model_dump_json(exclude=_SENSITIVE),
    )
    return db_mavis


@router.delete(
    "/{id}",
)
def delete_mavis(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a mavis.
    """
    mavis = session.get(Mavis, id)
    if not mavis:
        raise HTTPException(status_code=404, detail="Mavis not found")

    old_values = mavis.model_dump_json(exclude=_SENSITIVE)
    session.delete(mavis)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="Mavis",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="Mavis deleted successfully")
