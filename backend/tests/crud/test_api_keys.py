from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError
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
    allowed_ips: str | None = None,
) -> tuple[ApiKey, str]:
    return api_keys.create_api_key(
        session=db,
        api_key_create=ApiKeyCreate(
            name=random_lower_string(),
            scopes=scopes,
            expires_in_days=expires_in_days,
            allowed_ips=allowed_ips,
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
    assert api_keys.parse_scopes("mcp:read, mcp:write ,") == frozenset(
        {"mcp:read", "mcp:write"}
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
    db_api_key, plaintext = _create_key(db, user, scopes="mcp:read,mcp:write")

    principal = api_keys.resolve_api_key(plaintext, "10.0.0.1")

    assert principal is not None
    assert principal.user_id == user.id
    assert principal.user_email == user.email
    assert principal.api_key_id == db_api_key.id
    assert principal.has("mcp:read")
    assert principal.has("mcp:write")
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


def test_resolve_api_key_allows_any_ip_when_unset(db: Session) -> None:
    user = create_random_user(db=db)
    _, plaintext = _create_key(db, user)

    assert api_keys.resolve_api_key(plaintext, "203.0.113.9") is not None
    assert api_keys.resolve_api_key(plaintext, None) is not None


def test_resolve_api_key_allows_matching_cidr(db: Session) -> None:
    user = create_random_user(db=db)
    _, plaintext = _create_key(db, user, allowed_ips="10.0.0.0/24")

    assert api_keys.resolve_api_key(plaintext, "10.0.0.5") is not None


def test_resolve_api_key_rejects_non_matching_ip(db: Session) -> None:
    user = create_random_user(db=db)
    _, plaintext = _create_key(db, user, allowed_ips="10.0.0.0/24")

    assert api_keys.resolve_api_key(plaintext, "192.168.1.1") is None


def test_resolve_api_key_allows_exact_bare_address(db: Session) -> None:
    user = create_random_user(db=db)
    _, plaintext = _create_key(db, user, allowed_ips="203.0.113.4")

    assert api_keys.resolve_api_key(plaintext, "203.0.113.4") is not None
    assert api_keys.resolve_api_key(plaintext, "203.0.113.5") is None


def test_resolve_api_key_ipv6_cidr_containment(db: Session) -> None:
    user = create_random_user(db=db)
    _, plaintext = _create_key(db, user, allowed_ips="2001:db8::/32")

    assert api_keys.resolve_api_key(plaintext, "2001:db8::1") is not None
    assert api_keys.resolve_api_key(plaintext, "2001:db9::1") is None


def test_resolve_api_key_malformed_ip_does_not_crash(db: Session) -> None:
    user = create_random_user(db=db)
    _, plaintext = _create_key(db, user, allowed_ips="10.0.0.0/24")

    assert api_keys.resolve_api_key(plaintext, "not-an-ip") is None


def test_resolve_api_key_no_ip_denied_when_restricted(db: Session) -> None:
    user = create_random_user(db=db)
    _, plaintext = _create_key(db, user, allowed_ips="10.0.0.0/24")

    assert api_keys.resolve_api_key(plaintext, None) is None


def test_allowed_ips_validator_rejects_invalid_entry() -> None:
    with pytest.raises(ValidationError):
        ApiKeyCreate(name="k", allowed_ips="10.0.0.0/24, garbage")


def test_allowed_ips_validator_normalizes_empty_to_none() -> None:
    assert ApiKeyCreate(name="k", allowed_ips="").allowed_ips is None
    assert ApiKeyCreate(name="k", allowed_ips="   ,  ").allowed_ips is None


def test_allowed_ips_validator_normalizes_whitespace() -> None:
    created = ApiKeyCreate(name="k", allowed_ips="  10.0.0.1 ,10.0.0.2")
    assert created.allowed_ips == "10.0.0.1,10.0.0.2"


def test_update_allowed_ips(db: Session) -> None:
    user = create_random_user(db=db)
    db_api_key, _ = _create_key(db, user)

    updated = api_keys.update_allowed_ips(
        session=db, db_api_key=db_api_key, allowed_ips="10.0.0.0/24"
    )
    assert updated.allowed_ips == "10.0.0.0/24"
