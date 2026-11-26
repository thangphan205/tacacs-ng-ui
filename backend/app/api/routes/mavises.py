import uuid
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from sqlmodel import func, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    SuperUser,
    get_client_ip,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import mavises
from app.mcp_server.redact import REDACTED, is_secret_mavis_key
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


def _mavis_for_user(mavis: Mavis, current_user: CurrentUser) -> MavisPublic:
    pub = MavisPublic.model_validate(mavis)
    if not current_user.is_superuser and pub.mavis_value and is_secret_mavis_key(pub.mavis_key):
        pub.mavis_value = REDACTED
    return pub


@router.get(
    "/",
    response_model=MavisesPublic,
)
def read_mavises(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> Any:
    """
    Retrieve mavises.
    """

    count_statement = select(func.count()).select_from(Mavis)
    statement = select(Mavis)
    if search:
        if current_user.is_superuser:
            f = Mavis.mavis_key.ilike(f"%{search}%") | Mavis.mavis_value.ilike(
                f"%{search}%"
            )
        else:
            # Avoid search-oracle leaks against secret mavis_value entries.
            f = Mavis.mavis_key.ilike(f"%{search}%")
        count_statement = count_statement.where(f)
        statement = statement.where(f)
    count = session.exec(count_statement).one()
    rows = session.exec(statement.offset(skip).limit(limit)).all()

    return MavisesPublic(
        data=[_mavis_for_user(m, current_user) for m in rows], count=count
    )


@router.post(
    "/",
    response_model=MavisPublic,
)
def create_mavis(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    mavis_in: MavisCreate,
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
        session=session,
        action="CREATE",
        entity_type="Mavis",
        entity_id=str(mavis.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=mavis.model_dump_json(exclude=_SENSITIVE),
    )
    return mavis


@router.get(
    "/preview",
    response_model=MavisPreviewPublic,
)
def preview_mavis(session: SessionDep, current_user: CurrentUser) -> Any:
    """
    Preview mavis configuration.
    """
    statement = select(Mavis)
    rows = session.exec(statement).all()

    if not rows:
        return MavisPreviewPublic(data=None, created_at=None, updated_at=None)

    lines = []
    for m in rows:
        val = (
            REDACTED
            if (
                not current_user.is_superuser
                and m.mavis_value
                and is_secret_mavis_key(m.mavis_key)
            )
            else m.mavis_value
        )
        lines.append(f'setenv {m.mavis_key}="{val}"')
    data = "\n".join(lines)

    created_at = min(m.created_at for m in rows)
    updated_at = max(m.updated_at for m in rows)

    return MavisPreviewPublic(
        data=data,
        created_at=created_at,
        updated_at=updated_at,
    )


@router.get("/{id}", response_model=MavisPublic)
def read_mavis_by_id(
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Get a specific mavis by id.
    """
    mavis = session.get(Mavis, id)
    if not mavis:
        raise HTTPException(status_code=404, detail="Mavis not found")
    return _mavis_for_user(mavis, current_user)


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
        session=session,
        action="UPDATE",
        entity_type="Mavis",
        entity_id=str(db_mavis.id),
        user_id=current_user.id,
        user_email=current_user.email,
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
        session=session,
        action="DELETE",
        entity_type="Mavis",
        entity_id=str(id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="Mavis deleted successfully")
