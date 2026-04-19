import re
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import col, delete, func, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    SuperUser,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.crud import audit_logs as audit_logs_crud
from app.crud import users
from app.models import (
    Item,
    Message,
    UpdatePassword,
    User,
    UserCreate,
    UserPublic,
    UserRegister,
    UsersPublic,
    UserUpdate,
    UserUpdateMe,
)
from app.utils import generate_new_account_email, send_email

router = APIRouter(prefix="/users", tags=["users"])

_SENSITIVE = audit_logs_crud._SENSITIVE


def validate_password_pci_dss(password: str) -> None:
    """
    Validates a password against PCI DSS v4.0.1 requirements.
    - Minimum 12 characters.
    - Contains at least one lowercase letter, one uppercase letter, one number, and one special character.
    """
    if len(password) < 12:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 12 characters long.",
        )

    errors = []
    if not re.search(r"[a-z]", password):
        errors.append("one lowercase letter")
    if not re.search(r"[A-Z]", password):
        errors.append("one uppercase letter")
    if not re.search(r"[0-9]", password):
        errors.append("one number")
    # OWASP recommended special characters: !"#$%&'()*+,-./:;<=>?@[\]^_`{|}~
    if not re.search(r"[!\"#$%&'()*+,-./:;<=>?@\[\\\]^_`{|}~]", password):
        errors.append("one special character")

    if errors:
        raise HTTPException(
            status_code=400,
            detail=f"Password must contain at least {', '.join(errors)}.",
        )


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=UsersPublic,
)
def read_users(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve users.
    """

    count_statement = select(func.count()).select_from(User)
    count = session.exec(count_statement).one()

    statement = select(User).offset(skip).limit(limit)
    users = session.exec(statement).all()

    return UsersPublic(data=users, count=count)


@router.post("/", response_model=UserPublic)
def create_user(
    *, session: SessionDep, current_user: SuperUser, request: Request, user_in: UserCreate
) -> Any:
    """
    Create new user.
    """
    user = users.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    validate_password_pci_dss(user_in.password)

    user = users.create_user(session=session, user_create=user_in)
    if settings.emails_enabled and user_in.email:
        email_data = generate_new_account_email(
            email_to=user_in.email, username=user_in.email, password=user_in.password
        )
        send_email(
            email_to=user_in.email,
            subject=email_data.subject,
            html_content=email_data.html_content,
        )
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="User",
        entity_id=str(user.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        new_values=user.model_dump_json(exclude=_SENSITIVE),
    )
    return user


@router.patch("/me", response_model=UserPublic)
def update_user_me(
    *, session: SessionDep, request: Request, user_in: UserUpdateMe, current_user: CurrentUser
) -> Any:
    """
    Update own user.
    """

    if user_in.email:
        existing_user = users.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )
    old_values = current_user.model_dump_json(exclude=_SENSITIVE)
    user_data = user_in.model_dump(exclude_unset=True)
    current_user.sqlmodel_update(user_data)
    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="User",
        entity_id=str(current_user.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=current_user.model_dump_json(exclude=_SENSITIVE),
    )
    return current_user


@router.patch("/me/password", response_model=Message)
def update_password_me(
    *, session: SessionDep, request: Request, body: UpdatePassword, current_user: CurrentUser
) -> Any:
    """
    Update own password.
    """
    if not verify_password(body.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect password")
    if body.current_password == body.new_password:
        raise HTTPException(
            status_code=400, detail="New password cannot be the same as the current one"
        )

    validate_password_pci_dss(body.new_password)
    hashed_password = get_password_hash(body.new_password)
    current_user.hashed_password = hashed_password
    session.add(current_user)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="User",
        entity_id=str(current_user.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        description="Password updated",
    )
    return Message(message="Password updated successfully")


@router.get("/me", response_model=UserPublic)
def read_user_me(current_user: CurrentUser) -> Any:
    """
    Get current user.
    """
    return current_user


@router.delete("/me", response_model=Message)
def delete_user_me(
    session: SessionDep, request: Request, current_user: CurrentUser
) -> Any:
    """
    Delete own user.
    """
    if current_user.is_superuser:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    old_values = current_user.model_dump_json(exclude=_SENSITIVE)
    user_id = current_user.id
    user_email = current_user.email
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    session.delete(current_user)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="User",
        entity_id=str(user_id),
        user_id=user_id, user_email=user_email,
        ip_address=ip, user_agent=ua,
        old_values=old_values,
    )
    return Message(message="User deleted successfully")


@router.post("/signup", response_model=UserPublic)
def register_user(session: SessionDep, user_in: UserRegister) -> Any:
    """
    Create new user without the need to be logged in.
    """
    if not settings.USERS_OPEN_REGISTRATION:
        raise HTTPException(
            status_code=400,
            detail="Open user registration is forbidden on this server",
        )
    user = users.get_user_by_email(session=session, email=user_in.email)
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system",
        )

    validate_password_pci_dss(user_in.password)
    user_create = UserCreate.model_validate(user_in)
    user = users.create_user(session=session, user_create=user_create)
    return user


@router.get("/{user_id}", response_model=UserPublic)
def read_user_by_id(
    user_id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    """
    Get a specific user by id.
    """
    user = session.get(User, user_id)
    if user == current_user:
        return user
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=403,
            detail="The user doesn't have enough privileges",
        )
    return user


@router.patch(
    "/{user_id}",
    response_model=UserPublic,
)
def update_user(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    user_id: uuid.UUID,
    user_in: UserUpdate,
) -> Any:
    """
    Update a user.
    """

    db_user = session.get(User, user_id)
    if not db_user:
        raise HTTPException(
            status_code=404,
            detail="The user with this id does not exist in the system",
        )
    if user_in.email:
        existing_user = users.get_user_by_email(session=session, email=user_in.email)
        if existing_user and existing_user.id != user_id:
            raise HTTPException(
                status_code=409, detail="User with this email already exists"
            )

    if user_in.password:
        validate_password_pci_dss(user_in.password)

    old_values = db_user.model_dump_json(exclude=_SENSITIVE)
    db_user = users.update_user(session=session, db_user=db_user, user_in=user_in)
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="User",
        entity_id=str(db_user.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_user.model_dump_json(exclude=_SENSITIVE),
    )
    return db_user


@router.delete("/{user_id}", dependencies=[Depends(get_current_active_superuser)])
def delete_user(
    session: SessionDep, request: Request, current_user: CurrentUser, user_id: uuid.UUID
) -> Message:
    """
    Delete a user.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user == current_user:
        raise HTTPException(
            status_code=403, detail="Super users are not allowed to delete themselves"
        )
    old_values = user.model_dump_json(exclude=_SENSITIVE)
    statement = delete(Item).where(col(Item.owner_id) == user_id)
    session.exec(statement)  # type: ignore
    session.delete(user)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="User",
        entity_id=str(user_id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="User deleted successfully")
