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
from app.crud import tacacs_users
from app.models import (
    Message,
    TacacsUser,
    TacacsUserCreate,
    TacacsUserPublic,
    TacacsUsersPublic,
    TacacsUserUpdate,
)

router = APIRouter(prefix="/tacacs_users", tags=["tacacs_users"])

_SENSITIVE = audit_logs_crud._SENSITIVE


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
    response_model=TacacsUserPublic,
)
def create_tacacs_user(
    *, session: SessionDep, current_user: SuperUser, request: Request, user_in: TacacsUserCreate
) -> Any:
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
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="TacacsUser",
        entity_id=str(user.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=user.model_dump_json(exclude=_SENSITIVE),
    )
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
    response_model=TacacsUserPublic,
)
def update_tacacs_user(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
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

    old_values = db_user.model_dump_json(exclude=_SENSITIVE)
    db_user = tacacs_users.update_tacacs_user(
        session=session, db_user=db_user, user_in=user_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="TacacsUser",
        entity_id=str(db_user.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_user.model_dump_json(exclude=_SENSITIVE),
    )
    return db_user


@router.delete(
    "/{id}",
)
def delete_tacacs_user(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a TACACS user.
    """

    tacacs_user = session.get(TacacsUser, id)
    if not tacacs_user:
        raise HTTPException(status_code=404, detail="TACACS user not found")
    old_values = tacacs_user.model_dump_json(exclude=_SENSITIVE)
    session.delete(tacacs_user)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="TacacsUser",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="TACACS user deleted successfully")
