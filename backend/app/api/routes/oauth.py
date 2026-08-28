import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from datetime import timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from app.api.deps import SessionDep, get_client_ip
from app.core.config import settings
from app.core.security import create_access_token, decrypt_secret
from app.crud import audit_logs as audit_logs_crud
from app.crud import auth_providers as auth_providers_crud
from app.crud.users import get_or_create_google_user, get_or_create_keycloak_user
from app.models import AuditLogCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/oauth", tags=["oauth"])

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"
GOOGLE_SCOPES = "openid email profile"


# --- Credential resolution -------------------------------------------------
#
# A provider can be configured in two places: the AuthProviderConfig table,
# written by Admin -> Authentication Providers, and the environment. The table
# wins field by field, so a half-filled UI form still falls back to whatever the
# environment supplies rather than blanking it out.
#
# GET /auth-providers/status already reads the table, so without this the login
# page would offer a Google button that only ever leads to a 503.


@dataclass(frozen=True)
class _Creds:
    client_id: str
    client_secret: str
    redirect_uri: str
    auth_url: str
    token_url: str
    userinfo_url: str


def _stored(session: Session, provider: str) -> tuple[dict[str, str], str | None]:
    """Config dict and decrypted secret for a provider row. Empty when absent.

    Raises 503 when the row exists but is switched off, so a disabled provider
    refuses rather than silently falling back to stale environment values.
    """
    row = auth_providers_crud.get_provider_config(session=session, provider=provider)
    if row is None:
        return {}, None
    if not row.enabled:
        raise HTTPException(
            status_code=503, detail=f"{provider.title()} sign-in is disabled"
        )

    try:
        config = json.loads(row.config_json or "{}")
    except json.JSONDecodeError:
        logger.warning("Ignoring malformed config_json for provider %s", provider)
        config = {}

    secret: str | None = None
    if row.encrypted_secret:
        try:
            secret = decrypt_secret(row.encrypted_secret)
        except Exception:
            # Fernet is keyed on SECRET_KEY: rotating it makes every stored
            # secret undecryptable, and the fix is to re-enter it in the UI.
            logger.exception("Cannot decrypt stored secret for provider %s", provider)
            raise HTTPException(
                status_code=503,
                detail=(
                    f"Stored {provider} client secret cannot be decrypted. "
                    "Re-enter it under Admin -> Authentication Providers."
                ),
            ) from None
    return config, secret


def _google_creds(session: Session) -> _Creds:
    config, secret = _stored(session, "google")
    client_id = config.get("client_id") or settings.GOOGLE_CLIENT_ID
    if not client_id:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    return _Creds(
        client_id=client_id,
        client_secret=secret or settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=config.get("redirect_uri") or settings.GOOGLE_REDIRECT_URI,
        auth_url=GOOGLE_AUTH_URL,
        token_url=GOOGLE_TOKEN_URL,
        userinfo_url=GOOGLE_USERINFO_URL,
    )


def _keycloak_creds(session: Session) -> _Creds:
    config, secret = _stored(session, "keycloak")
    client_id = config.get("client_id") or settings.KEYCLOAK_CLIENT_ID
    if not client_id:
        raise HTTPException(status_code=503, detail="Keycloak is not configured")

    server_url = (config.get("server_url") or settings.KEYCLOAK_SERVER_URL).rstrip("/")
    realm = config.get("realm") or settings.KEYCLOAK_REALM
    base = f"{server_url}/realms/{realm}/protocol/openid-connect"
    return _Creds(
        client_id=client_id,
        client_secret=secret or settings.KEYCLOAK_CLIENT_SECRET,
        redirect_uri=config.get("redirect_uri") or settings.KEYCLOAK_REDIRECT_URI,
        auth_url=f"{base}/auth",
        token_url=f"{base}/token",
        userinfo_url=f"{base}/userinfo",
    )


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
def google_authorize(session: SessionDep) -> dict[str, str]:
    creds = _google_creds(session)

    params = {
        "client_id": creds.client_id,
        "redirect_uri": creds.redirect_uri,
        "response_type": "code",
        "scope": GOOGLE_SCOPES,
        "state": _make_state(),
        "access_type": "online",
    }
    return {"url": creds.auth_url + "?" + urlencode(params)}


@router.get("/google/callback")
def google_callback(
    request: Request,
    session: SessionDep,
    code: str,
    state: str,
) -> RedirectResponse:
    if not _verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    creds = _google_creds(session)

    # Exchange code for tokens
    with httpx.Client() as client:
        token_resp = client.post(
            creds.token_url,
            data={
                "code": code,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "redirect_uri": creds.redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=400, detail="Failed to exchange code with Google"
        )

    access_token = token_resp.json().get("access_token")

    # Fetch user info
    with httpx.Client() as client:
        userinfo_resp = client.get(
            creds.userinfo_url,
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
        ip_address=get_client_ip(request),
    )
    jwt = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    redirect_url = f"{settings.FRONTEND_HOST}/oauth-callback?token={jwt}"
    return RedirectResponse(url=redirect_url)


@router.get("/keycloak/authorize")
def keycloak_authorize(session: SessionDep) -> dict[str, str]:
    creds = _keycloak_creds(session)

    params = {
        "client_id": creds.client_id,
        "redirect_uri": creds.redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": _make_state(),
    }
    return {"url": creds.auth_url + "?" + urlencode(params)}


@router.get("/keycloak/callback")
def keycloak_callback(
    request: Request,
    session: SessionDep,
    code: str,
    state: str,
) -> RedirectResponse:
    if not _verify_state(state):
        raise HTTPException(status_code=400, detail="Invalid OAuth state")

    creds = _keycloak_creds(session)

    with httpx.Client() as client:
        token_resp = client.post(
            creds.token_url,
            data={
                "code": code,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "redirect_uri": creds.redirect_uri,
                "grant_type": "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(
            status_code=400, detail="Failed to exchange code with Keycloak"
        )

    access_token = token_resp.json().get("access_token")

    with httpx.Client() as client:
        userinfo_resp = client.get(
            creds.userinfo_url,
            headers={"Authorization": f"Bearer {access_token}"},
        )

    if userinfo_resp.status_code != 200:
        raise HTTPException(
            status_code=400, detail="Failed to fetch Keycloak user info"
        )

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
        ip_address=get_client_ip(request),
    )
    jwt = create_access_token(
        subject=str(user.id),
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )
    redirect_url = f"{settings.FRONTEND_HOST}/oauth-callback?token={jwt}"
    return RedirectResponse(url=redirect_url)
