import threading
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


_FAILOVER_AUDIT_WINDOW = timedelta(minutes=15)

# Audit-log wording for each `get_or_create_ldap_user` refusal.
_LINK_REFUSALS: dict[str, str] = {
    users.LDAP_EMAIL_LINK_OFF: "a local account uses that email and email linking is off",
    users.LDAP_SUPERUSER: "the account with that email is a superuser",
    users.LDAP_LINKED_ELSEWHERE: "that account is linked to another directory entry",
    users.LDAP_OPEN_REGISTRATION: (
        "email linking is refused while USERS_OPEN_REGISTRATION is on"
    ),
    users.LDAP_RESERVED_ID: "the directory identifier uses the reserved relink: prefix",
}

_LDAP_ACCOUNT_DETAIL = (
    "This account signs in with LDAP. Use the LDAP tab; its password is "
    "managed in the directory."
)


_USERNAME_MAX = 255  # AuditLog.user_email / entity_id column width
_IP_MAX = 45  # AuditLog.ip_address column width
_UA_MAX = 512  # AuditLog.user_agent column width

# Directory round trips block a threadpool thread for up to connect_timeout per
# server. With the directory down, a flood of sign-ins would fill the pool and
# stall every other sync route, the local emergency login included. Cap the
# ones in flight per worker; the rest are refused at once (no thread is held,
# no audit row is written per request). Sized lazily so tests can change it.
_ldap_slots: threading.BoundedSemaphore | None = None
_ldap_slots_size = 0
_ldap_slots_lock = threading.Lock()


def _ldap_semaphore() -> threading.BoundedSemaphore:
    global _ldap_slots, _ldap_slots_size
    size = max(1, settings.LDAP_MAX_CONCURRENT_SIGNINS)
    with _ldap_slots_lock:
        if _ldap_slots is None or _ldap_slots_size != size:
            _ldap_slots, _ldap_slots_size = threading.BoundedSemaphore(size), size
        return _ldap_slots


def _norm_username(username: str) -> str:
    """One spelling per account: directory names are case-insensitive, and the
    audit columns are bounded (an over-long value would 500 the failure write
    and so never be counted)."""
    return username.strip().lower()[:_USERNAME_MAX]


def _ua(user_agent: str | None) -> str | None:
    """Bounded to the audit column: an over-long header would make the audit
    write raise, so the failure is never recorded (or counted) and a correct
    password answers 500."""
    return user_agent[:_UA_MAX] if user_agent else None


def _login_client_ip(request: Request) -> str | None:
    """Client address for throttling and audit rows, bounded to the column."""
    ip = get_client_ip(request)
    return ip[:_IP_MAX] if ip else None


def _audit_login_failure(
    session: SessionDep,
    *,
    username: str,
    description: str,
    user_agent: str | None,
    ip: str | None,
    action: str = "LOGIN_FAILED",
) -> None:
    username = _norm_username(username)
    audit_logs_crud.create_audit_log(
        session=session,
        audit_log_in=AuditLogCreate(
            action=action,
            entity_type="User",
            entity_id=username,
            description=description[:1024],
            user_agent=_ua(user_agent),
        ),
        user_id=None,
        user_email=username,
        ip_address=ip,
    )


def _audit_login_success(
    session: SessionDep,
    *,
    user: User,
    description: str,
    user_agent: str | None,
    ip: str | None,
) -> None:
    audit_logs_crud.create_audit_log(
        session=session,
        audit_log_in=AuditLogCreate(
            action="LOGIN_SUCCESS",
            entity_type="User",
            entity_id=str(user.id),
            description=description,
            user_agent=_ua(user_agent),
        ),
        user_id=user.id,
        user_email=user.email,
        ip_address=ip,
    )
    users.record_last_login(session=session, user_id=user.id)


def _audit_ldap_failover(
    session: SessionDep,
    *,
    outcome_server: str | None,
    failed_servers: list[tuple[str, str]],
    username: str,
    user_agent: str | None,
    ip: str | None,
) -> None:
    """Record a failover once per state per window, not once per sign-in.

    A server down for a day would otherwise write (and ship to the SIEM) one
    identical row for every login.
    """
    failed_summary = ", ".join(srv for srv, _ in failed_servers)
    description = (
        f"LDAP server failover from [{failed_summary}] to {outcome_server}"
        if outcome_server
        else f"All LDAP servers unreachable: [{failed_summary}]"
    )[:1024]
    # Lock first: with 4 workers, the check and the insert below could
    # otherwise both pass in several of them at once.
    audit_logs_crud.lock_audit_dedupe(session)
    if audit_logs_crud.recent_audit_log_exists(
        session=session,
        action="LDAP_FAILOVER",
        description=description,
        within=_FAILOVER_AUDIT_WINDOW,
    ):
        return
    audit_logs_crud.create_audit_log(
        session=session,
        audit_log_in=AuditLogCreate(
            action="LDAP_FAILOVER",
            entity_type="AuthProviderConfig",
            entity_id="ldap",
            description=description,
            user_agent=_ua(user_agent),
        ),
        user_id=None,
        user_email=_norm_username(username),
        ip_address=ip,
    )


def _token_for(user: User) -> Token:
    minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    if user.ldap_id:
        # Never re-checked against the directory, so removal there takes
        # effect only when the token expires: keep it shorter.
        minutes = min(minutes, settings.LDAP_ACCESS_TOKEN_EXPIRE_MINUTES)
    return Token(
        access_token=security.create_access_token(
            user.id, expires_delta=timedelta(minutes=minutes)
        )
    )


def _throttle_login(
    session: SessionDep, *, username: str, ip: str | None, by_user: bool
) -> None:
    """429 once too many LOGIN_FAILED rows exist for this client or username.

    Per client address on both endpoints; per (username, client address) on
    the LDAP endpoint only, since every LDAP attempt reaches the directory and
    may trip its lockout policy. Keyed on the pair so a stranger elsewhere
    cannot lock a known user out, and never on a *local* username (that would
    lock the emergency administrator out).
    """
    window = timedelta(minutes=settings.LOGIN_THROTTLE_WINDOW_MINUTES)
    limits: list[tuple[int, dict[str, str | None]]] = [
        (settings.LOGIN_THROTTLE_MAX_FAILURES_PER_IP, {"ip_address": ip}),
    ]
    # Without a client address the pair key would degrade to the username
    # alone, counting that name's failures from every address: anyone could
    # then lock a known directory user out. Skip it; the per-address key
    # (also skipped, as all-None) cannot help either.
    if by_user and ip is not None:
        limits.append(
            (
                settings.LOGIN_THROTTLE_MAX_FAILURES_PER_USER,
                {"user_email": _norm_username(username), "ip_address": ip},
            )
        )
    for limit, key in limits:
        if limit <= 0 or all(v is None for v in key.values()):
            continue
        if (
            audit_logs_crud.count_recent_failed_logins(
                session=session, within=window, **key
            )
            >= limit
        ):
            raise HTTPException(
                status_code=429,
                detail="Too many failed sign-in attempts. Try again later.",
                headers={"Retry-After": str(int(window.total_seconds()))},
            )


@router.post("/login/access-token")
def login_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Local account sign-in (email + password). Never contacts LDAP.

    LDAP has its own endpoint, so a local password — or a typo of one — is
    never sent to the directory.
    """
    ip = _login_client_ip(request)
    user_agent = request.headers.get("user-agent")

    _throttle_login(session, username=form_data.username, ip=ip, by_user=False)
    user = users.authenticate(
        session=session, email=form_data.username, password=form_data.password
    )
    if not user:
        _audit_login_failure(
            session,
            username=form_data.username,
            description="Incorrect email or password",
            user_agent=user_agent,
            ip=ip,
        )
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    if not user.is_active:
        _audit_login_failure(
            session,
            username=form_data.username,
            description="Password login refused: inactive user",
            user_agent=user_agent,
            ip=ip,
        )
        raise HTTPException(status_code=400, detail="Inactive user")
    if not auth_providers_crud.password_login_allowed(session=session):
        raise HTTPException(
            status_code=400,
            detail="Password login has been disabled by the administrator.",
        )
    if user.password_login_disabled:
        raise HTTPException(
            status_code=400,
            detail="Password login is disabled for this account. Use a passkey to sign in.",
        )
    if user.ldap_id:
        # A directory account must keep going through the directory, so
        # removing it there (or from the Required Group) removes access here.
        _audit_login_failure(
            session,
            username=form_data.username,
            description="Local password login refused for an LDAP account",
            user_agent=user_agent,
            ip=ip,
        )
        raise HTTPException(status_code=400, detail=_LDAP_ACCOUNT_DETAIL)

    _audit_login_success(
        session, user=user, description="Password login", user_agent=user_agent, ip=ip
    )
    return _token_for(user)


@router.post("/login/ldap/access-token")
def login_ldap_access_token(
    request: Request,
    session: SessionDep,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """LDAP / Active Directory sign-in (directory username + password).

    Governed only by the LDAP provider's Enable switch: the passkey-only
    switches ("allow password login", per-user ``password_login_disabled``)
    restrict local passwords, not directory accounts.
    """
    ip = _login_client_ip(request)
    user_agent = request.headers.get("user-agent")

    def _fail(description: str, action: str = "LOGIN_FAILED") -> None:
        _audit_login_failure(
            session,
            username=form_data.username,
            description=description,
            user_agent=user_agent,
            ip=ip,
            action=action,
        )

    ldap_enabled, ldap_cfg, ldap_secret = auth_providers_crud.ldap_login_settings(
        session=session
    )
    if not ldap_enabled:
        raise HTTPException(status_code=400, detail="LDAP sign-in is not enabled")
    _throttle_login(session, username=form_data.username, ip=ip, by_user=True)

    effective = build_effective_ldap_config(ldap_cfg, ldap_secret)
    # The reads above opened a transaction and checked a connection out of the
    # pool. The directory call below blocks for up to connect_timeout per
    # server, so end it first: otherwise, with the directory down, every
    # in-flight sign-in (LDAP_MAX_CONCURRENT_SIGNINS per worker) pins a pooled
    # connection idle in transaction and starves unrelated requests, the local
    # emergency login included. The session reconnects on its next use.
    session.commit()
    slots = _ldap_semaphore()
    if not slots.acquire(blocking=False):
        raise HTTPException(
            status_code=503,
            detail="Too many LDAP sign-ins in progress. Try again shortly.",
            headers={"Retry-After": "5"},
        )
    try:
        outcome = authenticate_ldap_user(
            username=form_data.username,
            password=form_data.password,
            raw_config=ldap_cfg,
            secret=ldap_secret,
            effective=effective,
        )
    finally:
        slots.release()
    if outcome.failed_servers:
        _audit_ldap_failover(
            session,
            outcome_server=outcome.server_used,
            failed_servers=outcome.failed_servers,
            username=form_data.username,
            user_agent=user_agent,
            ip=ip,
        )

    if outcome.ok and outcome.identity is not None:
        ldap_user, refusal = users.get_or_create_ldap_user(
            session=session,
            ldap_id=outcome.identity.ldap_id,
            email=outcome.identity.email,
            full_name=outcome.identity.full_name,
            allow_email_link=effective.allow_email_link,
            username=outcome.identity.username,
        )
        if ldap_user is None:
            ident = outcome.identity
            if refusal == users.LDAP_NEW_ON_STANDBY:
                _fail(
                    f"LDAP user {ident.ldap_id} has no account yet; first "
                    "sign-in must happen on the primary"
                )
                raise HTTPException(
                    status_code=403,
                    detail="First sign-in with this directory account must be on the primary node.",
                )
            _fail(
                f"LDAP identity {ident.ldap_id} not linked to {ident.email}: "
                f"{_LINK_REFUSALS.get(refusal or '', refusal)}"
            )
            if refusal == users.LDAP_RESERVED_ID:
                raise HTTPException(
                    status_code=403,
                    detail="This directory account cannot sign in here. Ask an administrator.",
                )
            raise HTTPException(
                status_code=403,
                detail=(
                    "A local account already uses this directory account's email "
                    "address. Ask an administrator."
                ),
            )
        if not ldap_user.is_active:
            _fail(f"LDAP sign-in refused: {ldap_user.email} is inactive")
            raise HTTPException(status_code=400, detail="Inactive user")

        _audit_login_success(
            session,
            user=ldap_user,
            description=f"LDAP login via {outcome.server_used}",
            user_agent=user_agent,
            ip=ip,
        )
        return _token_for(ldap_user)

    # The detail stays in the audit log; the client gets as little as it needs.
    # A server-side fault is not a failed login: LOGIN_FAILED rows feed the
    # throttle, which would lock users (and the local admin, per client
    # address) out for as long as the directory is down. It is recorded as
    # LOGIN_ERROR, once per distinct message per window: unlike a failed login
    # nothing else bounds it, so a loop against a down directory would write
    # (and ship to the SIEM) a row per request and push real history out of the
    # table. No advisory lock here -- a race writes at most a few extra rows
    # (bounded by LDAP_MAX_CONCURRENT_SIGNINS), and a lock held to the end of
    # the request would serialise every sign-in during an outage.
    description = f"LDAP {outcome.reason}: {outcome.message}"
    if outcome.reason in ("unavailable", "misconfigured"):
        if not audit_logs_crud.recent_audit_log_exists(
            session=session,
            action="LOGIN_ERROR",
            description=description[:1024],
            within=_FAILOVER_AUDIT_WINDOW,
        ):
            _fail(description, action="LOGIN_ERROR")
    else:
        _fail(description)
    if outcome.reason == "group_denied":
        raise HTTPException(
            status_code=403,
            detail="Your directory account is not authorized to sign in.",
        )
    if outcome.reason == "no_email":
        raise HTTPException(status_code=403, detail=outcome.message)
    if outcome.reason == "unavailable":
        raise HTTPException(status_code=503, detail=outcome.message)
    if outcome.reason == "misconfigured":
        # Not "wrong password": users would keep retrying and could lock out
        # their directory accounts while the fault is the server's.
        raise HTTPException(
            status_code=503,
            detail="LDAP sign-in is misconfigured. Contact an administrator.",
        )
    raise HTTPException(status_code=400, detail="Incorrect username or password")


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
    if user.ldap_id:
        raise HTTPException(status_code=400, detail=_LDAP_ACCOUNT_DETAIL)
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
    if user.ldap_id:
        # A token issued before the account was linked to LDAP.
        raise HTTPException(status_code=400, detail=_LDAP_ACCOUNT_DETAIL)
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
    if user.ldap_id:
        raise HTTPException(status_code=400, detail=_LDAP_ACCOUNT_DETAIL)
    password_reset_token = generate_password_reset_token(email=email)
    email_data = generate_reset_password_email(
        email_to=user.email, email=email, token=password_reset_token
    )

    return HTMLResponse(
        content=email_data.html_content, headers={"subject:": email_data.subject}
    )
