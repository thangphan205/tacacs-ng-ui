import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.crud import tacacs_users
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    TacacsUser,
    TacacsUserCreate,
    TacacsUserPublic,
    TacacsUsersPublic,
    TacacsUserUpdate,
)

router = APIRouter(prefix="/tacacs_users", tags=["tacacs_users"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsUsersPublic,
)
def read_tacacs_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(TacacsUser)
    count = session.exec(count_statement).one()

    statement = select(TacacsUser).offset(skip).limit(limit)
    users = session.exec(statement).all()

    return TacacsUsersPublic(data=users, count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TacacsUserPublic,
)
def create_tacacs_user(*, session: SessionDep, user_in: TacacsUserCreate) -> Any:
    """
    Create new user.
    """
    user = tacacs_users.get_tacacs_user_by_username(
        session=session, username=user_in.username
    )
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this username already exists in the system.",
        )

    user = tacacs_users.create_tacacs_user(session=session, user_create=user_in)
    return user


@router.get(
    "/{id}", dependencies=[Depends(get_current_user)], response_model=TacacsUserPublic
)
def read_tacacs_user_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(TacacsUser, id)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )

    return user


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=TacacsUserPublic,
)
def update_tacacs_user(
    *,
    session: SessionDep,
    id: uuid.UUID,
    user_in: TacacsUserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(TacacsUser, id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.username:
        existing_user = tacacs_users.get_tacacs_user_by_username(
            session=session, username=user_in.username
        )
        if existing_user and existing_user.id != id:
            raise HTTPException(
                status_code=409, detail="User with this username already exists"
            )

    db_user = tacacs_users.update_tacacs_user(
        session=session, db_user=db_user, user_in=user_in
    )
    return db_user


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_tacacs_user(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    tacacs_user = session.get(TacacsUser, id)
    if not tacacs_user:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(tacacs_user)
    session.commit()
    return Message(message="Item deleted successfully")
