import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.config import settings
from app.core.ldap_auth import (
    LDAP_PROVIDER_PRESETS,
    LdapEffectiveConfig,
    build_effective_ldap_config,
    check_ldap_servers_connection,
    check_ldap_user_auth,
)
from app.crud import auth_providers as auth_providers_crud
from app.models import (
    AuthProviderConfigPublic,
    AuthProviderConfigUpdate,
    LdapTestAuthRequest,
    LdapTestAuthResponse,
    LdapTestConnectionRequest,
    LdapTestConnectionResponse,
    Mavis,
)

router = APIRouter(prefix="/admin/auth-providers", tags=["admin"])

_VALID_PROVIDERS = {"google", "keycloak", "ldap", "microsoft", "passkey"}


def _secret_destination(cfg: LdapEffectiveConfig) -> tuple[object, ...]:
    """Everything that decides where, and how safely, the bind password is sent."""
    return (
        tuple((s.host, s.port, s.use_ssl, s.start_tls) for s in cfg.servers),
        cfg.bind_dn,
        cfg.verify_tls,
        cfg.ca_cert_pem,
    )


def _resolve_ldap_config_and_secret(
    session: SessionDep,
    override_config: dict[str, Any] | None,
    override_secret: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Merge unsaved form values over the stored LDAP config for a test run.

    The stored bind password is reused only while the test would send it to
    the same servers, as the same Bind DN, with the same TLS checks. Otherwise
    the caller must type it again: the password is write-only everywhere else
    (``secret_is_set``), and a test pointed at ``ldap://attacker:389`` would
    hand it over in clear text.
    """
    row = auth_providers_crud.get_provider_config(session=session, provider="ldap")
    stored_cfg: dict[str, Any] = {}
    stored_secret: str | None = None
    if row is not None:
        try:
            stored_cfg = json.loads(row.config_json or "{}")
        except ValueError:
            stored_cfg = {}
        try:
            stored_secret = auth_providers_crud.resolve_provider_secret(row)
        except Exception:
            stored_secret = None
    merged_cfg = {**stored_cfg, **(override_config or {})}
    if override_secret:
        return merged_cfg, override_secret
    if not (stored_secret or settings.LDAP_BIND_PASSWORD):
        # Nothing stored to leak (e.g. testing an anonymous bind).
        return merged_cfg, None

    # No secret typed: the stored one, or LDAP_BIND_PASSWORD when none is stored.
    if _secret_destination(
        build_effective_ldap_config(merged_cfg, stored_secret)
    ) != _secret_destination(build_effective_ldap_config(stored_cfg, stored_secret)):
        raise HTTPException(
            status_code=400,
            detail=(
                "The servers, Bind DN or TLS settings differ from the saved "
                "configuration. Enter the Bind Password to test them."
            ),
        )
    return merged_cfg, stored_secret


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
    rows = list(session.exec(select(Mavis)).all())
    mavis_map = {r.mavis_key.upper(): r.mavis_value for r in rows}

    raw_type = (mavis_map.get("LDAP_SERVER_TYPE") or "").strip().lower()
    if raw_type in ("ad", "active_directory", "microsoft"):
        provider_type = "active_directory"
    elif "ipa" in raw_type:
        provider_type = "freeipa"
    elif "openldap" in raw_type:
        provider_type = "openldap"
    else:
        provider_type = "freeipa"

    preset = LDAP_PROVIDER_PRESETS[provider_type]
    raw_filter = (mavis_map.get("LDAP_FILTER") or "").strip()
    if raw_filter:
        user_filter = raw_filter.replace("%s", "{username}")
    else:
        user_filter = preset["user_search_filter"]

    return {
        "provider_type": provider_type,
        "hosts": mavis_map.get("LDAP_HOSTS", ""),
        "base_dn": mavis_map.get("LDAP_BASE", ""),
        "bind_dn": mavis_map.get("LDAP_BINDDN") or mavis_map.get("LDAP_USER", ""),
        "username_attr": mavis_map.get("LDAP_USER_NAME_ATTR")
        or preset["username_attr"],
        "user_search_filter": user_filter,
    }


@router.post(
    "/ldap/test-connection",
    response_model=LdapTestConnectionResponse,
    dependencies=[Depends(get_current_active_superuser)],
)
def test_ldap_connection_route(
    session: SessionDep, body: LdapTestConnectionRequest
) -> LdapTestConnectionResponse:
    cfg, secret = _resolve_ldap_config_and_secret(session, body.config, body.secret)
    return check_ldap_servers_connection(raw_config=cfg, secret=secret)


@router.post(
    "/ldap/test-auth",
    response_model=LdapTestAuthResponse,
    dependencies=[Depends(get_current_active_superuser)],
)
def test_ldap_auth_route(
    session: SessionDep, body: LdapTestAuthRequest
) -> LdapTestAuthResponse:
    cfg, secret = _resolve_ldap_config_and_secret(session, body.config, body.secret)
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
