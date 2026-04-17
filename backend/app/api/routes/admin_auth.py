from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import SessionDep, get_current_active_superuser
from app.core.config import settings
from app.crud import auth_providers as auth_providers_crud
from app.models import AuthProviderConfigPublic, AuthProviderConfigUpdate

router = APIRouter(prefix="/admin/auth-providers", tags=["admin"])

_VALID_PROVIDERS = {"google", "keycloak", "passkey"}


@router.get(
    "/",
    response_model=list[AuthProviderConfigPublic],
    dependencies=[Depends(get_current_active_superuser)],
)
def list_auth_providers(session: SessionDep) -> Any:
    rows = auth_providers_crud.get_all_provider_configs(session=session)
    # Ensure all three providers appear, even if not yet in DB
    existing = {r.provider for r in rows}
    result = [auth_providers_crud.to_public(r) for r in rows]
    for provider in _VALID_PROVIDERS - existing:
        result.append(
            AuthProviderConfigPublic(
                provider=provider, enabled=False, config={}, secret_is_set=False
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
            provider=provider, enabled=False, config={}, secret_is_set=False
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
        "passkey": db_map.get("passkey", True),
    }


status_router = _STATUS_ROUTER
