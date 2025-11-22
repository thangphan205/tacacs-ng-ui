import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import col, delete, func, select

from app.crud import tacacs_groups
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    TacacsGroup,
    TacacsGroupCreate,
    TacacsGroupPublic,
    TacacsGroupsPublic,
    TacacsGroupUpdate,
)

router = APIRouter(prefix="/tacacs_groups", tags=["tacacs_groups"])


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
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TacacsGroupPublic,
)
def create_tacacs_group(*, session: SessionDep, group_in: TacacsGroupCreate) -> Any:
    """
    Create new group.
    """

    group = tacacs_groups.get_tacacs_group_by_group_name(
        session=session, group_name=group_in.group_name
    )
    if group:
        raise HTTPException(
            status_code=400,
            detail="The user with this group name already exists in the system.",
        )

    user = tacacs_groups.create_tacacs_group(session=session, user_create=group_in)
    return user


@router.get(
    "/{id}", dependencies=[Depends(get_current_user)], response_model=TacacsGroupPublic
)
def read_tacacs_group_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific user by id.
    """
    group = session.get(TacacsGroup, id)

    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TacacsGroupPublic,
)
def update_tacacs_group(
    *,
    session: SessionDep,
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
            detail="The user with this id does not exist in the system",
        )

    db_tacacs_group = tacacs_groups.update_tacacs_group(
        session=session, db_tacacs_group=db_tacacs_group, group_in=group_in
    )
    return db_tacacs_group


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_tacacs_group(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    tacacs_group = session.get(TacacsGroup, id)
    if not tacacs_group:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(tacacs_group)
    session.commit()
    return Message(message="Group deleted successfully")
