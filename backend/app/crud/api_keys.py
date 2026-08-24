import ipaddress
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.core.config import settings
from app.core.db import engine
from app.core.security import generate_api_key, hash_api_key
from app.models import ApiKey, ApiKeyCreate, User

log = logging.getLogger(__name__)

# Only re-write last_used_at this often. Without it, four uvicorn workers would
# each write the same row on every single tool call.
_TOUCH_INTERVAL = timedelta(seconds=60)


@dataclass(frozen=True)
class ApiKeyPrincipal:
    """The identity an authenticated API key resolves to."""

    user_id: uuid.UUID
    user_email: str
    is_superuser: bool
    api_key_id: uuid.UUID
    api_key_name: str
    scopes: frozenset[str]

    def has(self, scope: str) -> bool:
        return scope in self.scopes


def parse_scopes(scopes: str) -> frozenset[str]:
    return frozenset(s.strip() for s in scopes.split(",") if s.strip())


def create_api_key(
    *,
    session: Session,
    api_key_create: ApiKeyCreate,
    owner_id: uuid.UUID,
    created_by_id: uuid.UUID,
) -> tuple[ApiKey, str]:
    """Create an API key. Returns (row, plaintext) — the only time plaintext exists."""
    plaintext, key_prefix, key_hash = generate_api_key()

    expires_at = api_key_create.expires_at
    if expires_at is None:
        days = api_key_create.expires_in_days
        if days is None:
            days = settings.MCP_DEFAULT_KEY_EXPIRY_DAYS
        if days > 0:
            expires_at = datetime.now(timezone.utc) + timedelta(days=days)

    db_api_key = ApiKey(
        name=api_key_create.name,
        scopes=api_key_create.scopes,
        allowed_ips=api_key_create.allowed_ips,
        description=api_key_create.description,
        expires_at=expires_at,
        user_id=owner_id,
        created_by_id=created_by_id,
        key_prefix=key_prefix,
        key_hash=key_hash,
    )
    session.add(db_api_key)
    session.commit()
    session.refresh(db_api_key)
    return db_api_key, plaintext


def get_api_key_by_id(*, session: Session, id: uuid.UUID) -> ApiKey | None:
    return session.get(ApiKey, id)


def revoke_api_key(*, session: Session, db_api_key: ApiKey) -> ApiKey:
    """Soft revoke, so the audit trail stays joinable."""
    if db_api_key.revoked_at is None:
        db_api_key.revoked_at = datetime.now(timezone.utc)
        session.add(db_api_key)
        session.commit()
        session.refresh(db_api_key)
    return db_api_key


def update_allowed_ips(
    *, session: Session, db_api_key: ApiKey, allowed_ips: str | None
) -> ApiKey:
    """Update the source-IP allowlist — the only field editable post-creation."""
    db_api_key.allowed_ips = allowed_ips
    session.add(db_api_key)
    session.commit()
    session.refresh(db_api_key)
    return db_api_key


def _ip_allowed(allowed_ips: str | None, ip: str | None) -> bool:
    if not allowed_ips:
        return True
    if ip is None:
        return False
    try:
        candidate = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in (e.strip() for e in allowed_ips.split(",")):
        if not entry:
            continue
        try:
            if candidate in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def _is_usable(api_key: ApiKey, *, now: datetime, ip: str | None) -> bool:
    if api_key.revoked_at is not None:
        return False
    if api_key.expires_at is not None:
        expires_at = api_key.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= now:
            return False
    if not _ip_allowed(api_key.allowed_ips, ip):
        return False
    return True


def _touch(session: Session, api_key: ApiKey, ip: str | None, now: datetime) -> None:
    """Record usage, throttled, and never on a read-only standby replica."""
    if settings.NODE_ROLE == "standby":
        return
    last = api_key.last_used_at
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last < _TOUCH_INTERVAL:
            return
    api_key.last_used_at = now
    api_key.last_used_ip = ip
    session.add(api_key)
    session.commit()


def resolve_api_key(raw: str, ip: str | None = None) -> ApiKeyPrincipal | None:
    """
    Resolve a plaintext API key to a principal, or None if it is not usable.

    Opens its own session: callers are ASGI middleware, not FastAPI routes, so
    there is no request-scoped session to borrow.
    """
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        statement = select(ApiKey).where(ApiKey.key_hash == hash_api_key(raw))
        api_key = session.exec(statement).first()
        if api_key is None or not _is_usable(api_key, now=now, ip=ip):
            return None

        user = session.get(User, api_key.user_id)
        if user is None or not user.is_active:
            return None

        principal = ApiKeyPrincipal(
            user_id=user.id,
            user_email=user.email,
            is_superuser=user.is_superuser,
            api_key_id=api_key.id,
            api_key_name=api_key.name,
            scopes=parse_scopes(api_key.scopes),
        )
        try:
            _touch(session, api_key, ip, now)
        except Exception:
            # Usage tracking must never fail an otherwise valid authentication.
            log.warning("Failed to record API key usage", exc_info=True)
            session.rollback()
        return principal
