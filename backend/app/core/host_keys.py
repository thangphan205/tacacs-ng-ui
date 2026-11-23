"""The TACACS+ key a host gets when it has none of its own.

tac_plus-ng treats a `host` with no `key` as one that talks TACACS+ without a
shared secret: it refuses the unencrypted flag ("Peers MUST use
Obfuscation") but reads a body sent with the flag clear as cleartext and
checks the password in it (verified on the binary,
tests/core/test_radius_binary.py). A RADIUS-only host (a RADIUS secret, no
TACACS+ key) would then let anyone at its address log in over TACACS+.

Such a host gets a key derived from SECRET_KEY instead: nobody knows it, so no
TACACS+ request from that address decrypts, and it is the same on every
Generate, so the preview never differs from the active config because of it.
It is never shown, and MCP output redacts it like any other key.

Pure function with no database access, so the MCP redaction can use it.
"""

import hashlib
import hmac
import uuid

from app.core.config import settings


def unused_tacacs_key(host_id: uuid.UUID) -> str:
    """A TACACS+ key for `host_id` that no device has, stable per install."""
    return hmac.new(
        settings.SECRET_KEY.encode(),
        f"tacacs-unused-host-key:{host_id}".encode(),
        hashlib.sha256,
    ).hexdigest()
