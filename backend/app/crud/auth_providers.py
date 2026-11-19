import json
import logging
from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.core.config import settings
from app.core.ldap_auth import (
    LDAP_PROVIDER_PRESETS,
    SECRET_UNDECRYPTABLE,
    LdapEffectiveConfig,
    build_effective_ldap_config,
)
from app.core.security import decrypt_secret, encrypt_secret
from app.models import AuthProviderConfig, AuthProviderConfigPublic, Mavis

logger = logging.getLogger(__name__)


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


def password_login_allowed(*, session: Session) -> bool:
    """False when an admin turned local password sign-in off (passkey-only).

    Governs local accounts only: LDAP sign-in has its own Enable switch.
    """
    row = get_provider_config(session=session, provider="passkey")
    if row is None or not row.enabled:
        return True
    try:
        cfg = json.loads(row.config_json or "{}")
    except ValueError:
        return True
    return bool(cfg.get("allow_password_login") != "false")


# --- LDAP ----------------------------------------------------------------------


def _stored_ldap(
    *, session: Session
) -> tuple[AuthProviderConfig | None, dict[str, Any], str | None]:
    """The saved LDAP row, its config and its decrypted bind password."""
    row = get_provider_config(session=session, provider="ldap")
    if row is None:
        return None, {}, None
    try:
        cfg = json.loads(row.config_json or "{}")
    except ValueError:
        cfg = {}
    if not isinstance(cfg, dict):
        cfg = {}
    try:
        secret = resolve_provider_secret(row)
    except Exception:
        # Not "no password": sign-in must say so, not fall back to the env's.
        logger.warning("Could not decrypt the stored LDAP bind password")
        secret = None
        cfg = {**cfg, SECRET_UNDECRYPTABLE: True}
    return row, cfg, secret


def ldap_login_settings(*, session: Session) -> tuple[bool, dict[str, Any], str | None]:
    """(enabled, config, bind password) for LDAP sign-in.

    The saved row wins; without one, LDAP is on when ``LDAP_HOSTS`` is set and
    `build_effective_ldap_config` fills every field from the ``LDAP_*`` env.
    """
    row, cfg, secret = _stored_ldap(session=session)
    if row is not None:
        return (True, cfg, secret) if row.enabled else (False, {}, None)
    if settings.LDAP_HOSTS:
        return True, {}, settings.LDAP_BIND_PASSWORD or None
    return False, {}, None


def ldap_env_public() -> AuthProviderConfigPublic:
    """What the admin card shows for LDAP before any row is saved.

    The ``LDAP_*`` settings in effect, not an empty placeholder: saving the
    card writes what it shows, and a placeholder with ``enabled=False`` would
    switch off a working env-configured deployment.
    """
    env = {
        "provider_type": settings.LDAP_PROVIDER_TYPE,
        "hosts": settings.LDAP_HOSTS,
        "base_dn": settings.LDAP_BASE_DN,
        "bind_dn": settings.LDAP_BIND_DN,
        "required_group": settings.LDAP_REQUIRED_GROUP,
        "allow_insecure": "true" if settings.LDAP_ALLOW_INSECURE else "",
    }
    return AuthProviderConfigPublic(
        provider="ldap",
        enabled=bool(settings.LDAP_HOSTS),
        config={k: v.strip() for k, v in env.items() if v and v.strip()},
        # Saving without typing one stores none, and sign-in then falls back
        # to LDAP_BIND_PASSWORD — so it is "set" from the card's point of view.
        secret_is_set=bool(settings.LDAP_BIND_PASSWORD),
    )


def ldap_public(*, session: Session) -> AuthProviderConfigPublic:
    """The LDAP card's view: the saved settings over the env ones in effect.

    A key the saved config lacks takes the ``LDAP_*`` value sign-in uses for
    it (the Enable switch saves a row with no settings at all, and a partial
    config is possible too). Otherwise the card would show placeholders and
    Save would write them over a working env setup. A key saved empty stays
    empty: it is the admin's choice (`build_effective_ldap_config`).
    """
    row, stored_cfg, _secret = _stored_ldap(session=session)
    env = ldap_env_public()
    if row is None:
        return env
    saved = {
        k: v for k, v in to_public(row).config.items() if k != SECRET_UNDECRYPTABLE
    }
    undecryptable = bool(stored_cfg.get(SECRET_UNDECRYPTABLE))
    return AuthProviderConfigPublic(
        provider="ldap",
        enabled=row.enabled,
        config={**env.config, **saved},
        # An unreadable saved password is not "set": the card must ask for it.
        secret_is_set=(
            False if undecryptable else bool(row.encrypted_secret) or env.secret_is_set
        ),
    )


def _secret_destination(cfg: LdapEffectiveConfig) -> tuple[object, ...]:
    """Everything that decides where, and how safely, the bind password is sent."""
    return (
        tuple((s.host, s.port, s.use_ssl, s.start_tls) for s in cfg.servers),
        cfg.bind_dn,
        cfg.verify_tls,
        cfg.ca_cert_pem,
    )


class LdapSecretRequired(Exception):
    """A test would send the stored bind password somewhere it was not saved for."""


def _moves_stored_secret(
    *,
    stored_cfg: dict[str, Any],
    stored_secret: str | None,
    new_cfg: dict[str, Any],
) -> bool:
    """True when `new_cfg` would send the stored bind password somewhere new.

    "Stored" includes ``LDAP_BIND_PASSWORD``, which sign-in falls back to.
    """
    if not (stored_secret or settings.LDAP_BIND_PASSWORD):
        return False  # nothing stored to leak (e.g. an anonymous bind)
    return _secret_destination(
        build_effective_ldap_config(new_cfg, stored_secret)
    ) != _secret_destination(build_effective_ldap_config(stored_cfg, stored_secret))


def ldap_test_settings(
    *,
    session: Session,
    override_config: dict[str, Any] | None,
    override_secret: str | None,
) -> tuple[dict[str, Any], str | None]:
    """Merge unsaved form values over the stored LDAP config for a test run.

    The stored bind password is reused only while the test would send it to
    the same servers, as the same Bind DN, with the same TLS checks; otherwise
    raises `LdapSecretRequired` and the caller must type it again. The
    password is write-only everywhere else (``secret_is_set``), and a test
    pointed at ``ldap://attacker:389`` would hand it over in clear text.
    """
    _row, stored_cfg, stored_secret = _stored_ldap(session=session)
    merged_cfg = {**stored_cfg, **(override_config or {})}
    if override_secret:
        return merged_cfg, override_secret
    if _moves_stored_secret(
        stored_cfg=stored_cfg, stored_secret=stored_secret, new_cfg=merged_cfg
    ):
        raise LdapSecretRequired
    return merged_cfg, stored_secret


def ldap_save_needs_secret(*, session: Session, new_config: dict[str, Any]) -> bool:
    """True when saving `new_config` without a new Bind Password is refused.

    The same rule as `ldap_test_settings`, for Save: a saved config is what
    every later sign-in uses, so repointing it would send the stored password
    to the new servers on the next login.
    """
    _row, stored_cfg, stored_secret = _stored_ldap(session=session)
    return _moves_stored_secret(
        stored_cfg=stored_cfg, stored_secret=stored_secret, new_cfg=new_config
    )


# MAVIS LDAP_SERVER_TYPE -> preset. tac_plus-ng's mavis_tacplus_ldap.pl knows
# "generic", "tacacs_schema" and "microsoft"; the UI's MAVIS templates also
# write "AD" and "openldap".
_MAVIS_SERVER_TYPES: dict[str, str] = {
    "ad": "active_directory",
    "active_directory": "active_directory",
    "microsoft": "active_directory",
    "openldap": "openldap",
    "freeipa": "freeipa",
    "ipa": "freeipa",
    "generic": "generic",
    "tacacs_schema": "generic",
}


def ldap_settings_from_mavis(*, session: Session) -> dict[str, str]:
    """Non-secret LDAP connection settings read from the MAVIS rows.

    Never returns ``LDAP_PASSWD``: the admin types the bind password again.
    """
    rows = session.exec(select(Mavis)).all()
    mavis_map = {r.mavis_key.upper(): r.mavis_value for r in rows}

    raw_type = (mavis_map.get("LDAP_SERVER_TYPE") or "").strip().lower()
    if raw_type in _MAVIS_SERVER_TYPES:
        provider_type = _MAVIS_SERVER_TYPES[raw_type]
    elif "ipa" in raw_type:
        provider_type = "freeipa"
    elif not raw_type:
        env_type = settings.LDAP_PROVIDER_TYPE.strip().lower()
        provider_type = env_type if env_type in LDAP_PROVIDER_PRESETS else "freeipa"
    else:
        provider_type = "generic"

    preset = LDAP_PROVIDER_PRESETS[provider_type]
    raw_filter = (mavis_map.get("LDAP_FILTER") or "").strip()
    user_filter = (
        raw_filter.replace("%s", "{username}")
        if raw_filter
        else preset["user_search_filter"]
    )
    return {
        "provider_type": provider_type,
        "hosts": mavis_map.get("LDAP_HOSTS", ""),
        "base_dn": mavis_map.get("LDAP_BASE", ""),
        "bind_dn": mavis_map.get("LDAP_BINDDN") or mavis_map.get("LDAP_USER", ""),
        "username_attr": mavis_map.get("LDAP_USER_NAME_ATTR")
        or preset["username_attr"],
        "user_search_filter": user_filter,
    }
