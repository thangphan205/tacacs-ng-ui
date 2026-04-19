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
from app.crud import tacacs_services
from app.models import (
    Message,
    TacacsService,
    TacacsServiceCreate,
    TacacsServicePublic,
    TacacsServicesPublic,
    TacacsServiceUpdate,
)

router = APIRouter(prefix="/tacacs_services", tags=["tacacs_services"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsServicesPublic,
)
def read_tacacs_services(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve tacacs_services.
    """

    count_statement = select(func.count()).select_from(TacacsService)
    count = session.exec(count_statement).one()

    statement = select(TacacsService).offset(skip).limit(limit)
    tacacs_services = session.exec(statement).all()

    return TacacsServicesPublic(data=tacacs_services, count=count)


@router.post(
    "/",
    response_model=TacacsServicePublic,
)
def create_tacacs_service(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    tacacs_service_in: TacacsServiceCreate,
) -> Any:
    """
    Create new tacacs_service.
    """

    tacacs_service = tacacs_services.get_tacacs_service_by_name(
        session=session, name=tacacs_service_in.name
    )
    if tacacs_service:
        raise HTTPException(
            status_code=400,
            detail="The tacacs_service with this tacacs_service name already exists in the system.",
        )

    tacacs_service = tacacs_services.create_tacacs_service(
        session=session, tacacs_service_create=tacacs_service_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="TacacsService",
        entity_id=str(tacacs_service.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        new_values=tacacs_service.model_dump_json(exclude=_SENSITIVE),
    )
    return tacacs_service


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsServicePublic,
)
def read_tacacs_service_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific tacacs_service by id.
    """

    tacacs_service = session.get(TacacsService, id)
    if not tacacs_service:
        raise HTTPException(status_code=404, detail="TacacsService not found")
    return tacacs_service


@router.put(
    "/{id}",
    response_model=TacacsServicePublic,
)
def update_tacacs_service(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    tacacs_service_in: TacacsServiceUpdate,
) -> Any:
    """
    Update a tacacs_service.
    """

    db_tacacs_service = session.get(TacacsService, id)
    if not db_tacacs_service:
        raise HTTPException(
            status_code=404,
            detail="The tacacs_service with this id does not exist in the system",
        )
    old_values = db_tacacs_service.model_dump_json(exclude=_SENSITIVE)
    db_tacacs_service = tacacs_services.update_tacacs_service(
        session=session,
        db_tacacs_service=db_tacacs_service,
        tacacs_service_in=tacacs_service_in,
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="TacacsService",
        entity_id=str(db_tacacs_service.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_tacacs_service.model_dump_json(exclude=_SENSITIVE),
    )
    return db_tacacs_service


@router.delete(
    "/{id}",
)
def delete_tacacs_service(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a TACACS service.
    """

    tacacs_service = session.get(TacacsService, id)
    if not tacacs_service:
        raise HTTPException(status_code=404, detail="TacacsService not found")
    old_values = tacacs_service.model_dump_json(exclude=_SENSITIVE)
    session.delete(tacacs_service)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="TacacsService",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="TacacsService deleted successfully")
