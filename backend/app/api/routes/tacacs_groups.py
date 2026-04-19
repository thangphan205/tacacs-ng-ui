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
from app.crud import tacacs_groups
from app.models import (
    Message,
    TacacsGroup,
    TacacsGroupCreate,
    TacacsGroupPublic,
    TacacsGroupsPublic,
    TacacsGroupUpdate,
)

router = APIRouter(prefix="/tacacs_groups", tags=["tacacs_groups"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsGroupsPublic,
)
def read_tacacs_groups(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve groups.
    """

    count_statement = select(func.count()).select_from(TacacsGroup)
    count = session.exec(count_statement).one()

    statement = select(TacacsGroup).offset(skip).limit(limit)
    groups = session.exec(statement).all()

    return TacacsGroupsPublic(data=groups, count=count)


@router.post(
    "/",
    response_model=TacacsGroupPublic,
)
def create_tacacs_group(
    *, session: SessionDep, current_user: SuperUser, request: Request, group_in: TacacsGroupCreate
) -> Any:
    """
    Create new group.
    """

    group = tacacs_groups.get_tacacs_group_by_group_name(
        session=session, group_name=group_in.group_name
    )
    if group:
        raise HTTPException(
            status_code=400,
            detail="The group with this group name already exists in the system.",
        )

    group = tacacs_groups.create_tacacs_group(session=session, user_create=group_in)
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="TacacsGroup",
        entity_id=str(group.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=group.model_dump_json(exclude=_SENSITIVE),
    )
    return group


@router.get(
    "/{id}", dependencies=[Depends(get_current_user)], response_model=TacacsGroupPublic
)
def read_tacacs_group_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific group by id.
    """
    group = session.get(TacacsGroup, id)

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.put(
    "/{id}",
    response_model=TacacsGroupPublic,
)
def update_tacacs_group(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    group_in: TacacsGroupUpdate,
) -> Any:
    """
    Update a group.
    """

    db_tacacs_group = session.get(TacacsGroup, id)
    if not db_tacacs_group:
        raise HTTPException(
            status_code=404,
            detail="The group with this id does not exist in the system",
        )

    old_values = db_tacacs_group.model_dump_json(exclude=_SENSITIVE)
    db_tacacs_group = tacacs_groups.update_tacacs_group(
        session=session, db_tacacs_group=db_tacacs_group, group_in=group_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="TacacsGroup",
        entity_id=str(db_tacacs_group.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_tacacs_group.model_dump_json(exclude=_SENSITIVE),
    )
    return db_tacacs_group


@router.delete(
    "/{id}",
)
def delete_tacacs_group(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a group.
    """

    tacacs_group = session.get(TacacsGroup, id)
    if not tacacs_group:
        raise HTTPException(status_code=404, detail="Group not found")
    old_values = tacacs_group.model_dump_json(exclude=_SENSITIVE)
    session.delete(tacacs_group)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="TacacsGroup",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="Group deleted successfully")
