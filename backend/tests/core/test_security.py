"""Password hashing behaviour after the passlib -> pwdlib migration.

Legacy hashes are minted through pwdlib's own BcryptHasher rather than by
importing `bcrypt` directly, since bcrypt is now only a transitive dependency.
"""

import sys

from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.security import get_password_hash, verify_password

PASSWORD = "Correct-Horse-1!"


def _legacy_bcrypt_hash(password: str = PASSWORD) -> str:
    """A hash in the format stored before the migration."""
    return BcryptHasher(rounds=12).hash(password)


def test_get_password_hash_is_argon2() -> None:
    hashed = get_password_hash(PASSWORD)
    assert hashed.startswith("$argon2id$")


def test_verify_new_argon2_hash_needs_no_update() -> None:
    assert verify_password(PASSWORD, get_password_hash(PASSWORD)) == (True, None)


def test_verify_wrong_password_against_argon2() -> None:
    assert verify_password("wrong", get_password_hash(PASSWORD)) == (False, None)


def test_verify_legacy_bcrypt_hash_succeeds() -> None:
    valid, _ = verify_password(PASSWORD, _legacy_bcrypt_hash())
    assert valid is True


def test_verify_legacy_bcrypt_hash_returns_argon2_upgrade() -> None:
    valid, updated = verify_password(PASSWORD, _legacy_bcrypt_hash())
    assert valid is True
    assert updated is not None
    assert updated.startswith("$argon2id$")
    # The upgraded hash must itself be usable and already current.
    assert verify_password(PASSWORD, updated) == (True, None)


def test_verify_wrong_password_against_bcrypt_returns_false_none() -> None:
    """A failed verify must never mint an upgrade hash."""
    assert verify_password("wrong", _legacy_bcrypt_hash()) == (False, None)


def test_verify_unknown_hash_format_returns_false_none() -> None:
    """pwdlib raises UnknownHashError, which must not escape as a 500."""
    assert verify_password(PASSWORD, "not-a-hash") == (False, None)


def test_verify_oversized_password_against_bcrypt_does_not_raise() -> None:
    """Regression guard for bcrypt >= 5.0.

    bcrypt 5.0 raises ValueError for secrets over 72 bytes instead of
    truncating. The login form's password field is length-unbounded, so without
    the guard in verify_password this is an unauthenticated 500 against any
    account still holding a bcrypt hash.
    """
    assert verify_password("a" * 200, _legacy_bcrypt_hash()) == (False, None)


def test_verify_oversized_password_against_argon2_is_fine() -> None:
    """Argon2 has no length ceiling, so a long password simply fails to match."""
    assert verify_password("a" * 200, get_password_hash(PASSWORD)) == (False, None)


def test_verify_argon2_hash_with_stale_params_is_upgraded() -> None:
    """The rehash path is parameter-driven, not merely bcrypt-specific."""
    weak = Argon2Hasher(time_cost=1, memory_cost=8, parallelism=1).hash(PASSWORD)
    valid, updated = verify_password(PASSWORD, weak)
    assert valid is True
    assert updated is not None
    assert verify_password(PASSWORD, updated) == (True, None)


def test_passlib_bcrypt_backend_is_never_loaded() -> None:
    """passlib is retained only for sha512_crypt, and must stay that way.

    passlib's bcrypt backend probes for an old OpenBSD wrap-around bug by
    hashing a 255-byte secret, which bcrypt >= 5.0 rejects with ValueError --
    loading it would break every hash and verify. Adding "bcrypt" to any passlib
    CryptContext in this codebase would reintroduce that, so assert it stays
    unloaded.
    """
    from app.crud.tacacs_users import hash_tacacs_password

    hashed = hash_tacacs_password(PASSWORD)
    assert hashed.startswith("$6$rounds=")
    assert "passlib.handlers.bcrypt" not in sys.modules
