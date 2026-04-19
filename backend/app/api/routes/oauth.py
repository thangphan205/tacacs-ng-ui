import hashlib
import hmac
import time
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.api.deps import SessionDep
from app.core.config import settings
from app.core.security import create_access_token
from app.crud import audit_logs as audit_logs_crud
from app.crud.users import get_or_create_google_user, get_or_create_keycloak_user
from app.models import AuditLogCreate

router = APIRouter(prefix="/oauth", tags=["oauth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_SCOPES = "openid email profile"


def _make_state() -> str:
    ts = str(int(time.time()))
    sig = hmac.new(
        settings.SECRET_KEY.encode(),
        ts.encode(),
        hashlib.sha256,
    ).hexdigest()
    return f"{ts}.{sig}"


def _verify_state(state: str) -> bool:
    try:
        ts, sig = state.split(".", 1)
    except ValueError:
        return False
    if abs(time.time() - int(ts)) > 600:  # 10-minute window
        return False
    expected = hmac.new(
        settings.SECRET_KEY.encode(),
        ts.encode(),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(sig, expected)


@router.get("/google/authorize")
def google_authorize() -> dict[str, str]:
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")

    state = _make_state()
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": state,
        "access_type": "online",
    }
    url = GOOGLE_AUTH_URL + "?" + urlencode(params)
    return {"url": url}


@router.get("/google/callback")
def google_callback(
    request: Request,
    session: SessionDep,
    code: str,
    state: str,
) -> RedirectResponse:
    if not _verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    # Exchange code for tokens
    with httpx.Client() as client:
        token_resp = client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code with Google")

    access_token = token_resp.json().get("access_token")

    # Fetch user info
    with httpx.Client() as client:
        userinfo_resp = client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch Google user info")

    userinfo = userinfo_resp.json()
    google_id: str = userinfo["sub"]
    email: str = userinfo["email"]
    full_name: str | None = userinfo.get("name")

    user = get_or_create_google_user(
        session=session,
        email=email,
        full_name=full_name,
        google_id=google_id,
    )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    audit_logs_crud.create_audit_log(
        session=session,
        audit_log_in=AuditLogCreate(
            action="LOGIN_SUCCESS",
            entity_type="User",
            entity_id=str(user.id),
            description="Google OAuth login",
            user_agent=request.headers.get("user-agent"),
        ),
        user_id=user.id,
        user_email=user.email,
        ip_address=request.client.host if request.client else None,
    )
    jwt = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    redirect_url = f"{settings.FRONTEND_HOST}/oauth-callback?token={jwt}"
    return RedirectResponse(url=redirect_url)


@router.get("/keycloak/authorize")
def keycloak_authorize() -> dict[str, str]:
    if not settings.KEYCLOAK_CLIENT_ID:
        raise HTTPException(status_code=503, detail="Keycloak is not configured")

    params = {
        "client_id": settings.KEYCLOAK_CLIENT_ID,
        "redirect_uri": settings.KEYCLOAK_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": _make_state(),
    }
    return {"url": settings.KEYCLOAK_AUTH_URL + "?" + urlencode(params)}


@router.get("/keycloak/callback")
def keycloak_callback(
    request: Request,
    session: SessionDep,
    code: str,
    state: str,
) -> RedirectResponse:
    if not _verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    with httpx.Client() as client:
        token_resp = client.post(
            settings.KEYCLOAK_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.KEYCLOAK_CLIENT_ID,
                "client_secret": settings.KEYCLOAK_CLIENT_SECRET,
                "redirect_uri": settings.KEYCLOAK_REDIRECT_URI,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to exchange code with Keycloak")

    access_token = token_resp.json().get("access_token")

    with httpx.Client() as client:
        userinfo_resp = client.get(
            settings.KEYCLOAK_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch Keycloak user info")

    userinfo = userinfo_resp.json()
    keycloak_id: str = userinfo["sub"]
    email: str = userinfo["email"]
    full_name: str | None = userinfo.get("name")

    user = get_or_create_keycloak_user(
        session=session,
        email=email,
        full_name=full_name,
        keycloak_id=keycloak_id,
    )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    audit_logs_crud.create_audit_log(
        session=session,
        audit_log_in=AuditLogCreate(
            action="LOGIN_SUCCESS",
            entity_type="User",
            entity_id=str(user.id),
            description="Keycloak OIDC login",
            user_agent=request.headers.get("user-agent"),
        ),
        user_id=user.id,
        user_email=user.email,
        ip_address=request.client.host if request.client else None,
    )
    jwt = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    redirect_url = f"{settings.FRONTEND_HOST}/oauth-callback?token={jwt}"
    return RedirectResponse(url=redirect_url)
