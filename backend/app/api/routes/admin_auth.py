from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.config import settings
from app.core.ldap_auth import (
    LDAP_PROVIDER_PRESETS,
    check_ldap_servers_connection,
    check_ldap_user_auth,
    invalid_ldap_server_entries,
)
from app.crud import auth_providers as auth_providers_crud
from app.models import (
    AuthProviderConfigPublic,
    AuthProviderConfigUpdate,
    LdapTestAuthRequest,
    LdapTestAuthResponse,
    LdapTestConnectionRequest,
    LdapTestConnectionResponse,
)

router = APIRouter(prefix="/admin/auth-providers", tags=["admin"])

_VALID_PROVIDERS = {"google", "keycloak", "ldap", "microsoft", "passkey"}


def _ldap_test_settings(
    session: SessionDep,
    override_config: dict[str, Any] | None,
    override_secret: str | None,
) -> tuple[dict[str, Any], str | None]:
    _refuse_invalid_ldap_servers(override_config)
    try:
        return auth_providers_crud.ldap_test_settings(
            session=session,
            override_config=override_config,
            override_secret=override_secret,
        )
    except auth_providers_crud.LdapSecretRequired:
        raise HTTPException(
            status_code=400,
            detail=(
                "The servers, Bind DN or TLS settings differ from the saved "
                "configuration. Enter the Bind Password to test them."
            ),
        ) from None


def _refuse_invalid_ldap_servers(config: dict[str, Any] | None) -> None:
    """422 for a server entry that would otherwise be silently left out."""
    bad = invalid_ldap_server_entries(config or {})
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid LDAP server address: {', '.join(bad)}",
        )


@router.get(
    "/ldap/presets",
    dependencies=[Depends(get_current_active_superuser)],
)
def get_ldap_presets() -> dict[str, dict[str, str]]:
    return LDAP_PROVIDER_PRESETS


@router.get(
    "/ldap/mavis-import",
    dependencies=[Depends(get_current_active_superuser)],
)
def import_ldap_from_mavis(session: SessionDep) -> dict[str, str]:
    """Read non-secret connection settings from existing MAVIS LDAP rows."""
    return auth_providers_crud.ldap_settings_from_mavis(session=session)


@router.post(
    "/ldap/test-connection",
    response_model=LdapTestConnectionResponse,
    dependencies=[Depends(get_current_active_superuser)],
)
def test_ldap_connection_route(
    session: SessionDep, body: LdapTestConnectionRequest
) -> LdapTestConnectionResponse:
    cfg, secret = _ldap_test_settings(session, body.config, body.secret)
    return check_ldap_servers_connection(raw_config=cfg, secret=secret)


@router.post(
    "/ldap/test-auth",
    response_model=LdapTestAuthResponse,
    dependencies=[Depends(get_current_active_superuser)],
)
def test_ldap_auth_route(
    session: SessionDep, body: LdapTestAuthRequest
) -> LdapTestAuthResponse:
    cfg, secret = _ldap_test_settings(session, body.config, body.secret)
    return check_ldap_user_auth(
        username=body.username,
        password=body.password,
        raw_config=cfg,
        secret=secret,
    )


@router.get(
    "/",
    response_model=list[AuthProviderConfigPublic],
    dependencies=[Depends(get_current_active_superuser)],
)
def list_auth_providers(session: SessionDep) -> Any:
    rows = auth_providers_crud.get_all_provider_configs(session=session)
    # Ensure all providers appear, even if not yet in DB
    existing = {r.provider for r in rows}
    result = [auth_providers_crud.to_public(r) for r in rows]
    for provider in _VALID_PROVIDERS - existing:
        if provider == "ldap":
            result.append(auth_providers_crud.ldap_env_public())
            continue
        result.append(
            AuthProviderConfigPublic(
                provider=provider,
                enabled=(provider == "passkey"),
                config={},
                secret_is_set=False,
            )
        )
    return sorted(result, key=lambda x: x.provider)


@router.get(
    "/{provider}",
    response_model=AuthProviderConfigPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def get_auth_provider(session: SessionDep, provider: str) -> Any:
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    row = auth_providers_crud.get_provider_config(session=session, provider=provider)
    if not row and provider == "ldap":
        return auth_providers_crud.ldap_env_public()
    if not row:
        return AuthProviderConfigPublic(
            provider=provider,
            enabled=(provider == "passkey"),
            config={},
            secret_is_set=False,
        )
    return auth_providers_crud.to_public(row)


@router.put(
    "/{provider}",
    response_model=AuthProviderConfigPublic,
    dependencies=[Depends(get_current_active_superuser)],
)
def update_auth_provider(
    session: SessionDep, provider: str, body: AuthProviderConfigUpdate
) -> Any:
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if provider == "ldap":
        _refuse_invalid_ldap_servers(body.config)
    row = auth_providers_crud.upsert_provider_config(
        session=session,
        provider=provider,
        enabled=body.enabled,
        config=body.config,
        secret=body.secret,
    )
    return auth_providers_crud.to_public(row)


# --- Public status endpoint (no auth) used by the login page ---

_STATUS_ROUTER = APIRouter(prefix="/auth-providers", tags=["auth-providers"])


@_STATUS_ROUTER.get("/status")
def auth_providers_status(session: SessionDep) -> dict[str, bool]:
    rows = auth_providers_crud.get_all_provider_configs(session=session)
    db_map = {r.provider: r.enabled for r in rows}

    def _enabled(provider: str, env_key: str) -> bool:
        if provider in db_map:
            return db_map[provider]
        return bool(env_key)

    return {
        "google": _enabled("google", settings.GOOGLE_CLIENT_ID),
        "keycloak": _enabled("keycloak", settings.KEYCLOAK_CLIENT_ID),
        "ldap": _enabled("ldap", settings.LDAP_HOSTS),
        "microsoft": _enabled("microsoft", settings.MICROSOFT_CLIENT_ID),
        "passkey": db_map.get("passkey", True),
        # Local email + password sign-in; the login page hides that form when
        # off. Presentation only — /login/access-token enforces it.
        "password_login": auth_providers_crud.password_login_allowed(session=session),
        # Lets the login page hide its "Sign up" link, and the signup route
        # turn people away, instead of offering a form that can only fail.
        # This is presentation only — POST /users/signup enforces the setting.
        "open_registration": settings.USERS_OPEN_REGISTRATION,
    }


status_router = _STATUS_ROUTER
