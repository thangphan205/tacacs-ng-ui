import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from cryptography.fernet import Fernet
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError
from pwdlib.hashers.argon2 import Argon2Hasher
from pwdlib.hashers.bcrypt import BcryptHasher

from app.core.config import settings

# Argon2 comes first, which makes it pwdlib's "current" hasher: every new hash
# and every rehash is argon2id. Bcrypt is kept ONLY so hashes written before
# this migration stay verifiable; crud.users.authenticate() upgrades them on the
# owner's next successful login.
password_hash = PasswordHash(
    (
        Argon2Hasher(),
        BcryptHasher(),
    )
)


ALGORITHM = "HS256"


def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    """Return (is_valid, updated_hash).

    `updated_hash` is non-None only when the stored hash should be rewritten —
    i.e. it is a legacy bcrypt hash, or an argon2 hash whose parameters no
    longer match the current Argon2Hasher config.
    """
    try:
        return password_hash.verify_and_update(plain_password, hashed_password)
    except (UnknownHashError, ValueError):
        # UnknownHashError: the stored hash matches no enabled hasher.
        # ValueError: bcrypt >= 5.0 raises for secrets longer than 72 bytes
        # instead of truncating them, and the password field of
        # OAuth2PasswordRequestForm on /login/access-token is length-unbounded.
        # Treat both as "wrong password" — never let them become a 500.
        return False, None


def get_password_hash(password: str) -> str:
    return password_hash.hash(password)


def _fernet() -> Fernet:
    key = base64.urlsafe_b64encode(
        hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    )
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


# --- API keys ---
#
# API keys are 256-bit CSPRNG tokens, not human passwords, so they are stored as
# a keyed digest rather than a bcrypt hash. Two reasons:
#   1. bcrypt embeds a random salt, which makes `WHERE key_hash = :h` impossible.
#   2. bcrypt is ~100ms of *blocking* CPU by design; every MCP tool call is one
#      key verification, so that cost lands on the request path.
# Keying the digest with SECRET_KEY means a stolen DB dump alone cannot be used
# to verify guesses. Note this makes API keys share the fate of JWTs and Fernet
# secrets: rotating SECRET_KEY invalidates all of them.

API_KEY_LABEL = "tngk"
API_KEY_PREFIX_LENGTH = 20


def hash_api_key(raw: str) -> str:
    return hmac.new(
        settings.SECRET_KEY.encode(), raw.encode(), hashlib.sha256
    ).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Return (plaintext, key_prefix, key_hash). The plaintext is never stored."""
    raw = f"{API_KEY_LABEL}_{secrets.token_urlsafe(32)}"
    return raw, raw[:API_KEY_PREFIX_LENGTH], hash_api_key(raw)
