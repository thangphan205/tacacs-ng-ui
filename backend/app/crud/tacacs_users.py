import time as _time
from datetime import datetime, timezone
from typing import Any

from passlib.context import CryptContext
from passlib.hash import sha512_crypt
from sqlalchemy import update as sa_update
from sqlmodel import Session, select

from app.core.config import settings
from app.models import (
    TacacsUser,
    TacacsUserCreate,
    TacacsUserPublic,
    TacacsUserUpdate,
    check_clear_password,
)

# SHA-512 crypt hashing - compatible with tac_plus-ng "crypt" password type
tacacs_pwd_context = CryptContext(schemes=["sha512_crypt"], deprecated="auto")

_LIVE_LAST_AUTH_TTL = 60.0
_live_last_auth_cache: dict[str, Any] = {}


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def update_last_authenticated(
    *, session: Session, last_auth: dict[str, datetime]
) -> int:
    """Advance ``TacacsUser.last_authenticated_at`` for users in ``last_auth``.

    Only updates rows where the new timestamp is strictly newer than the stored
    value (or the stored value is ``None``). Preserves ``updated_at`` so login
    activity does not look like a configuration edit. Caller commits.
    """
    if not last_auth:
        return 0

    rows = session.exec(
        select(
            TacacsUser.id, TacacsUser.username, TacacsUser.last_authenticated_at
        ).where(TacacsUser.username.in_(list(last_auth.keys())))  # type: ignore[attr-defined]
    ).all()

    updated = 0
    for user_id, username, current in rows:
        candidate = _as_utc(last_auth[username])
        if current is None or candidate > _as_utc(current):
            session.exec(
                sa_update(TacacsUser)
                .where(TacacsUser.id == user_id)  # type: ignore[arg-type]
                .values(
                    last_authenticated_at=candidate,
                    updated_at=TacacsUser.updated_at,
                )
            )
            updated += 1
    return updated


def get_live_last_authenticated() -> dict[str, datetime]:
    """Today's latest successful login per username from local (and peer) logs.

    Cached for 60 s so the TACACS Users page reflects recent logins without
    waiting for the periodic stats collector or writing on GET requests.
    """
    from app.crud.aaa_statistics import _peer_payloads
    from scripts._log_stats_base import local_today, parse_authentication_logs

    today = local_today()
    today_str = today.isoformat()
    now_ts = _time.monotonic()

    if (
        _live_last_auth_cache.get("date") == today_str
        and now_ts - _live_last_auth_cache.get("ts", 0.0) < _LIVE_LAST_AUTH_TTL
    ):
        return _live_last_auth_cache["data"]

    last_auth: dict[str, datetime] = {}
    parse_authentication_logs(today, settings.TACACS_LOG_DIRECTORY, last_auth=last_auth)

    for payload in _peer_payloads(today_str):
        raw_peer = payload.get("last_authenticated")
        if not isinstance(raw_peer, dict):
            continue
        for username, ts_str in raw_peer.items():
            if not isinstance(ts_str, str):
                continue
            try:
                ts = _as_utc(datetime.fromisoformat(ts_str))
            except ValueError:
                continue
            if username not in last_auth or ts > last_auth[username]:
                last_auth[username] = ts

    _live_last_auth_cache["date"] = today_str
    _live_last_auth_cache["ts"] = now_ts
    _live_last_auth_cache["data"] = last_auth
    return last_auth


def to_public_with_live_auth(
    user: TacacsUser, live_map: dict[str, datetime]
) -> TacacsUserPublic:
    """Build ``TacacsUserPublic`` with ``last_authenticated_at`` overlaid from today's logs."""
    stored = user.last_authenticated_at
    live = live_map.get(user.username)
    effective: datetime | None
    if stored is None:
        effective = live
    elif live is None:
        effective = stored
    else:
        effective = live if _as_utc(live) > _as_utc(stored) else stored

    public = TacacsUserPublic.model_validate(user)
    public.last_authenticated_at = effective
    return public


def hash_tacacs_password(password: str) -> str:
    return tacacs_pwd_context.hash(password)


def is_tacacs_password_hash(value: str) -> bool:
    """True when `value` is already a complete sha512-crypt hash.

    The `password` field carries a plaintext password that this module hashes.
    Callers sometimes supply a `$6$...` digest instead — an admin pasting one
    into the UI form, an MCP client that saw `password login = crypt "$6$..."`
    in the syntax reference and produced a matching digest, or an operator
    migrating accounts from another system. Hashing that a second time stores
    `sha512_crypt(sha512_crypt(pw))`, and the account then silently rejects the
    password its owner was given.

    Deliberately stricter than `CryptContext.identify()`, which accepts a bare
    `$6$notahash`: a *malformed* digest is far more likely to be someone's
    unusual plaintext than a real hash, and must still be hashed. Requiring a
    parsed checksum draws that line.
    """
    try:
        parsed = sha512_crypt.from_string(value)
    except (ValueError, TypeError):
        return False
    return bool(parsed.checksum)


def get_tacacs_user_by_username(
    *, session: Session, username: str
) -> TacacsUser | None:
    statement = select(TacacsUser).where(TacacsUser.username == username)
    session_user = session.exec(statement).first()
    return session_user


def create_tacacs_user(
    *, session: Session, user_create: TacacsUserCreate
) -> TacacsUser:
    db_obj = TacacsUser.model_validate(user_create)
    if (
        db_obj.password_type == "crypt"
        and db_obj.password
        and not is_tacacs_password_hash(db_obj.password)
    ):
        db_obj.password = hash_tacacs_password(db_obj.password)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_tacacs_user(
    *, session: Session, db_user: TacacsUser, user_in: TacacsUserUpdate
) -> Any:
    """Raises ``ValueError`` when the merged row has an unsafe clear password."""
    user_data = user_in.model_dump(exclude_unset=True)
    check_clear_password(
        user_data.get("password_type", db_user.password_type),
        user_data.get("password", db_user.password),
    )
    # Hash the password if type is crypt and a new plaintext password is given.
    # An already-hashed value is stored verbatim — it arrives either because the
    # caller sent a digest (see is_tacacs_password_hash) or because a partial
    # update echoed the stored hash back, and re-hashing either would lock the
    # account's owner out.
    password_type = user_data.get("password_type", db_user.password_type)
    if (
        password_type == "crypt"
        and user_data.get("password")
        and not is_tacacs_password_hash(user_data["password"])
    ):
        user_data["password"] = hash_tacacs_password(user_data["password"])
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user
