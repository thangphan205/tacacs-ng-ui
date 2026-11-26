"""Keep secrets out of the audit log's before/after values and descriptions.

Audit entries store a JSON snapshot of the object (`old_values`, `new_values`)
and a free-text `description`. Field-level redaction masks structured secret
columns (`TacacsUser.password`, `Host.secret_key`, `Host.radius_secret_key`,
`TacacsConfig.config_text`, secret MAVIS keys, etc.), and content-based
scrubbing (`redact_text`) strips inline credentials from free-text fields such
as `ConfigurationOption.config_option`, script bodies, nested `config_json`
blobs, and `description`.

`create_audit_log` runs every entry through `redact_audit_values` and
`redact_text`, so REST routes, MCP writes and any future caller are covered in
one place at write time. A redacted field keeps its key, so the entry still
shows that it existed; on an update whose secret changed, the new side says so.
"""

import json
import re
from typing import Any

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
        "radius_secret_key",  # a host's shared RADIUS secret
        "encrypted_secret",
        "key_hash",
        "plaintext_key",
        "webhook_token",
        "webhook_token_encrypted",
        "bot_token",
        "smtp_password",
        "client_secret",
        "bind_password",
        "api_key",
        "access_token",
        "refresh_token",
        "private_key",
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

# Content-based scrubbers for free-text fields (e.g. ConfigurationOption.config_option,
# script bodies, descriptions). All replacements are idempotent.
_PEM_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z0-9 ]*PRIVATE KEY-----"
)
_API_KEY_RE = re.compile(r"\btngk_[A-Za-z0-9_-]{8,}\b")
_TELEGRAM_BOT_TOKEN_RE = re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{30,}\b")
_JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"
)
_AUTH_HEADER_RE = re.compile(
    r"(\bAuthorization\s*:\s*(?:Bearer|Basic)\s+)(\S+)",
    re.IGNORECASE,
)
# tac_plus-ng password directives:
#   password login = clear "secret"
#   password chap = clear "secret"
#   password ms-chap = clear "secret"
#   password enable = crypt "$6$..."
#   password login = clear secret
# Does NOT touch `password pap = login`, `password login = mavis`, etc.
_TACACS_PASSWORD_QUOTED_RE = re.compile(
    r'(\bpassword(?:\s+[\w-]+)?\s*=\s*(?:(?:clear|des|crypt|pbkdf2|md5|sha\d*)\s+)?)(["\'])([^"\']*)\2',
    re.IGNORECASE,
)
_TACACS_PASSWORD_UNQUOTED_RE = re.compile(
    r'(\bpassword(?:\s+[\w-]+)?\s*=\s*(?:clear|des|crypt|pbkdf2|md5|sha\d*)\s+)([^\s;{}#"\']+)',
    re.IGNORECASE,
)
# tac_plus-ng key / shared-key / secret / psk directives:
#   key = "secret", radius.key = "secret", shared-key = "secret", key = secret
_TACACS_KEY_QUOTED_RE = re.compile(
    r'(\b(?:(?:radius\.)?key|shared[-_ ]?key|secret(?:[-_]?key)?|psk|radius[-_]?secret(?:[-_]?key)?)\s*[=:]\s*(?:clear\s+)?)(["\'])([^"\']*)\2',
    re.IGNORECASE,
)
_TACACS_KEY_UNQUOTED_RE = re.compile(
    r'(\b(?:(?:radius\.)?key|shared[-_ ]?key|secret(?:[-_]?key)?|psk|radius[-_]?secret(?:[-_]?key)?)\s*=\s*(?:clear\s+)?)([^\s;{}#"\']+)',
    re.IGNORECASE,
)
# tac_plus-ng setenv with a secret-looking variable name:
#   setenv LDAP_PASSWD = "secret"
_SETENV_SECRET_RE = re.compile(
    r'(\bsetenv\s+\w*(?:PASSWD|PASSWORD|PASS|SECRET|TOKEN|PRIVATE|CREDENTIAL|PW|KEY)\w*\s*=\s*)(?:"([^"]*)"|\'([^\']*)\'|([^\s;{}#"\']+))',
    re.IGNORECASE,
)
# Generic named secret assignments in free text (e.g. descriptions, scripts).
_GENERIC_SECRET_KV_RE = re.compile(
    r'(\b(?:api[-_]?key|access[-_]?token|refresh[-_]?token|bot[-_]?token|webhook[-_]?token|client[-_]?secret|bind[-_]?pw|bind[-_]?password|secret\w*)\s*[=:]\s*)(?:"([^"]*)"|\'([^\']*)\'|([^\s,;{}#"\']+))',
    re.IGNORECASE,
)
_ALREADY_REDACTED = frozenset({REDACTED, CHANGED, "***REDACTED***"})
_NON_SECRET_LITERALS = frozenset({"none", "null", "true", "false"})


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


def redact_text(text: str) -> str:
    """Scrub inline secrets from arbitrary free-text values. Idempotent."""
    if not text:
        return text
    text = _PEM_PRIVATE_KEY_RE.sub(REDACTED, text)
    text = _API_KEY_RE.sub(REDACTED, text)
    text = _TELEGRAM_BOT_TOKEN_RE.sub(REDACTED, text)
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
    if entity_type == "Mavis" and _SECRET_MAVIS_KEY.search(
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


def _scrub_nested_value(value: Any, *, depth: int = 0) -> tuple[Any, bool]:
    """Recursively scrub secrets inside strings, nested JSON strings, dicts and lists."""
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
                scrubbed_obj, changed = _scrub_nested_value(parsed, depth=depth + 1)
                if changed:
                    return (
                        json.dumps(
                            scrubbed_obj, separators=(",", ":"), ensure_ascii=False
                        ),
                        True,
                    )
                return value, False
        scrubbed = redact_text(value)
        return scrubbed, scrubbed != value
    if isinstance(value, dict):
        changed = False
        out: dict[str, Any] = {}
        for k, v in value.items():
            if k in SECRET_FIELDS and v not in (None, "", REDACTED, CHANGED):
                out[k] = REDACTED
                changed = True
            else:
                sv, c = _scrub_nested_value(v, depth=depth + 1)
                out[k] = sv
                if c:
                    changed = True
        return (out, True) if changed else (value, False)
    if isinstance(value, list):
        changed = False
        out_list: list[Any] = []
        for item in value:
            si, c = _scrub_nested_value(item, depth=depth + 1)
            out_list.append(si)
            if c:
                changed = True
        return (out_list, True) if changed else (value, False)
    return value, False


def redact_audit_values(
    entity_type: str, old_values: str | None, new_values: str | None
) -> tuple[str | None, str | None]:
    """The two JSON snapshots with secret fields and inline secrets replaced.

    A snapshot that holds no secret is returned as the very same string. A
    non-JSON-object string is still passed through `redact_text` so raw text
    cannot bypass content scrubbing.
    """
    old, new = _parse(old_values), _parse(new_values)
    originals = {"old": dict(old or {}), "new": dict(new or {})}
    out = {"old": old_values, "new": new_values}

    for side, data in (("old", old), ("new", new)):
        if data is None:
            raw = out[side]
            if raw:
                scrubbed_raw = redact_text(raw)
                if scrubbed_raw != raw:
                    out[side] = scrubbed_raw
            continue
        modified = False
        secret_field_names = _secret_fields(entity_type, data)
        hit = [
            f
            for f in secret_field_names
            if data.get(f) not in (None, "")
        ]
        other = originals["old" if side == "new" else "new"]
        for field in hit:
            # Only the new side flags a change, and only when the old side had
            # a different value for the same field. Compared before redaction.
            changed = (
                side == "new"
                and other.get(field) not in (None, "")
                and other[field] != originals["new"][field]
            )
            replacement = CHANGED if changed else REDACTED
            if data[field] != replacement:
                data[field] = replacement
                modified = True

        # Content-based scrubbing for all remaining fields (e.g.
        # ConfigurationOption.config_option, script bodies, nested config_json).
        for field, val in list(data.items()):
            if field in secret_field_names:
                continue
            scrubbed, was_changed = _scrub_nested_value(val)
            if was_changed:
                data[field] = scrubbed
                modified = True

        if modified:
            out[side] = json.dumps(data, separators=(",", ":"), ensure_ascii=False)
    return out["old"], out["new"]
