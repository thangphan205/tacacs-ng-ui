"""scrub inline secrets already stored in auditlog

Revision ID: c7e3a9d14f20
Revises: b5d2e7f41c86
Create Date: 2026-11-26 16:40:00.000000

Migration d8a41f6b2c95 masked structured secret fields (`TacacsUser.password`,
`Host.secret_key`, `TacacsConfig.config_text`, secret MAVIS keys). Free-text
fields such as `ConfigurationOption.config_option`, script bodies, nested JSON
blobs (`config_json`), `description`, and `Host.radius_secret_key` (added after
d8a41f6b2c95) could still hold inline credentials such as
`password login = clear "..."` or `key = "..."`.

New entries are scrubbed at write time by `core/audit_redact.py`. This
migration applies a frozen copy of those rules to every historical row in
`auditlog`, leaving `updated_at` untouched.

IRREVERSIBLE: secret values are overwritten with `[redacted]`. Downgrade is a
no-op.
"""

import json
import logging
import re
from typing import Any

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c7e3a9d14f20"
down_revision = "b5d2e7f41c86"
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
        "radius_secret_key",
        "encrypted_secret",
        "key_hash",
        "plaintext_key",
        "webhook_token",
        "webhook_token_encrypted",
        "bot_token",
        "client_secret",
        "bind_password",
        "api_key",
        "access_token",
        "refresh_token",
        "private_key",
    }
)
ENTITY_SECRET_FIELDS = {"TacacsConfig": frozenset({"config_text"})}
SECRET_MAVIS_KEY = re.compile(
    r"PASS|SECRET|TOKEN|PRIVATE|CREDENTIAL|(^|_)(PW|KEY)($|_)", re.IGNORECASE
)

_PEM_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"
)
_API_KEY_RE = re.compile(r"\btngk_[A-Za-z0-9_-]{8,}\b")
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)
_AUTH_HEADER_RE = re.compile(
    r"(\bAuthorization\s*:\s*(?:Bearer|Basic)\s+)(\S+)",
    re.IGNORECASE,
)
_TACACS_PASSWORD_QUOTED_RE = re.compile(
    r'(\bpassword(?:\s+[\w-]+)?\s*=\s*(?:(?:clear|des|crypt|pbkdf2|md5|sha\d*)\s+)?)(["\'])([^"\']*)\2',
    re.IGNORECASE,
)
_TACACS_PASSWORD_UNQUOTED_RE = re.compile(
    r'(\bpassword(?:\s+[\w-]+)?\s*=\s*(?:clear|des|crypt|pbkdf2|md5|sha\d*)\s+)([^\s;{}#"\']+)',
    re.IGNORECASE,
)
_TACACS_KEY_QUOTED_RE = re.compile(
    r'(\b(?:(?:radius\.)?key|shared[-_ ]?key|secret(?:[-_]?key)?|psk|radius[-_]?secret(?:[-_]?key)?)\s*[=:]\s*(?:clear\s+)?)(["\'])([^"\']*)\2',
    re.IGNORECASE,
)
_TACACS_KEY_UNQUOTED_RE = re.compile(
    r'(\b(?:(?:radius\.)?key|shared[-_ ]?key|secret(?:[-_]?key)?|psk|radius[-_]?secret(?:[-_]?key)?)\s*=\s*(?:clear\s+)?)([^\s;{}#"\']+)',
    re.IGNORECASE,
)
_SETENV_SECRET_RE = re.compile(
    r'(\bsetenv\s+\w*(?:PASSWD|PASSWORD|PASS|SECRET|TOKEN|PRIVATE|CREDENTIAL|PW|KEY)\w*\s*=\s*)(?:"([^"]*)"|\'([^\']*)\'|([^\s;{}#"\']+))',
    re.IGNORECASE,
)
_GENERIC_SECRET_KV_RE = re.compile(
    r'(\b(?:api[-_]?key|access[-_]?token|refresh[-_]?token|bot[-_]?token|webhook[-_]?token|client[-_]?secret|bind[-_]?pw|bind[-_]?password|secret\w*)\s*[=:]\s*)(?:"([^"]*)"|\'([^\']*)\'|([^\s,;{}#"\']+))',
    re.IGNORECASE,
)
_ALREADY_REDACTED = frozenset({REDACTED, CHANGED, "***REDACTED***"})
_NON_SECRET_LITERALS = frozenset({"none", "null", "true", "false"})
_BATCH = 200


def _replace_quoted(match: re.Match[str]) -> str:
    prefix, quote, value = match.group(1), match.group(2), match.group(3)
    if not value or value in _ALREADY_REDACTED:
        return match.group(0)
    return f"{prefix}{quote}{REDACTED}{quote}"


def _replace_unquoted(match: re.Match[str]) -> str:
    prefix, value = match.group(1), match.group(2)
    if not value or value in _ALREADY_REDACTED or value.lower() in _NON_SECRET_LITERALS:
        return match.group(0)
    return f"{prefix}{REDACTED}"


def _replace_kv(match: re.Match[str]) -> str:
    prefix = match.group(1)
    dq, sq, bare = match.group(2), match.group(3), match.group(4)
    if dq is not None:
        if not dq or dq in _ALREADY_REDACTED:
            return match.group(0)
        return f'{prefix}"{REDACTED}"'
    if sq is not None:
        if not sq or sq in _ALREADY_REDACTED:
            return match.group(0)
        return f"{prefix}'{REDACTED}'"
    if (
        not bare
        or bare in _ALREADY_REDACTED
        or bare.lower() in _NON_SECRET_LITERALS
    ):
        return match.group(0)
    return f"{prefix}{REDACTED}"


def _redact_text(text: str) -> str:
    if not text:
        return text
    text = _PEM_PRIVATE_KEY_RE.sub(REDACTED, text)
    text = _API_KEY_RE.sub(REDACTED, text)
    text = _JWT_RE.sub(REDACTED, text)
    text = _AUTH_HEADER_RE.sub(_replace_unquoted, text)
    text = _TACACS_PASSWORD_QUOTED_RE.sub(_replace_quoted, text)
    text = _TACACS_PASSWORD_UNQUOTED_RE.sub(_replace_unquoted, text)
    text = _TACACS_KEY_QUOTED_RE.sub(_replace_quoted, text)
    text = _TACACS_KEY_UNQUOTED_RE.sub(_replace_unquoted, text)
    text = _SETENV_SECRET_RE.sub(_replace_kv, text)
    text = _GENERIC_SECRET_KV_RE.sub(_replace_kv, text)
    return text


def _secret_fields(entity_type: str, data: dict[str, Any]) -> set[str]:
    fields = set(SECRET_FIELDS) | ENTITY_SECRET_FIELDS.get(entity_type, frozenset())
    if entity_type == "Mavis" and SECRET_MAVIS_KEY.search(
        str(data.get("mavis_key") or "")
    ):
        fields.add("mavis_value")
    return fields


def _parse(raw: str | None) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _scrub_nested(value: Any, *, depth: int = 0) -> tuple[Any, bool]:
    if depth > 6:
        return value, False
    if isinstance(value, str):
        stripped = value.strip()
        if stripped and stripped[0] in ("{", "["):
            try:
                parsed = json.loads(value)
            except ValueError:
                parsed = None
            if isinstance(parsed, (dict, list)):
                scrubbed_obj, changed = _scrub_nested(parsed, depth=depth + 1)
                if changed:
                    return (
                        json.dumps(
                            scrubbed_obj, separators=(",", ":"), ensure_ascii=False
                        ),
                        True,
                    )
                return value, False
        scrubbed = _redact_text(value)
        return scrubbed, scrubbed != value
    if isinstance(value, dict):
        changed = False
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in SECRET_FIELDS and v not in (None, "", REDACTED, CHANGED):
                out[k] = REDACTED
                changed = True
            else:
                sv, c = _scrub_nested(v, depth=depth + 1)
                out[k] = sv
                if c:
                    changed = True
        return (out, True) if changed else (value, False)
    if isinstance(value, list):
        changed = False
        out_list: list[Any] = []
        for item in value:
            si, c = _scrub_nested(item, depth=depth + 1)
            out_list.append(si)
            if c:
                changed = True
        return (out_list, True) if changed else (value, False)
    return value, False


def _redact(
    entity_type: str,
    old_values: str | None,
    new_values: str | None,
    description: str | None = None,
) -> tuple[str | None, str | None, str | None]:
    old, new = _parse(old_values), _parse(new_values)
    originals = {"old": dict(old or {}), "new": dict(new or {})}
    out = {"old": old_values, "new": new_values}

    for side, data in (("old", old), ("new", new)):
        if data is None:
            raw = out[side]
            if raw:
                scrubbed_raw = _redact_text(raw)
                if scrubbed_raw != raw:
                    out[side] = scrubbed_raw
            continue
        modified = False
        secret_field_names = _secret_fields(entity_type, data)
        hit = [f for f in secret_field_names if data.get(f) not in (None, "")]
        other = originals["old" if side == "new" else "new"]
        for field in hit:
            changed = (
                side == "new"
                and other.get(field) not in (None, "")
                and other[field] != originals["new"][field]
            )
            replacement = CHANGED if changed else REDACTED
            if data[field] != replacement:
                data[field] = replacement
                modified = True
        for field, val in list(data.items()):
            if field in secret_field_names:
                continue
            scrubbed, was_changed = _scrub_nested(val)
            if was_changed:
                data[field] = scrubbed
                modified = True
        if modified:
            out[side] = json.dumps(data, separators=(",", ":"), ensure_ascii=False)

    desc_out = _redact_text(description) if description else description
    return out["old"], out["new"], desc_out


def upgrade() -> None:
    bind = op.get_bind()
    ids = (
        bind.execute(
            sa.text(
                "SELECT id FROM auditlog "
                "WHERE old_values IS NOT NULL "
                "OR new_values IS NOT NULL "
                "OR description IS NOT NULL "
                "ORDER BY created_at"
            )
        )
        .scalars()
        .all()
    )
    select = sa.text(
        "SELECT id, entity_type, old_values, new_values, description "
        "FROM auditlog WHERE id IN :ids"
    ).bindparams(sa.bindparam("ids", expanding=True))
    update = sa.text(
        "UPDATE auditlog SET old_values = :old_values, new_values = :new_values, "
        "description = :description WHERE id = :id"
    )
    rewritten = 0
    for start in range(0, len(ids), _BATCH):
        rows = bind.execute(select, {"ids": ids[start : start + _BATCH]}).all()
        changes = []
        for row_id, entity_type, old_values, new_values, description in rows:
            old_out, new_out, desc_out = _redact(
                entity_type, old_values, new_values, description
            )
            if (old_out, new_out, desc_out) != (old_values, new_values, description):
                changes.append(
                    {
                        "id": row_id,
                        "old_values": old_out,
                        "new_values": new_out,
                        "description": desc_out,
                    }
                )
        if changes:
            bind.execute(update, changes)
            rewritten += len(changes)
    log.info(
        "Scrubbed inline secrets in %d of %d audit rows checked", rewritten, len(ids)
    )


def downgrade() -> None:
    # The secret values are gone; there is nothing to restore.
    pass
