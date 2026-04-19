import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import func, select

from app.api.deps import (
    SessionDep,
    SuperUser,
    get_current_user,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import hosts
from app.models import (
    Host,
    HostCreate,
    HostPublic,
    HostsPublic,
    HostUpdate,
    Message,
)

router = APIRouter(prefix="/hosts", tags=["hosts"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=HostsPublic,
)
def read_hosts(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve hosts.
    """

    count_statement = select(func.count()).select_from(Host)
    count = session.exec(count_statement).one()

    statement = select(Host).offset(skip).limit(limit)
    hosts = session.exec(statement).all()

    return HostsPublic(data=hosts, count=count)


@router.post(
    "/",
    response_model=HostPublic,
)
def create_host(
    *, session: SessionDep, current_user: SuperUser, request: Request, host_in: HostCreate
) -> Any:
    """
    Create new host.
    """
    host = hosts.get_host_by_name(session=session, name=host_in.name)
    if host:
        raise HTTPException(
            status_code=400,
            detail="The host with this host name already exists in the system.",
        )

    host = hosts.create_host(session=session, host_create=host_in)
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="Host",
        entity_id=str(host.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        new_values=host.model_dump_json(exclude=_SENSITIVE),
    )
    return host


@router.get(
    "/{id}", dependencies=[Depends(get_current_user)], response_model=HostPublic
)
def read_host_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific host by id.
    """
    host = session.get(Host, id)
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    return host


@router.put(
    "/{id}",
    response_model=HostPublic,
)
def update_host(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    host_in: HostUpdate,
) -> Any:
    """
    Update a host.
    """
    db_host = session.get(Host, id)
    if not db_host:
        raise HTTPException(
            status_code=404,
            detail="The host with this id does not exist in the system",
        )
    old_values = db_host.model_dump_json(exclude=_SENSITIVE)
    db_host = hosts.update_host(session=session, db_host=db_host, host_in=host_in)
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="Host",
        entity_id=str(db_host.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_host.model_dump_json(exclude=_SENSITIVE),
    )
    return db_host


@router.delete(
    "/{id}",
)
def delete_host(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a host.
    """
    host = session.get(Host, id)
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")

    old_values = host.model_dump_json(exclude=_SENSITIVE)
    session.delete(host)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="Host",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="Host deleted successfully")
