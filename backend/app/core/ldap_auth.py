"""Native LDAP / Active Directory / FreeIPA / OpenLDAP authentication for the Web UI.

Scoped strictly to Web UI authentication (with an optional custom `required_group`
membership gate). Web UI RBAC (`is_superuser`, `is_active`) remains owned by the
local `user` table in PostgreSQL.
"""

from __future__ import annotations

import json
import logging
import re
import ssl
import time
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from ldap3 import BASE, NONE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import (
    LDAPBindError,
    LDAPBusyResult,
    LDAPCommunicationError,
    LDAPException,
    LDAPInvalidCredentialsResult,
    LDAPMaximumRetriesError,
    LDAPNoSuchObjectResult,
    LDAPResponseTimeoutError,
    LDAPSocketOpenError,
    LDAPStartTLSError,
    LDAPUnavailableResult,
)
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import parse_dn
from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.config import settings
from app.models import (
    LdapServerDiagResult,
    LdapTestAuthResponse,
    LdapTestConnectionResponse,
)

logger = logging.getLogger(__name__)

# Errors that mean "this server is not usable right now" — the only ones that
# move on to the next server (#404: never fail over on a credential or
# authorization answer).
# Every other LDAP error is an answer from the server — a malformed Bind DN,
# a wrong base DN, missing rights — that every replica gives alike.
_UNAVAILABLE_ERRORS: tuple[type[BaseException], ...] = (
    LDAPSocketOpenError,
    LDAPCommunicationError,
    LDAPStartTLSError,
    LDAPResponseTimeoutError,
    LDAPMaximumRetriesError,
    LDAPBusyResult,
    LDAPUnavailableResult,
    OSError,
)

LDAP_PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "active_directory": {
        "label": "Microsoft Active Directory",
        "username_attr": "sAMAccountName",
        "email_attr": "mail",
        "full_name_attr": "displayName",
        "user_search_filter": (
            "(&(objectClass=user)(|(sAMAccountName={username})(userPrincipalName={username})))"
        ),
        "group_search_filter": "(&(objectClass=group)(cn={group}))",
        "group_member_attr": "member",
        "unique_id_attr": "objectGUID",
    },
    "freeipa": {
        "label": "FreeIPA",
        "username_attr": "uid",
        "email_attr": "mail",
        "full_name_attr": "cn",
        "user_search_filter": (
            "(&(objectClass=posixAccount)(|(uid={username})(krbPrincipalName={username})))"
        ),
        "group_search_filter": (
            "(&(|(objectClass=ipaUserGroup)(objectClass=groupOfNames)(objectClass=posixGroup))(cn={group}))"
        ),
        "group_member_attr": "member,memberUid",
        "unique_id_attr": "ipaUniqueID",
    },
    "openldap": {
        "label": "OpenLDAP",
        "username_attr": "uid",
        "email_attr": "mail",
        "full_name_attr": "cn",
        "user_search_filter": "(&(objectClass=inetOrgPerson)(uid={username}))",
        "group_search_filter": (
            "(&(|(objectClass=groupOfNames)(objectClass=groupOfUniqueNames)(objectClass=posixGroup))(cn={group}))"
        ),
        "group_member_attr": "member,uniqueMember,memberUid",
        "unique_id_attr": "entryUUID",
    },
    "generic": {
        "label": "Generic LDAP (Custom Schema)",
        "username_attr": "uid",
        "email_attr": "mail",
        "full_name_attr": "cn",
        "user_search_filter": "(&(objectClass=person)(uid={username}))",
        "group_search_filter": (
            "(&(|(objectClass=groupOfNames)(objectClass=posixGroup))(cn={group}))"
        ),
        "group_member_attr": "member,uniqueMember,memberUid",
        "unique_id_attr": "entryUUID",
    },
}


@dataclass(frozen=True)
class LdapServerTarget:
    url: str
    host: str
    port: int
    use_ssl: bool
    start_tls: bool
    priority: int = 1


@dataclass(frozen=True)
class LdapEffectiveConfig:
    provider_type: str
    servers: list[LdapServerTarget]
    base_dn: str
    user_base_dn: str
    group_base_dn: str
    bind_dn: str
    bind_password: str
    username_attr: str
    unique_id_attr: str
    email_attr: str
    full_name_attr: str
    user_search_filter: str
    required_group: str
    group_search_filter: str
    group_member_attr: str
    start_tls: bool
    verify_tls: bool
    ca_cert_pem: str
    connect_timeout: int
    receive_timeout: int
    fallback_email_domain: str
    allow_email_link: bool
    require_approval: bool = False
    allow_insecure: bool = False
    # The saved bind password exists but cannot be decrypted (SECRET_KEY changed).
    bind_password_undecryptable: bool = False


@dataclass(frozen=True)
class LdapIdentity:
    ldap_id: str
    user_dn: str
    email: str
    full_name: str | None
    # The directory username (``username_attr``): lets an account keyed on it
    # (no readable unique ID) be re-keyed once the ID becomes readable.
    username: str = ""


@dataclass
class LdapAuthOutcome:
    ok: bool
    # "ok" | "user_not_found" | "ambiguous_user" | "invalid_credentials"
    # | "group_denied" | "no_email" | "unavailable" | "misconfigured"
    reason: str
    message: str
    identity: LdapIdentity | None = None
    server_used: str | None = None
    failover_occurred: bool = False
    failed_servers: list[tuple[str, str]] = field(default_factory=list)


def _parse_bool(val: Any, default: bool = False) -> bool:
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        v = val.strip().lower()
        if v in ("true", "1", "yes", "on"):
            return True
        if v in ("false", "0", "no", "off"):
            return False
    return default


def _parse_int(val: Any, default: int, minimum: int = 1, maximum: int = 120) -> int:
    try:
        parsed = int(str(val).strip())
        return max(minimum, min(maximum, parsed))
    except (ValueError, TypeError):
        return default


def _parse_single_server_url(
    raw_url: str, default_start_tls: bool = False, priority: int = 1
) -> LdapServerTarget | None:
    raw = raw_url.strip()
    if not raw:
        return None
    if "://" not in raw:
        raw = f"ldap://{raw}"
    try:
        parsed = urlparse(raw)
        explicit_port = parsed.port  # ValueError when out of range or not a number
        host = parsed.hostname or ""
    except ValueError:
        logger.warning("Ignoring LDAP server %r: invalid address or port", raw_url)
        return None
    scheme = (parsed.scheme or "ldap").lower()
    if scheme not in ("ldap", "ldaps"):
        logger.warning("Ignoring LDAP server %r: scheme must be ldap or ldaps", raw_url)
        return None
    use_ssl = scheme == "ldaps"
    if not host:
        return None
    default_port = 636 if use_ssl else 389
    port = explicit_port or default_port
    canonical_url = f"{'ldaps' if use_ssl else 'ldap'}://{host}:{port}"
    return LdapServerTarget(
        url=canonical_url,
        host=host,
        port=port,
        use_ssl=use_ssl,
        start_tls=(default_start_tls and not use_ssl),
        priority=priority,
    )


def parse_ldap_servers(
    raw_config: dict[str, Any], default_start_tls: bool = False
) -> list[LdapServerTarget]:
    """Parse priority-ordered LDAP servers from config dict or environment fallback."""
    targets: list[tuple[int, int, LdapServerTarget]] = []

    servers_json_raw = raw_config.get("servers_json")
    if servers_json_raw:
        try:
            items = (
                json.loads(servers_json_raw)
                if isinstance(servers_json_raw, str)
                else servers_json_raw
            )
            if isinstance(items, list):
                for idx, item in enumerate(items):
                    if not isinstance(item, dict):
                        continue
                    url_or_host = str(item.get("url") or item.get("host") or "").strip()
                    if not url_or_host:
                        continue
                    prio = _parse_int(item.get("priority"), idx + 1, 1, 1000)
                    item_start_tls = _parse_bool(
                        item.get("start_tls"), default_start_tls
                    )
                    target = _parse_single_server_url(
                        url_or_host, default_start_tls=item_start_tls, priority=prio
                    )
                    if target is not None:
                        targets.append((prio, idx, target))
        except (ValueError, TypeError):
            logger.warning("Ignoring malformed servers_json in LDAP config")

    has_saved_servers = any(
        k in raw_config for k in ("servers_json", "hosts", "server_urls")
    )
    if not targets:
        hosts_raw = str(
            raw_config.get("hosts")
            or raw_config.get("server_urls")
            or ("" if has_saved_servers else settings.LDAP_HOSTS)
            or ""
        )
        parts = [p.strip() for p in re.split(r"[\s,;]+", hosts_raw) if p.strip()]
        for idx, part in enumerate(parts):
            prio = idx + 1
            target = _parse_single_server_url(
                part, default_start_tls=default_start_tls, priority=prio
            )
            if target is not None:
                targets.append((prio, idx, target))

    targets.sort(key=lambda t: (t[0], t[1]))
    return [t[2] for t in targets]


def invalid_ldap_server_entries(raw_config: dict[str, Any]) -> list[str]:
    """Server entries in a config being saved that `parse_ldap_servers` would drop.

    Checked on save so a typo (``ldap://dc2:99999``) is refused instead of
    silently leaving that server out of the failover list.
    """
    entries: list[str] = []
    servers_json_raw = raw_config.get("servers_json")
    if servers_json_raw:
        try:
            items = (
                json.loads(servers_json_raw)
                if isinstance(servers_json_raw, str)
                else servers_json_raw
            )
        except ValueError:
            return ["servers_json (not valid JSON)"]
        if not isinstance(items, list):
            return ["servers_json (not a list)"]
        for item in items:
            if isinstance(item, dict):
                entries.append(str(item.get("url") or item.get("host") or "").strip())
    hosts_raw = str(raw_config.get("hosts") or raw_config.get("server_urls") or "")
    entries.extend(p.strip() for p in re.split(r"[\s,;]+", hosts_raw))
    bad = [e for e in entries if e and _parse_single_server_url(e) is None]
    return list(dict.fromkeys(bad))


# Marker key crud.auth_providers adds to a config whose secret cannot be read.
SECRET_UNDECRYPTABLE = "_secret_undecryptable"


def _saved_or_env(cfg: dict[str, Any], key: str, env_value: str) -> str:
    """A saved value wins, even an empty one; env fills only an absent key.

    Otherwise an admin could never clear a field the env sets — an empty
    Required Group or Bind DN would silently keep the env's.
    """
    if key in cfg and cfg[key] is not None:
        return str(cfg[key]).strip()
    return (env_value or "").strip()


def build_effective_ldap_config(
    raw_config: dict[str, Any] | None,
    secret: str | None,
) -> LdapEffectiveConfig:
    cfg = raw_config or {}
    provider_type = (
        _saved_or_env(cfg, "provider_type", settings.LDAP_PROVIDER_TYPE) or "freeipa"
    ).lower()
    if provider_type not in LDAP_PROVIDER_PRESETS:
        provider_type = "generic"
    preset = LDAP_PROVIDER_PRESETS[provider_type]

    start_tls = _parse_bool(cfg.get("start_tls"), False)
    verify_tls = _parse_bool(cfg.get("verify_tls"), True)
    servers = parse_ldap_servers(cfg, default_start_tls=start_tls)

    base_dn = _saved_or_env(cfg, "base_dn", settings.LDAP_BASE_DN)
    user_base_dn = str(cfg.get("user_base_dn") or "").strip() or base_dn
    group_base_dn = str(cfg.get("group_base_dn") or "").strip() or base_dn
    bind_dn = _saved_or_env(cfg, "bind_dn", settings.LDAP_BIND_DN)
    # `_secret_undecryptable` is set by crud.auth_providers when the saved
    # password cannot be decrypted; a typed password overrides it. The env
    # password is for a deployment with no saved one — never for a directory
    # the admin configured.
    undecryptable = bool(cfg.get(SECRET_UNDECRYPTABLE)) and not secret
    bind_password = (
        ""
        if undecryptable
        else (secret if secret is not None else (settings.LDAP_BIND_PASSWORD or ""))
    )

    username_attr = (
        str(cfg.get("username_attr") or "").strip() or preset["username_attr"]
    )
    # Absent key -> preset default; an explicit empty string opts out and keys
    # accounts on the (recyclable) username instead.
    raw_unique = cfg.get("unique_id_attr")
    unique_id_attr = (
        preset["unique_id_attr"] if raw_unique is None else str(raw_unique).strip()
    )
    email_attr = str(cfg.get("email_attr") or "").strip() or preset["email_attr"]
    full_name_attr = (
        str(cfg.get("full_name_attr") or "").strip() or preset["full_name_attr"]
    )
    user_search_filter = (
        str(cfg.get("user_search_filter") or "").strip() or preset["user_search_filter"]
    )

    required_group = _saved_or_env(cfg, "required_group", settings.LDAP_REQUIRED_GROUP)
    group_search_filter = (
        str(cfg.get("group_search_filter") or "").strip()
        or preset["group_search_filter"]
    )
    group_member_attr = (
        str(cfg.get("group_member_attr") or "").strip() or preset["group_member_attr"]
    )

    ca_cert_pem = str(cfg.get("ca_cert_pem") or "").strip()
    connect_timeout = _parse_int(cfg.get("connect_timeout"), 5, 1, 60)
    receive_timeout = _parse_int(cfg.get("receive_timeout"), 10, 1, 120)
    fallback_email_domain = (
        str(cfg.get("fallback_email_domain") or "").strip().lstrip("@").lower()
    )

    return LdapEffectiveConfig(
        provider_type=provider_type,
        servers=servers,
        base_dn=base_dn,
        user_base_dn=user_base_dn,
        group_base_dn=group_base_dn,
        bind_dn=bind_dn,
        bind_password=bind_password,
        username_attr=username_attr,
        unique_id_attr=unique_id_attr,
        email_attr=email_attr,
        full_name_attr=full_name_attr,
        user_search_filter=user_search_filter,
        required_group=required_group,
        group_search_filter=group_search_filter,
        group_member_attr=group_member_attr,
        start_tls=start_tls,
        verify_tls=verify_tls,
        ca_cert_pem=ca_cert_pem,
        connect_timeout=connect_timeout,
        receive_timeout=receive_timeout,
        fallback_email_domain=fallback_email_domain,
        allow_email_link=_parse_bool(cfg.get("allow_email_link"), False),
        require_approval=_parse_bool(cfg.get("require_approval"), False),
        allow_insecure=_parse_bool(
            cfg.get("allow_insecure"), settings.LDAP_ALLOW_INSECURE
        ),
        bind_password_undecryptable=undecryptable,
    )


def cleartext_servers(cfg: LdapEffectiveConfig) -> list[str]:
    """Servers a bind would reach without TLS (plain ldap:// and no StartTLS)."""
    return [t.url for t in cfg.servers if not (t.use_ssl or t.start_tls)]


def _has_placeholder(template: str, name: str) -> bool:
    return bool(_PLACEHOLDER_RE[name].search(template))


def invalid_ldap_filters(raw_config: dict[str, Any]) -> list[str]:
    """Saved filters that would not depend on who is signing in.

    ``(uid=svc)`` without a placeholder matches the same entry whatever
    username was typed, so every sign-in becomes an attempt on that account.
    """
    bad: list[str] = []
    for key, name in (
        ("user_search_filter", "username"),
        ("group_search_filter", "group"),
    ):
        value = str(raw_config.get(key) or "").strip()
        if value and not _has_placeholder(value, name):
            bad.append(f"{key} must contain {{{name}}} (or %s)")
    return bad


def configuration_problem(cfg: LdapEffectiveConfig) -> str | None:
    """Why sign-in or a connection test must not run with `cfg`, or None."""
    if cfg.bind_dn and not cfg.bind_password:
        if cfg.bind_password_undecryptable:
            return (
                "The saved Bind Password cannot be decrypted (the SECRET_KEY "
                "changed). Enter it again and save."
            )
        return "A Bind DN is set but no Bind Password is configured."
    ca_error = ca_cert_error(cfg.ca_cert_pem)
    if ca_error:
        return ca_error
    insecure = cleartext_servers(cfg)
    if insecure and not cfg.allow_insecure:
        return (
            f"{', '.join(insecure)} would send passwords without encryption. "
            "Use ldaps:// or StartTLS, or allow unencrypted connections "
            "explicitly (only on a trusted network)."
        )
    if not _has_placeholder(cfg.user_search_filter, "username"):
        return "The user search filter must contain {username} (or %s)."
    return None


def _build_tls(cfg: LdapEffectiveConfig) -> Tls:
    validate_mode = ssl.CERT_REQUIRED if cfg.verify_tls else ssl.CERT_NONE
    kwargs: dict[str, Any] = {
        "validate": validate_mode,
        "version": ssl.PROTOCOL_TLS_CLIENT,
    }
    if cfg.ca_cert_pem:
        kwargs["ca_certs_data"] = cfg.ca_cert_pem
    return Tls(**kwargs)


_PLACEHOLDER_RE: dict[str, re.Pattern[str]] = {
    name: re.compile(r"\{" + name + r"\}|%s") for name in ("username", "group")
}


def _fill_placeholder(template: str, name: str, value: str) -> str:
    """Substitute `{name}` and MAVIS-style `%s` in one pass.

    Two chained ``replace`` calls would substitute a ``%s`` inside the
    already-inserted value a second time (``ab%scd`` -> ``abab%scdcd``).
    """
    escaped = escape_filter_chars(value)
    return _PLACEHOLDER_RE[name].sub(lambda _m: escaped, template)


def _format_user_filter(template: str, username: str) -> str:
    return _fill_placeholder(template, "username", username)


def ca_cert_error(pem: str) -> str | None:
    """Why `pem` cannot be used as the CA bundle, or None when it can.

    Checked up front: a malformed PEM raises ``ssl.SSLError``, an ``OSError``,
    which would otherwise read as every server being unreachable.
    """
    if not pem.strip():
        return None
    try:
        ssl.create_default_context(cadata=pem)
    except (ssl.SSLError, ValueError) as exc:
        return f"CA certificate is not a valid PEM bundle: {exc}"
    return None


def _extract_first_str(entry_attrs: dict[str, Any], attr_name: str) -> str | None:
    # Case-insensitive attribute lookup in entry dictionary
    target_lower = attr_name.lower()
    for k, val in entry_attrs.items():
        if k.lower() == target_lower:
            if isinstance(val, list):
                for item in val:
                    if item is not None and str(item).strip():
                        return str(item).strip()
            elif val is not None and str(val).strip():
                return str(val).strip()
    return None


def _extract_str_list(entry_attrs: dict[str, Any], attr_name: str) -> list[str]:
    target_lower = attr_name.lower()
    for k, val in entry_attrs.items():
        if k.lower() == target_lower:
            if isinstance(val, list):
                return [str(v).strip() for v in val if v is not None and str(v).strip()]
            if val is not None and str(val).strip():
                return [str(val).strip()]
    return []


_EMAIL_ADAPTER: TypeAdapter[str] = TypeAdapter(EmailStr)


def _valid_email(value: str | None) -> str | None:
    """Return `value` lower-cased when the User model's EmailStr accepts it.

    Checked here, not left to the database: `User.email` is only validated on
    the way out (`UserPublic`), so a stored special-use domain such as
    `@ldap.local` would make `/users/me` fail for that account.
    """
    if not value:
        return None
    try:
        return _EMAIL_ADAPTER.validate_python(value.strip()).lower()
    except ValidationError:
        return None


def _extract_unique_id(entry: Any, attr_name: str) -> str | None:
    """Return the entry's immutable identifier (objectGUID / ipaUniqueID / entryUUID).

    Read from the raw values: without a loaded schema ldap3 leaves the binary
    objectGUID undecoded, and a GUID is formatted the way AD displays it.
    """
    if not attr_name:
        return None
    target = attr_name.lower()
    raw_attrs = getattr(entry, "entry_raw_attributes", None)
    if isinstance(raw_attrs, dict):
        for key, values in raw_attrs.items():
            if key.lower() != target or not values:
                continue
            raw = values[0] if isinstance(values, list) else values
            if isinstance(raw, bytes):
                if target == "objectguid" and len(raw) == 16:
                    return str(uuid.UUID(bytes_le=raw))
                try:
                    raw = raw.decode("utf-8")
                except UnicodeDecodeError:
                    hex_value: str = raw.hex()
                    return hex_value
            text = str(raw).strip()
            return text.lower() or None
    attrs = getattr(entry, "entry_attributes_as_dict", None)
    if isinstance(attrs, dict):
        value = _extract_first_str(attrs, attr_name)
        return value.lower() if value else None
    return None


def _extract_rdn_value(dn: str) -> str:
    """Return the first RDN value of a DN (e.g. 'CN=netops,DC=example,DC=com' -> 'netops')."""
    first_part = dn.split(",", 1)[0].strip()
    if "=" in first_part:
        return first_part.split("=", 1)[1].strip()
    return first_part


def _normalize_dn(dn: str) -> list[tuple[str, str]] | None:
    """Parse a DN into lower-cased (attribute, value) RDNs, or None when malformed.

    Lets `CN=Admins, OU=Groups,DC=corp` and `cn=admins,ou=groups,dc=corp`
    compare equal, as the directory treats them.
    """
    try:
        parts = parse_dn(dn, escape=False, strip=True)
    except LDAPException:
        return None
    if not parts:
        return None
    return [(attr.strip().lower(), value.strip().lower()) for attr, value, _ in parts]


def _dn_is_under(dn: list[tuple[str, str]], base: list[tuple[str, str]]) -> bool:
    """True when `dn` is strictly below `base` in the tree."""
    return len(dn) > len(base) and dn[-len(base) :] == base


def _rebind_as_user(conn: Connection, user_dn: str, password: str) -> None:
    """Simple-bind `conn` as the user to verify the password.

    ldap3's ``rebind`` turns a connection the server dropped into
    ``LDAPBindError``; re-raise the socket error so it fails over instead of
    reading as a wrong password.
    """
    try:
        conn.rebind(user=user_dn, password=password)
    except LDAPBindError as exc:
        if isinstance(exc.__context__, _UNAVAILABLE_ERRORS):
            raise exc.__context__ from exc
        raise


class LdapGroupSearchError(Exception):
    """The required-group search itself failed (bad base DN, filter or rights)."""


def _open_server_connection(
    target: LdapServerTarget,
    cfg: LdapEffectiveConfig,
    bind_dn: str | None,
    bind_password: str | None,
) -> Connection:
    tls = _build_tls(cfg) if (target.use_ssl or target.start_tls) else None
    server = Server(
        host=target.host,
        port=target.port,
        use_ssl=target.use_ssl,
        tls=tls,
        # Authentication needs neither the schema nor the root DSE; ALL would
        # download both on every connection (twice per login).
        get_info=NONE,
        connect_timeout=cfg.connect_timeout,
    )
    conn = Connection(
        server,
        user=bind_dn or None,
        password=bind_password if bind_dn else None,
        auto_bind=False,
        receive_timeout=cfg.receive_timeout,
        raise_exceptions=True,
        # ldap3 would follow a referral to any host it names, without TLS when
        # the referral offers none, and bind there with the same password.
        auto_referrals=False,
    )
    conn.open()
    if target.start_tls and not target.use_ssl:
        conn.start_tls()
    if bind_dn:
        conn.bind()
    return conn


# memberOf entries with the required name below the Group Base DN that are
# checked against the Group Search Filter (one BASE read each).
_MAX_MEMBER_OF_CANDIDATES = 5


def _entry_matches(conn: Connection, dn: str, search_filter: str) -> bool:
    """Whether the entry at `dn` exists and matches `search_filter`."""
    try:
        conn.search(
            search_base=dn,
            search_filter=search_filter,
            search_scope=BASE,
            attributes=["cn"],
            size_limit=1,
        )
    except _UNAVAILABLE_ERRORS:
        raise
    except LDAPNoSuchObjectResult:
        return False
    except LDAPException as exc:
        raise LdapGroupSearchError(str(exc) or exc.__class__.__name__) from exc
    return bool(conn.entries)


def _check_required_group(
    conn: Connection,
    cfg: LdapEffectiveConfig,
    user_dn: str,
    username: str,
    entry_attrs: dict[str, Any],
) -> bool:
    """Return True if the user is a member of `cfg.required_group`.

    Raises `LdapGroupSearchError` when the directory search fails for a reason
    other than the server being unavailable, so a configuration error is not
    reported as "not a member".
    """
    required = cfg.required_group.strip()
    if not required:
        return True

    required_is_dn = "=" in required
    required_cn = _extract_rdn_value(required) if required_is_dn else required
    required_cn_lower = required_cn.lower()
    required_parts = _normalize_dn(required) if required_is_dn else None
    group_base_parts = _normalize_dn(cfg.group_base_dn or cfg.base_dn)

    group_clause = (
        None
        if required_is_dn
        else _fill_placeholder(cfg.group_search_filter, "group", required_cn)
    )

    # 1. Fast path: check `memberOf` attribute on the user entry. Both forms
    # stay inside the same scope as the directory search below — comparing
    # only a group's first RDN would let a same-named group in any other OU
    # satisfy the gate:
    # - a full DN must match exactly (the administrator named that entry);
    # - a bare name must name a group below the Group Base DN, and that entry
    #   must match the Group Search Filter, as the search below requires.
    #   memberOf is not only groups: FreeIPA lists roles, privileges and
    #   HBAC/sudo rules there too (cn=netops,cn=roles,cn=accounts,...).
    member_of_list = _extract_str_list(entry_attrs, "memberOf")
    candidates: list[str] = []
    for group_dn in member_of_list:
        group_parts = _normalize_dn(group_dn)
        if group_parts is None:
            continue
        if required_is_dn:
            if required_parts is not None and group_parts == required_parts:
                return True
        elif (
            group_parts[0][1] == required_cn_lower
            and group_base_parts is not None
            and _dn_is_under(group_parts, group_base_parts)
        ):
            candidates.append(group_dn)
    if group_clause is not None:
        for group_dn in candidates[:_MAX_MEMBER_OF_CANDIDATES]:
            if _entry_matches(conn, group_dn, group_clause):
                return True

    # 2. Directory group search (handles OpenLDAP without memberOf overlay,
    # POSIX memberUid, uniqueMember, and Active Directory nested groups)
    escaped_dn = escape_filter_chars(user_dn)
    escaped_uid = escape_filter_chars(username)

    member_attrs = [
        a.strip() for a in cfg.group_member_attr.split(",") if a.strip()
    ] or ["member", "uniqueMember", "memberUid"]

    membership_clauses: list[str] = []
    for attr in member_attrs:
        attr_lower = attr.lower()
        if attr_lower == "memberuid":
            membership_clauses.append(f"({attr}={escaped_uid})")
        else:
            membership_clauses.append(f"({attr}={escaped_dn})")
            membership_clauses.append(f"({attr}={escaped_uid})")
            if cfg.provider_type == "active_directory" and attr_lower == "member":
                membership_clauses.append(
                    f"(member:1.2.840.113556.1.4.1941:={escaped_dn})"
                )

    membership_or = (
        f"(|{''.join(membership_clauses)})"
        if len(membership_clauses) > 1
        else membership_clauses[0]
    )

    if required_is_dn:
        # Only the group entry itself (BASE scope), matching the exact-DN
        # memberOf check above. A SUBTREE search here would accept membership
        # of any group below the DN -- an OU entered as Required Group, or a
        # group with child entries, would let in members of every group under
        # it. AD's in-chain matching rule still resolves nesting on the entry.
        search_base = required
        search_filter = membership_or
        search_scope = BASE
    else:
        search_base = cfg.group_base_dn or cfg.base_dn
        search_filter = f"(&{group_clause}{membership_or})"
        search_scope = SUBTREE

    try:
        conn.search(
            search_base=search_base,
            search_filter=search_filter,
            search_scope=search_scope,
            attributes=["cn"],
            size_limit=1,
        )
        return bool(conn.entries)
    except _UNAVAILABLE_ERRORS:
        raise
    except LDAPException as exc:
        raise LdapGroupSearchError(str(exc) or exc.__class__.__name__) from exc


def authenticate_ldap_user(
    *,
    username: str,
    password: str,
    raw_config: dict[str, Any] | None,
    secret: str | None,
    effective: LdapEffectiveConfig | None = None,
) -> LdapAuthOutcome:
    """Authenticate `username` + `password` against priority-ordered LDAP servers.

    Failover rules (#404):
    - Only socket/TLS/connection unavailability triggers failover to the next server.
    - Invalid credentials, user-not-found, or missing required group membership
      terminate immediately without failing over.

    One connection per server: the service account searches for the user
    and checks the group, then the same connection rebinds as the user to
    verify the password. The group verdict is only reported after the
    password is accepted, so a wrong password never learns group membership.

    `effective` lets a caller that already built the config skip a rebuild.
    """
    clean_username = username.strip()
    if not clean_username or not password:
        return LdapAuthOutcome(
            ok=False,
            reason="invalid_credentials",
            message="Username and password are required.",
        )

    cfg = effective or build_effective_ldap_config(raw_config, secret)
    if not cfg.servers or not cfg.base_dn:
        return LdapAuthOutcome(
            ok=False,
            reason="misconfigured",
            message="LDAP servers or Base DN are not configured.",
        )
    # Also covers a Bind DN with no password: ldap3 refuses an empty
    # simple-bind password before sending anything, which caught as a
    # connection error would read as "server unreachable".
    problem = configuration_problem(cfg)
    if problem:
        return LdapAuthOutcome(ok=False, reason="misconfigured", message=problem)

    failed_servers: list[tuple[str, str]] = []

    for target in cfg.servers:
        conn: Connection | None = None
        try:
            conn = _open_server_connection(
                target=target,
                cfg=cfg,
                bind_dn=cfg.bind_dn,
                bind_password=cfg.bind_password,
            )
        except _UNAVAILABLE_ERRORS as exc:
            err_msg = str(exc) or exc.__class__.__name__
            logger.warning(
                "LDAP server %s (priority %d) unreachable: %s",
                target.url,
                target.priority,
                err_msg,
            )
            failed_servers.append((target.url, err_msg))
            continue
        except LDAPInvalidCredentialsResult:
            logger.error(
                "LDAP service bind failed on %s: invalid Bind DN credentials",
                target.url,
            )
            return LdapAuthOutcome(
                ok=False,
                reason="misconfigured",
                message="LDAP service account bind failed (invalid Bind DN credentials).",
                server_used=target.url,
                failover_occurred=len(failed_servers) > 0,
                failed_servers=failed_servers,
            )
        except LDAPException as exc:
            # The server answered (e.g. invalidDNSyntax for a malformed Bind
            # DN): every replica would say the same, so no failover.
            err_msg = str(exc) or exc.__class__.__name__
            logger.error("LDAP service bind failed on %s: %s", target.url, err_msg)
            return LdapAuthOutcome(
                ok=False,
                reason="misconfigured",
                message=f"LDAP service account bind failed: {err_msg}",
                server_used=target.url,
                failover_occurred=len(failed_servers) > 0,
                failed_servers=failed_servers,
            )

        def _fail(
            reason: str,
            message: str,
            identity: LdapIdentity | None = None,
            server: str = target.url,
        ) -> LdapAuthOutcome:
            return LdapAuthOutcome(
                ok=False,
                reason=reason,
                message=message,
                identity=identity,
                server_used=server,
                failover_occurred=len(failed_servers) > 0,
                failed_servers=failed_servers,
            )

        try:
            search_filter = _format_user_filter(cfg.user_search_filter, clean_username)
            requested_attrs = sorted(
                {
                    cfg.username_attr,
                    cfg.email_attr,
                    cfg.full_name_attr,
                    "memberOf",
                    "mail",
                    "cn",
                    "uid",
                    "sAMAccountName",
                }
                | ({cfg.unique_id_attr} if cfg.unique_id_attr else set())
            )
            try:
                conn.search(
                    search_base=cfg.user_base_dn,
                    search_filter=search_filter,
                    search_scope=SUBTREE,
                    attributes=requested_attrs,
                    size_limit=2,
                )
            except _UNAVAILABLE_ERRORS as exc:
                err_msg = str(exc) or exc.__class__.__name__
                logger.warning(
                    "LDAP server %s dropped during search: %s", target.url, err_msg
                )
                failed_servers.append((target.url, err_msg))
                continue
            except LDAPException as exc:
                # noSuchObject (wrong User Base DN), insufficientAccessRights, a
                # malformed filter: the same on every replica, so no failover.
                logger.error("LDAP user search failed on %s: %s", target.url, exc)
                return _fail(
                    "misconfigured",
                    "LDAP user search failed; check the User Base DN, the user "
                    "search filter and the service account's read rights.",
                )

            entries = list(conn.entries)
            if not entries:
                return _fail("user_not_found", "User not found in LDAP directory.")
            if len(entries) > 1:
                # e.g. one entry matched on sAMAccountName and another on
                # userPrincipalName: binding as whichever came first would sign
                # in as an arbitrary account.
                logger.warning(
                    "LDAP user search on %s matched more than one entry for %r",
                    target.url,
                    clean_username,
                )
                return _fail(
                    "ambiguous_user",
                    "The username matches more than one LDAP entry; narrow the "
                    "user search filter.",
                )

            entry = entries[0]
            user_dn = str(entry.entry_dn)
            entry_attrs: dict[str, Any] = (
                entry.entry_attributes_as_dict
                if hasattr(entry, "entry_attributes_as_dict")
                else {}
            )

            resolved_uid = (
                _extract_first_str(entry_attrs, cfg.username_attr) or clean_username
            )
            resolved_name = _extract_first_str(entry_attrs, cfg.full_name_attr)
            ldap_id = _extract_unique_id(entry, cfg.unique_id_attr)
            if ldap_id is None:
                if cfg.unique_id_attr:
                    logger.warning(
                        "LDAP entry %s has no readable %s; keying the account on "
                        "its username instead",
                        user_dn,
                        cfg.unique_id_attr,
                    )
                ldap_id = resolved_uid.lower()

            # Optional custom Required LDAP Group check — run as the service
            # account before the rebind below, reported only after it.
            in_group = True
            group_error: LdapGroupSearchError | None = None
            if cfg.required_group:
                try:
                    in_group = _check_required_group(
                        conn=conn,
                        cfg=cfg,
                        user_dn=user_dn,
                        username=resolved_uid,
                        entry_attrs=entry_attrs,
                    )
                except _UNAVAILABLE_ERRORS as exc:
                    err_msg = str(exc) or exc.__class__.__name__
                    failed_servers.append((target.url, err_msg))
                    continue
                except LdapGroupSearchError as exc:
                    group_error = exc

            # Verify the user's password: simple bind as user_dn on the same
            # connection (no second TCP/TLS handshake).
            try:
                _rebind_as_user(conn, user_dn, password)
            except LDAPInvalidCredentialsResult:
                return _fail(
                    "invalid_credentials", "Invalid LDAP username or password."
                )
            except _UNAVAILABLE_ERRORS as exc:
                # Server dropped between search and user bind -> failover
                err_msg = str(exc) or exc.__class__.__name__
                failed_servers.append((target.url, err_msg))
                continue
            except LDAPException:
                return _fail("invalid_credentials", "LDAP user bind failed.")

            if group_error is not None:
                # noSuchObject, insufficientAccessRights, a malformed group
                # filter: the same on every replica, so no failover.
                logger.error(
                    "LDAP group membership search failed on %s: %s",
                    target.url,
                    group_error,
                )
                return _fail(
                    "misconfigured",
                    "LDAP group membership search failed; check the "
                    "Required Group, the Group Base DN, the group search "
                    "filter and the service account's read rights.",
                )
            if not in_group:
                return _fail(
                    "group_denied",
                    f"User '{resolved_uid}' is not a member of required LDAP "
                    f"group '{cfg.required_group}'.",
                    identity=LdapIdentity(
                        ldap_id=ldap_id,
                        user_dn=user_dn,
                        email=_extract_first_str(entry_attrs, cfg.email_attr) or "",
                        full_name=resolved_name,
                        username=resolved_uid,
                    ),
                )

            resolved_email = _valid_email(
                _extract_first_str(entry_attrs, cfg.email_attr)
            )
            if resolved_email is None and cfg.fallback_email_domain:
                safe_local = re.sub(r"[^a-zA-Z0-9._+-]", "_", resolved_uid.lower())
                resolved_email = _valid_email(
                    f"{safe_local}@{cfg.fallback_email_domain}"
                )
            if resolved_email is None:
                return _fail(
                    "no_email",
                    f"LDAP account '{resolved_uid}' has no valid '{cfg.email_attr}' "
                    "address and no fallback email domain is configured.",
                )

            return LdapAuthOutcome(
                ok=True,
                reason="ok",
                message="LDAP authentication succeeded.",
                identity=LdapIdentity(
                    ldap_id=ldap_id,
                    user_dn=user_dn,
                    email=resolved_email,
                    full_name=resolved_name,
                    username=resolved_uid,
                ),
                server_used=target.url,
                failover_occurred=len(failed_servers) > 0,
                failed_servers=failed_servers,
            )
        finally:
            if conn is not None:
                try:
                    conn.unbind()
                except Exception:
                    pass

    return LdapAuthOutcome(
        ok=False,
        reason="unavailable",
        message="All configured LDAP servers are unreachable.",
        failover_occurred=len(failed_servers) > 0,
        failed_servers=failed_servers,
    )


def check_ldap_servers_connection(
    *,
    raw_config: dict[str, Any] | None,
    secret: str | None,
) -> LdapTestConnectionResponse:
    """Test TCP/TLS connectivity, Bind DN, and failover across all configured LDAP servers.

    Every server is probed, but the verdict follows `authenticate_ldap_user`:
    sign-in moves past a server only when it is unavailable, and stops at the
    first one that answers. A rejected service bind there fails sign-in even
    when a later server would accept it, so it fails this test too.
    """
    cfg = build_effective_ldap_config(raw_config, secret)
    if not cfg.servers:
        return LdapTestConnectionResponse(
            ok=False,
            message="No LDAP servers configured.",
        )
    problem = configuration_problem(cfg)
    if problem:
        return LdapTestConnectionResponse(ok=False, message=problem)

    results: list[LdapServerDiagResult] = []
    # The server sign-in would stop at: (index, url, error or None when bound)
    deciding: tuple[int, str, str | None] | None = None

    for idx, target in enumerate(cfg.servers):
        t0 = time.monotonic()
        conn: Connection | None = None
        try:
            conn = _open_server_connection(
                target=target,
                cfg=cfg,
                bind_dn=cfg.bind_dn,
                bind_password=cfg.bind_password,
            )
            elapsed_ms = round((time.monotonic() - t0) * 1000.0, 1)
            if deciding is None:
                deciding = (idx, target.url, None)
            results.append(
                LdapServerDiagResult(
                    server=target.url,
                    priority=target.priority,
                    ok=True,
                    latency_ms=elapsed_ms,
                    tls_active=bool(target.use_ssl or target.start_tls),
                    bind_ok=True,
                )
            )
        except _UNAVAILABLE_ERRORS as exc:
            # Sign-in moves on to the next server.
            elapsed_ms = round((time.monotonic() - t0) * 1000.0, 1)
            results.append(
                LdapServerDiagResult(
                    server=target.url,
                    priority=target.priority,
                    ok=False,
                    latency_ms=elapsed_ms,
                    tls_active=bool(target.use_ssl or target.start_tls),
                    bind_ok=False,
                    error=str(exc) or exc.__class__.__name__,
                )
            )
        except Exception as exc:
            # The server answered and refused (invalid credentials, a
            # malformed Bind DN, ...): sign-in stops here.
            if isinstance(exc, LDAPInvalidCredentialsResult):
                error = "Service Bind failed: invalid Bind DN or password."
            else:
                error = f"Service Bind failed: {str(exc) or exc.__class__.__name__}"
            if deciding is None:
                deciding = (idx, target.url, error)
            elapsed_ms = round((time.monotonic() - t0) * 1000.0, 1)
            results.append(
                LdapServerDiagResult(
                    server=target.url,
                    priority=target.priority,
                    ok=False,
                    latency_ms=elapsed_ms,
                    tls_active=bool(target.use_ssl or target.start_tls),
                    bind_ok=False,
                    error=error,
                )
            )
        finally:
            if conn is not None:
                try:
                    conn.unbind()
                except Exception:
                    pass

    active_server: str | None = None
    failover_occurred = False
    if deciding is None:
        ok = False
        msg = "All configured LDAP servers are unreachable."
    else:
        idx, url, refusal = deciding
        ok = refusal is None
        if refusal is not None:
            msg = (
                f"{url} rejected the service bind ({refusal}). Sign-in stops at "
                "the first server that answers, so it will fail."
            )
        else:
            active_server = url
            failover_occurred = idx > 0
            if failover_occurred:
                msg = (
                    "Higher-priority server(s) unreachable; failover succeeded "
                    f"using {url}."
                )
            else:
                msg = f"Connected and bound successfully to {url}."

    return LdapTestConnectionResponse(
        ok=ok,
        active_server=active_server,
        failover_occurred=failover_occurred,
        servers=results,
        message=msg,
    )


def check_ldap_user_auth(
    *,
    username: str,
    password: str,
    raw_config: dict[str, Any] | None,
    secret: str | None,
) -> LdapTestAuthResponse:
    """Diagnostic helper to test user authentication and optional custom group check."""
    cfg = build_effective_ldap_config(raw_config, secret)
    outcome = authenticate_ldap_user(
        username=username,
        password=password,
        raw_config=raw_config,
        secret=secret,
        effective=cfg,
    )
    group_check_passed: bool | None = None
    if cfg.required_group:
        if outcome.ok:
            group_check_passed = True
        elif outcome.reason == "group_denied":
            group_check_passed = False

    return LdapTestAuthResponse(
        ok=outcome.ok,
        server_used=outcome.server_used,
        failover_occurred=outcome.failover_occurred,
        user_dn=outcome.identity.user_dn if outcome.identity else None,
        ldap_id=outcome.identity.ldap_id if outcome.identity else None,
        email=outcome.identity.email if outcome.identity else None,
        full_name=outcome.identity.full_name if outcome.identity else None,
        group_check_passed=group_check_passed,
        required_group=cfg.required_group or None,
        message=outcome.message,
    )
