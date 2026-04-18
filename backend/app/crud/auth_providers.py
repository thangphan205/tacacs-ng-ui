import json
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.security import decrypt_secret, encrypt_secret
from app.models import AuthProviderConfig, AuthProviderConfigPublic


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def get_provider_config(
    *, session: Session, provider: str
) -> AuthProviderConfig | None:
    return session.exec(
        select(AuthProviderConfig).where(AuthProviderConfig.provider == provider)
    ).first()


def get_all_provider_configs(*, session: Session) -> list[AuthProviderConfig]:
    return list(session.exec(select(AuthProviderConfig)).all())


def upsert_provider_config(
    *,
    session: Session,
    provider: str,
    enabled: bool | None = None,
    config: dict | None = None,  # type: ignore[type-arg]
    secret: str | None = None,
) -> AuthProviderConfig:
    db = get_provider_config(session=session, provider=provider)
    if db is None:
        db = AuthProviderConfig(provider=provider)
        session.add(db)

    if enabled is not None:
        db.enabled = enabled
    if config is not None:
        db.config_json = json.dumps(config)
    if secret is not None:
        db.encrypted_secret = encrypt_secret(secret)
    db.updated_at = _utc_now()

    session.commit()
    session.refresh(db)
    return db


def to_public(db: AuthProviderConfig) -> AuthProviderConfigPublic:
    return AuthProviderConfigPublic(
        provider=db.provider,
        enabled=db.enabled,
        config=json.loads(db.config_json),
        secret_is_set=db.encrypted_secret is not None,
    )


def resolve_provider_secret(db: AuthProviderConfig) -> str | None:
    if db.encrypted_secret:
        return decrypt_secret(db.encrypted_secret)
    return None
