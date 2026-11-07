"""Keep secrets out of the audit log's before/after values.

Audit entries store a JSON snapshot of the object (`old_values`, `new_values`)
that the Audit Logs page shows to every superuser. The snapshot used to hold
the TACACS+ password hash, each host's shared secret, the whole generated
config (which embeds both) and MAVIS bind passwords: the old `_SENSITIVE`
exclusion only covered `hashed_password`, `encrypted_secret`, `key_hash` and
`plaintext_key`.

`create_audit_log` runs every entry through `redact_audit_values`, so REST
routes, MCP writes and any future caller are covered in one place. A redacted
field keeps its key, so the entry still shows that it existed; on an update
whose secret changed, the new side says so. Migration d8a41f6b2c95 applied the
same rules to rows stored before this existed, from a frozen copy of them.
"""

import json
import re

REDACTED = "[redacted]"
CHANGED = "[redacted: changed]"

# Secret fields whatever the entity type, by exact name. Not a pattern:
# `password_type` and `password_login_disabled` are not secrets and are worth
# seeing in the log.
SECRET_FIELDS = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "hashed_password",
        "secret_key",  # a host's shared TACACS+ secret
        "encrypted_secret",
        "key_hash",
        "plaintext_key",
        "webhook_token",
        "webhook_token_encrypted",
    }
)
# Secret fields of one entity type only.
ENTITY_SECRET_FIELDS: dict[str, frozenset[str]] = {
    # The generated config embeds every host secret and TACACS+ password.
    "TacacsConfig": frozenset({"config_text"}),
}
# A MAVIS entry is a key/value pair; its value is secret when the key says so
# (LDAP_PASSWD). The other keys (LDAP_HOSTS, LDAP_BASE, ...) stay readable.
_SECRET_MAVIS_KEY = re.compile(
    r"PASS|SECRET|TOKEN|PRIVATE|CREDENTIAL|(^|_)(PW|KEY)($|_)", re.IGNORECASE
)


def _secret_fields(entity_type: str, data: dict[str, object]) -> set[str]:
    fields = set(SECRET_FIELDS) | ENTITY_SECRET_FIELDS.get(entity_type, frozenset())
    if entity_type == "Mavis" and _SECRET_MAVIS_KEY.search(
        str(data.get("mavis_key") or "")
    ):
        fields.add("mavis_value")
    return fields


def _parse(raw: str | None) -> dict[str, object] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def redact_audit_values(
    entity_type: str, old_values: str | None, new_values: str | None
) -> tuple[str | None, str | None]:
    """The two JSON snapshots with secret fields replaced by a marker.

    A snapshot that holds no secret is returned as the very same string, and
    one that is not a JSON object is returned unchanged (our own code only
    writes objects).
    """
    old, new = _parse(old_values), _parse(new_values)
    originals = {"old": dict(old or {}), "new": dict(new or {})}
    out = {"old": old_values, "new": new_values}

    for side, data in (("old", old), ("new", new)):
        if data is None:
            continue
        hit = [
            f
            for f in _secret_fields(entity_type, data)
            if data.get(f) not in (None, "")
        ]
        if not hit:
            continue
        other = originals["old" if side == "new" else "new"]
        for field in hit:
            # Only the new side flags a change, and only when the old side had
            # a different value for the same field. Compared before redaction.
            changed = (
                side == "new"
                and other.get(field) not in (None, "")
                and other[field] != originals["new"][field]
            )
            data[field] = CHANGED if changed else REDACTED
        out[side] = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return out["old"], out["new"]
