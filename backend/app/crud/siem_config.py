"""SIEM settings (singleton SiemConfig row, id=1)."""

from datetime import datetime, timezone

from sqlmodel import Session

from app.core.security import encrypt_secret
from app.models import SiemConfig, SiemConfigPublic, SiemConfigUpdate

# Fields compared and logged by the audit trail; the token never is.
AUDITED_FIELDS: tuple[str, ...] = (
    "enabled",
    "webhook_url",
    "webhook_verify_tls",
    "syslog_host",
    "syslog_port",
    "syslog_protocol",
    "ship_access",
    "ship_authentication",
    "ship_authorization",
    "ship_accounting",
    "ship_audit",
)


def get_config(*, session: Session) -> SiemConfig:
    """The stored row, or an unsaved default when none exists yet."""
    return session.get(SiemConfig, 1) or SiemConfig(id=1)


def to_public(cfg: SiemConfig) -> SiemConfigPublic:
    return SiemConfigPublic(
        **cfg.model_dump(include=set(AUDITED_FIELDS)),
        webhook_token_is_set=cfg.webhook_token_encrypted is not None,
        updated_at=cfg.updated_at,
    )


def audit_snapshot(cfg: SiemConfig) -> dict[str, object]:
    snap: dict[str, object] = cfg.model_dump(include=set(AUDITED_FIELDS))
    snap["webhook_token_is_set"] = cfg.webhook_token_encrypted is not None
    return snap


def update_config(*, session: Session, config_in: SiemConfigUpdate) -> SiemConfig:
    cfg = session.get(SiemConfig, 1)
    if cfg is None:
        cfg = SiemConfig(id=1)
        session.add(cfg)
    data = config_in.model_dump(exclude_unset=True)
    token = data.pop("webhook_token", None)
    if "webhook_token" in config_in.model_fields_set and token is not None:
        cfg.webhook_token_encrypted = encrypt_secret(token) if token else None
    for key in ("webhook_url", "syslog_host"):
        if key in data and not data[key]:
            data[key] = None  # "" clears
    for key, value in data.items():
        if value is not None or key in ("webhook_url", "syslog_host"):
            setattr(cfg, key, value)
    cfg.updated_at = datetime.now(timezone.utc)
    session.commit()
    session.refresh(cfg)
    return cfg
