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
from app.core.ldap_auth import authenticate_ldap_user, build_effective_ldap_config
from app.core.security import get_password_hash
from app.crud import audit_logs as audit_logs_crud
from app.crud import auth_providers as auth_providers_crud
from app.crud import users
from app.models import (
    AuditLogCreate,
    Message,
    NewPassword,
    Token,
    User,
    UserPublic,
)
from app.utils import (
    generate_password_reset_token,
    generate_reset_password_email,
    send_email,
    verify_password_reset_token,
)

router = APIRouter(tags=["login"])


def _ldap_provider_creds(
    session: SessionDep,
) -> tuple[bool, dict[str, Any], str | None]:
    row = auth_providers_crud.get_provider_config(session=session, provider="ldap")
    if row is not None:
        if not row.enabled:
            return False, {}, None
        try:
            cfg = json.loads(row.config_json or "{}")
        except ValueError:
            cfg = {}
        try:
            secret = auth_providers_crud.resolve_provider_secret(row)
        except Exception:
            secret = None
        return True, cfg, secret
    if settings.LDAP_HOSTS:
        return True, {}, settings.LDAP_BIND_PASSWORD or None
    return False, {}, None


_GLOBAL_PASSWORD_LOGIN_OFF = "Password login has been disabled by the administrator."


def _global_password_login_disabled(session: SessionDep) -> bool:
    passkey_cfg = auth_providers_crud.get_provider_config(
        session=session, provider="passkey"
    )
    if passkey_cfg and passkey_cfg.enabled:
        cfg = json.loads(passkey_cfg.config_json)
        return bool(cfg.get("allow_password_login") == "false")
    return False


def _check_password_login_allowed(session: SessionDep, user: User) -> None:
    """Apply the passkey-only switches to any password-based sign-in.

    LDAP is a password login too: skipping these on that path would let a
    directory password sign in to an account an administrator restricted to
    passkeys.
    """
    if _global_password_login_disabled(session):
        raise HTTPException(status_code=400, detail=_GLOBAL_PASSWORD_LOGIN_OFF)
    if user.password_login_disabled:
        raise HTTPException(
            status_code=400,
            detail="Password login is disabled for this account. Use a passkey to sign in.",
        )


@router.post("/login/access-token")
def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    def _audit_failure(description: str) -> None:
        audit_logs_crud.create_audit_log(
            session=session,
            audit_log_in=AuditLogCreate(
                action="LOGIN_FAILED",
                entity_type="User",
                entity_id=form_data.username,
                description=description[:1024],
                user_agent=user_agent,
            ),
            user_id=None,
            user_email=form_data.username,
            ip_address=ip,
        )

    # 1. Local password authentication first (ensures local emergency admin
    # accounts remain accessible even if external LDAP servers are unreachable).
    user = users.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if user:
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        _check_password_login_allowed(session, user)

        audit_logs_crud.create_audit_log(
            session=session,
            audit_log_in=AuditLogCreate(
                action="LOGIN_SUCCESS",
                entity_type="User",
                entity_id=str(user.id),
                description="Password login",
                user_agent=user_agent,
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

    # 2. If local authentication did not match, attempt LDAP authentication when enabled.
    ldap_enabled, ldap_cfg, ldap_secret = _ldap_provider_creds(session)
    if not ldap_enabled:
        _audit_failure("Incorrect email or password")
        raise HTTPException(status_code=400, detail="Incorrect email or password")

    # Passkey-only mode: do not even send the password to the directory.
    if _global_password_login_disabled(session):
        raise HTTPException(status_code=400, detail=_GLOBAL_PASSWORD_LOGIN_OFF)

    outcome = authenticate_ldap_user(
        username=form_data.username,
        password=form_data.password,
        raw_config=ldap_cfg,
        secret=ldap_secret,
    )
    if outcome.failed_servers:
        failed_summary = ", ".join(f"{srv}" for srv, _ in outcome.failed_servers)
        failover_desc = (
            f"LDAP server failover from [{failed_summary}] to {outcome.server_used}"
            if outcome.server_used
            else f"All LDAP servers unreachable: [{failed_summary}]"
        )
        audit_logs_crud.create_audit_log(
            session=session,
            audit_log_in=AuditLogCreate(
                action="LDAP_FAILOVER",
                entity_type="AuthProviderConfig",
                entity_id="ldap",
                description=failover_desc[:1024],
                user_agent=user_agent,
            ),
            user_id=None,
            user_email=form_data.username,
            ip_address=ip,
        )

    if outcome.ok and outcome.identity is not None:
        ldap_user = users.get_or_create_ldap_user(
            session=session,
            ldap_id=outcome.identity.ldap_id,
            email=outcome.identity.email,
            full_name=outcome.identity.full_name,
            allow_email_link=build_effective_ldap_config(
                ldap_cfg, ldap_secret
            ).allow_email_link,
        )
        if ldap_user is None:
            if settings.NODE_ROLE == "standby":
                _audit_failure(
                    f"LDAP user {outcome.identity.ldap_id} has no account yet; "
                    "first sign-in must happen on the primary"
                )
                raise HTTPException(
                    status_code=403,
                    detail="First sign-in with this directory account must be on the primary node.",
                )
            _audit_failure(
                f"LDAP identity {outcome.identity.ldap_id} not linked: a local "
                f"account already uses {outcome.identity.email} (email linking is "
                "off or the account is a superuser)"
            )
            raise HTTPException(
                status_code=403,
                detail=(
                    "A local account already uses this directory account's email "
                    "address. Ask an administrator."
                ),
            )
        if not ldap_user.is_active:
            raise HTTPException(status_code=400, detail="Inactive user")
        _check_password_login_allowed(session, ldap_user)

        audit_logs_crud.create_audit_log(
            session=session,
            audit_log_in=AuditLogCreate(
                action="LOGIN_SUCCESS",
                entity_type="User",
                entity_id=str(ldap_user.id),
                description=f"LDAP login via {outcome.server_used}",
                user_agent=user_agent,
            ),
            user_id=ldap_user.id,
            user_email=ldap_user.email,
            ip_address=ip,
        )
        return Token(
            access_token=security.create_access_token(
                ldap_user.id, expires_delta=access_token_expires
            )
        )

    # The detail stays in the audit log; the client gets as little as it needs.
    _audit_failure(f"LDAP {outcome.reason}: {outcome.message}")
    if outcome.reason == "group_denied":
        raise HTTPException(
            status_code=403,
            detail="Your directory account is not authorized to sign in.",
        )
    if outcome.reason == "no_email":
        raise HTTPException(status_code=403, detail=outcome.message)
    if outcome.reason == "unavailable":
        raise HTTPException(status_code=503, detail=outcome.message)
    raise HTTPException(status_code=400, detail="Incorrect email or password")


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
