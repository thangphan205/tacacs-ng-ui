import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import asc, desc, func, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    SuperUser,
    get_client_ip,
    require_primary_node,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import hosts
from app.mcp_server.redact import REDACTED
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

_SORT_FIELDS = {
    "name": Host.name,
    "ipv4_address": Host.ipv4_address,
    "created_at": Host.created_at,
    "updated_at": Host.updated_at,
}


def _host_for_user(host: Host, current_user: CurrentUser) -> HostPublic:
    pub = HostPublic.model_validate(host)
    if not current_user.is_superuser:
        if pub.secret_key:
            pub.secret_key = REDACTED
        if pub.radius_secret_key:
            pub.radius_secret_key = REDACTED
    return pub


@router.get(
    "/",
    response_model=HostsPublic,
)
def read_hosts(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
    sort_by: str = "name",
    sort_order: str = "asc",
    has_radius_secret: bool | None = None,
) -> Any:
    """
    Retrieve hosts, sorted by name unless sort_by says otherwise.
    `has_radius_secret` keeps only hosts with (true) or without (false) a
    RADIUS secret of their own.
    """

    count_statement = select(func.count()).select_from(Host)
    statement = select(Host)
    if search:
        f = (
            Host.name.ilike(f"%{search}%")
            | Host.ipv4_address.ilike(f"%{search}%")
            | Host.ipv6_address.ilike(f"%{search}%")
            | Host.description.ilike(f"%{search}%")
        )
        count_statement = count_statement.where(f)
        statement = statement.where(f)
    if has_radius_secret is not None:
        has = Host.radius_secret_key.is_not(None) & (Host.radius_secret_key != "")
        f = has if has_radius_secret else ~has
        count_statement = count_statement.where(f)
        statement = statement.where(f)
    col = _SORT_FIELDS.get(sort_by, Host.name)
    # id breaks ties so pages never overlap or skip rows.
    order = (
        (desc(col), desc(Host.id)) if sort_order == "desc" else (asc(col), asc(Host.id))
    )
    count = session.exec(count_statement).one()
    rows = session.exec(statement.order_by(*order).offset(skip).limit(limit)).all()

    return HostsPublic(data=[_host_for_user(h, current_user) for h in rows], count=count)


@router.post(
    "/",
    dependencies=[Depends(require_primary_node)],
    response_model=HostPublic,
)
def create_host(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    host_in: HostCreate,
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

    try:
        host = hosts.create_host(session=session, host_create=host_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_logs_crud.log_entity_action(
        session=session,
        action="CREATE",
        entity_type="Host",
        entity_id=str(host.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=host.model_dump_json(exclude=_SENSITIVE),
    )
    return host


@router.get("/{id}", response_model=HostPublic)
def read_host_by_id(
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    """
    Get a specific host by id.
    """
    host = session.get(Host, id)
    if not host:
        raise HTTPException(status_code=404, detail="Host not found")
    return _host_for_user(host, current_user)


@router.put(
    "/{id}",
    dependencies=[Depends(require_primary_node)],
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
    try:
        db_host = hosts.update_host(session=session, db_host=db_host, host_in=host_in)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    audit_logs_crud.log_entity_action(
        session=session,
        action="UPDATE",
        entity_type="Host",
        entity_id=str(db_host.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_host.model_dump_json(exclude=_SENSITIVE),
    )
    return db_host


@router.delete(
    "/{id}",
    dependencies=[Depends(require_primary_node)],
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
    delete_error = hosts.check_can_delete(session=session, host=host)
    if delete_error:
        raise HTTPException(status_code=400, detail=delete_error)

    old_values = host.model_dump_json(exclude=_SENSITIVE)
    session.delete(host)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session,
        action="DELETE",
        entity_type="Host",
        entity_id=str(id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="Host deleted successfully")
