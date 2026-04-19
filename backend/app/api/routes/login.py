import json
from datetime import timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.security import OAuth2PasswordRequestForm

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_client_ip,
    get_current_active_superuser,
)
from app.core import security
from app.core.config import settings
from app.core.security import get_password_hash
from app.crud import audit_logs as audit_logs_crud
from app.crud import auth_providers as auth_providers_crud
from app.crud import users
from app.models import AuditLogCreate, Message, NewPassword, Token, UserPublic
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


@router.post("/login/access-token")
def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    ip = get_client_ip(request)

    user = users.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        audit_logs_crud.create_audit_log(
            session=session,
            audit_log_in=AuditLogCreate(
                action="LOGIN_FAILED",
                entity_type="User",
                entity_id=form_data.username,
                description="Incorrect email or password",
                user_agent=request.headers.get("user-agent"),
            ),
            user_id=None,
            user_email=form_data.username,
            ip_address=ip,
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Check admin-level global password login disable
    passkey_cfg = auth_providers_crud.get_provider_config(session=session, provider="passkey")
    if passkey_cfg and passkey_cfg.enabled:
        cfg = json.loads(passkey_cfg.config_json)
        if cfg.get("allow_password_login") == "false":
            raise HTTPException(
                status_code=400,
                detail="Password login has been disabled by the administrator.",
            )

    # Check per-user password login disable
    if user.password_login_disabled:
        raise HTTPException(
            status_code=400,
            detail="Password login is disabled for this account. Use a passkey to sign in.",
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    audit_logs_crud.create_audit_log(
        session=session,
        audit_log_in=AuditLogCreate(
            action="LOGIN_SUCCESS",
            entity_type="User",
            entity_id=str(user.id),
            description="Password login",
            user_agent=request.headers.get("user-agent"),
        ),
        user_id=user.id,
        user_email=user.email,
        ip_address=ip,
    )
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=access_token_expires
        )
    )


@router.post("/login/test-token", response_model=UserPublic)
def test_token(current_user: CurrentUser) -> Any:
    """
    Test access token
    """
    return current_user


@router.post("/password-recovery/{email}")
def recover_password(email: str, session: SessionDep) -> Message:
    """
    Password Recovery
    """
    user = users.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )
    send_email(
        email_to=user.email,
        subject=email_data.subject,
        html_content=email_data.html_content,
    )
    return Message(message="Password recovery email sent")


@router.post("/reset-password/")
def reset_password(session: SessionDep, body: NewPassword) -> Message:
    """
    Reset password
    """
    email = verify_password_reset_token(token=body.token)
    if not email:
        raise HTTPException(status_code=400, detail="Invalid token")
    user = users.get_user_by_email(session=session, email=email)
    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this email does not exist in the system.",
        )
    elif not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    hashed_password = get_password_hash(password=body.new_password)
    user.hashed_password = hashed_password
    session.add(user)
    session.commit()
    return Message(message="Password updated successfully")


@router.post(
    "/password-recovery-html-content/{email}",
    dependencies=[Depends(get_current_active_superuser)],
    response_class=HTMLResponse,
)
def recover_password_html_content(email: str, session: SessionDep) -> Any:
    """
    HTML Content for Password Recovery
    """
    user = users.get_user_by_email(session=session, email=email)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="The user with this username does not exist in the system.",
        )
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
