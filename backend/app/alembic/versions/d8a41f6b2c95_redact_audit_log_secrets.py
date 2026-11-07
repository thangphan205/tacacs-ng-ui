"""redact secrets already stored in auditlog

Revision ID: d8a41f6b2c95
Revises: c3f8e2a91b47
Create Date: 2026-11-07 20:00:00.000000

Audit entries kept a JSON snapshot of the changed object, and for TacacsUser,
Host, Mavis and TacacsConfig that snapshot held the TACACS+ password hash,
the host's shared secret, MAVIS bind passwords and the generated config (which
embeds the first two). The Audit Logs page shows those snapshots to every
superuser. New entries are redacted when written (core/audit_redact.py); this
applies the same rules to the rows already in the table.

IRREVERSIBLE: the secret values are overwritten with a marker, not moved. The
downgrade does nothing. Take a backup first if you need the old rows, and
note that a backup holds the secrets too.

The rules below are a frozen copy of core/audit_redact.py at this revision, so
this migration keeps doing the same thing if that module changes later. Only
rows containing a secret field name are read and rewritten, one at a time by
id, and `updated_at` is left alone.
"""

import json
import logging
import re

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d8a41f6b2c95"
down_revision = "c3f8e2a91b47"
branch_labels = None
depends_on = None

log = logging.getLogger("alembic.runtime.migration")

REDACTED = "[redacted]"
CHANGED = "[redacted: changed]"
SECRET_FIELDS = frozenset(
    {
        "password",
        "current_password",
        "new_password",
        "hashed_password",
        "secret_key",
        "encrypted_secret",
        "key_hash",
        "plaintext_key",
        "webhook_token",
        "webhook_token_encrypted",
    }
)
ENTITY_SECRET_FIELDS = {"TacacsConfig": frozenset({"config_text"})}
SECRET_MAVIS_KEY = re.compile(
    r"PASS|SECRET|TOKEN|PRIVATE|CREDENTIAL|(^|_)(PW|KEY)($|_)", re.IGNORECASE
)
_BATCH = 200


def _secret_fields(entity_type, data):
    fields = set(SECRET_FIELDS) | ENTITY_SECRET_FIELDS.get(entity_type, frozenset())
    if entity_type == "Mavis" and SECRET_MAVIS_KEY.search(
        str(data.get("mavis_key") or "")
    ):
        fields.add("mavis_value")
    return fields


def _parse(raw):
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _redact(entity_type, old_values, new_values):
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
            changed = (
                side == "new"
                and other.get(field) not in (None, "")
                and other[field] != originals["new"][field]
            )
            data[field] = CHANGED if changed else REDACTED
        out[side] = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return out["old"], out["new"]


def upgrade() -> None:
    bind = op.get_bind()
    names = sorted(SECRET_FIELDS | {"config_text", "mavis_value"})
    pattern = '"(' + "|".join(names) + ')"'
    ids = (
        bind.execute(
            sa.text(
                "SELECT id FROM auditlog "
                "WHERE old_values ~ :p OR new_values ~ :p ORDER BY created_at"
            ),
            {"p": pattern},
        )
        .scalars()
        .all()
    )
    select = sa.text(
        "SELECT id, entity_type, old_values, new_values FROM auditlog WHERE id IN :ids"
    ).bindparams(sa.bindparam("ids", expanding=True))
    update = sa.text(
        "UPDATE auditlog SET old_values = :old_values, new_values = :new_values "
        "WHERE id = :id"
    )
    rewritten = 0
    for start in range(0, len(ids), _BATCH):
        rows = bind.execute(select, {"ids": ids[start : start + _BATCH]}).all()
        changes = []
        for row_id, entity_type, old_values, new_values in rows:
            old_out, new_out = _redact(entity_type, old_values, new_values)
            if (old_out, new_out) != (old_values, new_values):
                changes.append(
                    {"id": row_id, "old_values": old_out, "new_values": new_out}
                )
        if changes:
            bind.execute(update, changes)
            rewritten += len(changes)
    log.info("Redacted secrets in %d of %d audit rows checked", rewritten, len(ids))


def downgrade() -> None:
    # The secret values are gone; there is nothing to restore.
    pass
