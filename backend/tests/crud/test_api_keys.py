from datetime import datetime, timedelta, timezone

from sqlmodel import Session

from app.core.security import API_KEY_LABEL, generate_api_key, hash_api_key
from app.crud import api_keys
from app.models import ApiKey, ApiKeyCreate, User
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


def _create_key(
    db: Session,
    user: User,
    *,
    scopes: str = "mcp:read",
    expires_in_days: int | None = 90,
) -> tuple[ApiKey, str]:
    return api_keys.create_api_key(
        session=db,
        api_key_create=ApiKeyCreate(
            name=random_lower_string(),
            scopes=scopes,
            expires_in_days=expires_in_days,
        ),
        owner_id=user.id,
        created_by_id=user.id,
    )


def test_generate_api_key_shape() -> None:
    plaintext, prefix, key_hash = generate_api_key()
    assert plaintext.startswith(f"{API_KEY_LABEL}_")
    assert prefix == plaintext[:20]
    assert len(key_hash) == 64
    assert key_hash == hash_api_key(plaintext)


def test_generate_api_key_is_unique() -> None:
    keys = {generate_api_key()[0] for _ in range(50)}
    assert len(keys) == 50


def test_hash_api_key_is_deterministic() -> None:
    plaintext, _, _ = generate_api_key()
    assert hash_api_key(plaintext) == hash_api_key(plaintext)
    assert hash_api_key(plaintext) != hash_api_key(plaintext + "x")


def test_parse_scopes() -> None:
    assert api_keys.parse_scopes("mcp:read, mcp:generate ,") == frozenset(
        {"mcp:read", "mcp:generate"}
    )
    assert api_keys.parse_scopes("") == frozenset()


def test_create_api_key_does_not_store_plaintext(db: Session) -> None:
    user = create_random_user(db=db)
    db_api_key, plaintext = _create_key(db, user)

    assert db_api_key.key_hash == hash_api_key(plaintext)
    assert db_api_key.key_hash != plaintext
    assert db_api_key.key_prefix == plaintext[:20]
    assert db_api_key.expires_at is not None


def test_create_api_key_without_expiry(db: Session) -> None:
    user = create_random_user(db=db)
    db_api_key, _ = _create_key(db, user, expires_in_days=0)
    assert db_api_key.expires_at is None


def test_resolve_api_key_happy_path(db: Session) -> None:
    user = create_random_user(db=db)
    db_api_key, plaintext = _create_key(db, user, scopes="mcp:read,mcp:generate")

    principal = api_keys.resolve_api_key(plaintext, "10.0.0.1")

    assert principal is not None
    assert principal.user_id == user.id
    assert principal.user_email == user.email
    assert principal.api_key_id == db_api_key.id
    assert principal.has("mcp:read")
    assert principal.has("mcp:generate")
    assert not principal.has("mcp:secrets")


def test_resolve_api_key_rejects_unknown_key() -> None:
    assert api_keys.resolve_api_key("tngk_definitely-not-a-real-key") is None


def test_resolve_api_key_rejects_revoked(db: Session) -> None:
    user = create_random_user(db=db)
    db_api_key, plaintext = _create_key(db, user)
    api_keys.revoke_api_key(session=db, db_api_key=db_api_key)

    assert api_keys.resolve_api_key(plaintext) is None


def test_resolve_api_key_rejects_expired(db: Session) -> None:
    user = create_random_user(db=db)
    db_api_key, plaintext = _create_key(db, user)
    db_api_key.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.add(db_api_key)
    db.commit()

    assert api_keys.resolve_api_key(plaintext) is None


def test_resolve_api_key_rejects_inactive_user(db: Session) -> None:
    user = create_random_user(db=db)
    _, plaintext = _create_key(db, user)
    user.is_active = False
    db.add(user)
    db.commit()

    assert api_keys.resolve_api_key(plaintext) is None


def test_resolve_api_key_touch_is_throttled(db: Session) -> None:
    user = create_random_user(db=db)
    db_api_key, plaintext = _create_key(db, user)

    api_keys.resolve_api_key(plaintext, "10.0.0.1")
    db.refresh(db_api_key)
    first_used_at = db_api_key.last_used_at
    assert first_used_at is not None

    api_keys.resolve_api_key(plaintext, "10.0.0.2")
    db.refresh(db_api_key)
    assert db_api_key.last_used_at == first_used_at
    assert db_api_key.last_used_ip == "10.0.0.1"


def test_revoke_api_key_is_idempotent(db: Session) -> None:
    user = create_random_user(db=db)
    db_api_key, _ = _create_key(db, user)

    revoked = api_keys.revoke_api_key(session=db, db_api_key=db_api_key)
    first_revoked_at = revoked.revoked_at
    assert first_revoked_at is not None

    revoked_again = api_keys.revoke_api_key(session=db, db_api_key=revoked)
    assert revoked_again.revoked_at == first_revoked_at
