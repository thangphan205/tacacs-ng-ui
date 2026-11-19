import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import (
    CurrentUser,
    SessionDep,
    get_client_ip,
    get_current_active_superuser,
)
from app.core.config import settings
from app.core.ldap_auth import (
    LDAP_PROVIDER_PRESETS,
    build_effective_ldap_config,
    ca_cert_error,
    check_ldap_servers_connection,
    check_ldap_user_auth,
    cleartext_servers,
    invalid_ldap_filters,
    invalid_ldap_server_entries,
)
from app.crud import audit_logs as audit_logs_crud
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

_LDAP_SECRET_REQUIRED = (
    "The servers, Bind DN or TLS settings differ from the saved configuration. "
    "Enter the Bind Password again to use them."
)


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
        raise HTTPException(status_code=400, detail=_LDAP_SECRET_REQUIRED) from None


def _refuse_invalid_ldap_servers(config: dict[str, Any] | None) -> None:
    """422 for a server entry that would be silently left out, or a bad CA."""
    bad = invalid_ldap_server_entries(config or {})
    if bad:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid LDAP server address: {', '.join(bad)}",
        )
    ca_error = ca_cert_error(str((config or {}).get("ca_cert_pem") or ""))
    if ca_error:
        raise HTTPException(status_code=422, detail=ca_error)
    bad_filters = invalid_ldap_filters(config or {})
    if bad_filters:
        raise HTTPException(status_code=422, detail="; ".join(bad_filters))


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
    session: SessionDep,
    current_user: CurrentUser,
    request: Request,
    body: LdapTestAuthRequest,
) -> LdapTestAuthResponse:
    cfg, secret = _ldap_test_settings(session, body.config, body.secret)
    result = check_ldap_user_auth(
        username=body.username,
        password=body.password,
        raw_config=cfg,
        secret=secret,
    )
    # It binds as any directory user with a typed password: never untraced.
    audit_logs_crud.log_entity_action(
        session=session,
        action="LDAP_TEST_AUTH",
        entity_type="AuthProviderConfig",
        entity_id="ldap",
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        description=(
            f"Test sign-in as {body.username!r}: "
            f"{'succeeded' if result.ok else 'failed'} — {result.message}"
        )[:1024],
    )
    return result


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
    result = [r for r in result if r.provider != "ldap"]
    result.append(auth_providers_crud.ldap_public(session=session))
    for provider in _VALID_PROVIDERS - existing - {"ldap"}:
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
    if provider == "ldap":
        return auth_providers_crud.ldap_public(session=session)
    row = auth_providers_crud.get_provider_config(session=session, provider=provider)
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
    session: SessionDep,
    current_user: CurrentUser,
    request: Request,
    provider: str,
    body: AuthProviderConfigUpdate,
) -> Any:
    if provider not in _VALID_PROVIDERS:
        raise HTTPException(status_code=404, detail="Unknown provider")
    if provider == "ldap":
        _refuse_invalid_ldap_servers(body.config)
        if (
            body.config is not None
            and not body.secret
            and auth_providers_crud.ldap_save_needs_secret(
                session=session, new_config=body.config
            )
        ):
            raise HTTPException(status_code=400, detail=_LDAP_SECRET_REQUIRED)
        if body.config is not None:
            effective = build_effective_ldap_config(body.config, body.secret)
            insecure = cleartext_servers(effective)
            if insecure and not effective.allow_insecure:
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"{', '.join(insecure)} would send passwords without "
                        "encryption. Use ldaps:// or StartTLS, or tick Allow "
                        "unencrypted connections."
                    ),
                )
    existing = auth_providers_crud.get_provider_config(
        session=session, provider=provider
    )
    old_values = (
        _provider_snapshot(auth_providers_crud.to_public(existing))
        if existing is not None
        else None
    )
    row = auth_providers_crud.upsert_provider_config(
        session=session,
        provider=provider,
        enabled=body.enabled,
        config=body.config,
        secret=body.secret,
    )
    public = auth_providers_crud.to_public(row)
    # Who widened sign-in (email linking on, Required Group cleared, a new
    # server) must be traceable. The secret itself is never recorded.
    audit_logs_crud.log_entity_action(
        session=session,
        action="CREATE" if existing is None else "UPDATE",
        entity_type="AuthProviderConfig",
        entity_id=provider,
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=_provider_snapshot(public),
        description="Secret changed" if body.secret else None,
    )
    if provider == "ldap":
        return auth_providers_crud.ldap_public(session=session)
    return public


def _provider_snapshot(public: AuthProviderConfigPublic) -> str:
    return json.dumps(
        {
            "provider": public.provider,
            "enabled": public.enabled,
            "config": public.config,
        }
    )


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
