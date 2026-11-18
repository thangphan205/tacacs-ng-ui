from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import MagicMock

import pytest
from ldap3.core.exceptions import (
    LDAPInvalidCredentialsResult,
    LDAPNoSuchObjectResult,
    LDAPSocketOpenError,
)

from app.core.ldap_auth import (
    LDAP_PROVIDER_PRESETS,
    LdapEffectiveConfig,
    LdapServerTarget,
    _format_user_filter,
    authenticate_ldap_user,
    build_effective_ldap_config,
    check_ldap_servers_connection,
    check_ldap_user_auth,
    invalid_ldap_server_entries,
    parse_ldap_servers,
)


class _FakeEntry:
    def __init__(
        self,
        dn: str,
        attrs: dict[str, Any],
        raw: dict[str, list[bytes]] | None = None,
    ) -> None:
        self.entry_dn = dn
        self.entry_attributes_as_dict = attrs
        self.entry_raw_attributes = raw or {}


def test_presets_cover_all_four_providers() -> None:
    assert set(LDAP_PROVIDER_PRESETS.keys()) == {
        "active_directory",
        "freeipa",
        "openldap",
        "generic",
    }
    assert (
        LDAP_PROVIDER_PRESETS["active_directory"]["username_attr"] == "sAMAccountName"
    )
    assert LDAP_PROVIDER_PRESETS["freeipa"]["username_attr"] == "uid"
    assert LDAP_PROVIDER_PRESETS["openldap"]["username_attr"] == "uid"


def test_parse_ldap_servers_orders_by_priority() -> None:
    cfg = {
        "servers_json": (
            '[{"url": "ldaps://ipa03.example.com:636", "priority": 3}, '
            '{"url": "ldaps://ipa01.example.com:636", "priority": 1}, '
            '{"url": "ldap://ipa02.example.com", "priority": 2}]'
        )
    }
    servers = parse_ldap_servers(cfg, default_start_tls=True)
    assert [s.url for s in servers] == [
        "ldaps://ipa01.example.com:636",
        "ldap://ipa02.example.com:389",
        "ldaps://ipa03.example.com:636",
    ]
    assert servers[0].use_ssl is True
    assert servers[0].start_tls is False
    assert servers[1].use_ssl is False
    assert servers[1].start_tls is True


def test_format_user_filter_escapes_ldap_injection() -> None:
    rendered = _format_user_filter(
        "(&(objectClass=person)(uid={username}))", "admin*)(|(uid=*"
    )
    assert "admin\\2a\\29\\28|\\28uid=\\2a" in rendered
    assert "admin*)(|(uid=*" not in rendered


def test_authenticate_ldap_user_failover_on_socket_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str | None]] = []

    def fake_open(
        target: LdapServerTarget,
        cfg: LdapEffectiveConfig,
        bind_dn: str | None,
        bind_password: str | None = None,
    ) -> Any:
        _ = bind_password
        calls.append((target.url, bind_dn))
        if target.host == "ipa01.example.com":
            raise LDAPSocketOpenError("Connection refused")
        conn = MagicMock()
        if bind_dn == cfg.bind_dn:
            conn.entries = [
                _FakeEntry(
                    "uid=jdoe,cn=users,cn=accounts,dc=example,dc=com",
                    {
                        "uid": ["jdoe"],
                        "mail": ["jdoe@example.com"],
                        "cn": ["Jane Doe"],
                    },
                )
            ]
        return conn

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)

    outcome = authenticate_ldap_user(
        username="jdoe",
        password="correct-password",
        raw_config={
            "provider_type": "freeipa",
            "hosts": "ldaps://ipa01.example.com:636, ldaps://ipa02.example.com:636",
            "base_dn": "dc=example,dc=com",
            "bind_dn": "uid=svc,cn=users,dc=example,dc=com",
        },
        secret="svc-secret",
    )

    assert outcome.ok is True
    assert outcome.failover_occurred is True
    assert outcome.server_used == "ldaps://ipa02.example.com:636"
    assert len(outcome.failed_servers) == 1
    assert outcome.failed_servers[0][0] == "ldaps://ipa01.example.com:636"
    assert outcome.identity is not None
    assert outcome.identity.ldap_id == "jdoe"
    assert outcome.identity.email == "jdoe@example.com"
    assert outcome.identity.full_name == "Jane Doe"


def test_authenticate_ldap_user_does_not_failover_on_invalid_password(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited_servers: list[str] = []

    def fake_open(
        target: LdapServerTarget,
        cfg: LdapEffectiveConfig,
        bind_dn: str | None,
        bind_password: str | None = None,
    ) -> Any:
        _ = bind_password
        visited_servers.append(target.host)
        assert bind_dn == cfg.bind_dn, "the user binds on the same connection"
        conn = MagicMock()
        conn.entries = [
            _FakeEntry(
                "uid=jdoe,cn=users,dc=example,dc=com",
                {"uid": ["jdoe"], "mail": ["jdoe@example.com"]},
            )
        ]
        conn.rebind.side_effect = LDAPInvalidCredentialsResult("invalidCredentials")
        return conn

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)

    outcome = authenticate_ldap_user(
        username="jdoe",
        password="wrong-password",
        raw_config={
            "provider_type": "freeipa",
            "hosts": "ldaps://ipa01.example.com:636, ldaps://ipa02.example.com:636",
            "base_dn": "dc=example,dc=com",
            "bind_dn": "uid=svc,cn=users,dc=example,dc=com",
        },
        secret="svc-secret",
    )

    assert outcome.ok is False
    assert outcome.reason == "invalid_credentials"
    assert outcome.failover_occurred is False
    # Secondary server (ipa02) must NEVER be contacted on wrong password
    assert "ipa02.example.com" not in visited_servers


def test_authenticate_ldap_user_custom_required_group_member_of_and_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def make_fake_open(user_attrs: dict[str, Any], group_found: bool) -> Any:
        def fake_open(
            target: LdapServerTarget,
            cfg: LdapEffectiveConfig,
            bind_dn: str | None,
            bind_password: str | None = None,
        ) -> Any:
            _ = (target, bind_password)
            conn = MagicMock()
            if bind_dn == cfg.bind_dn:

                def fake_search(**kwargs: Any) -> bool:
                    if "(cn=my-custom-group)" not in kwargs.get("search_filter", ""):
                        conn.entries = [
                            _FakeEntry(
                                "uid=alice,ou=people,dc=example,dc=com",
                                user_attrs,
                            )
                        ]
                    else:
                        conn.entries = (
                            [
                                _FakeEntry(
                                    "cn=my-custom-group,ou=groups,dc=example,dc=com",
                                    {"cn": ["my-custom-group"]},
                                )
                            ]
                            if group_found
                            else []
                        )
                    return True

                conn.search.side_effect = fake_search
            return conn

        return fake_open

    cfg = {
        "provider_type": "openldap",
        "hosts": "ldap://ldap01.example.com:389",
        "base_dn": "dc=example,dc=com",
        "bind_dn": "cn=admin,dc=example,dc=com",
        "required_group": "my-custom-group",
        "fallback_email_domain": "corp.example.com",
    }

    # Case 1: OpenLDAP without memberOf overlay, matched via group search (memberUid/member)
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        make_fake_open({"uid": ["alice"]}, group_found=True),
    )
    ok_outcome = authenticate_ldap_user(
        username="alice",
        password="secret",
        raw_config=cfg,
        secret="bindpw",
    )
    assert ok_outcome.ok is True
    assert ok_outcome.identity is not None
    # Synthesizes the fallback email when the LDAP entry has no mail attribute
    assert ok_outcome.identity.email == "alice@corp.example.com"

    # Case 2: Not in custom group -> denied without failover
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        make_fake_open({"uid": ["alice"]}, group_found=False),
    )
    denied_outcome = authenticate_ldap_user(
        username="alice",
        password="secret",
        raw_config=cfg,
        secret="bindpw",
    )
    assert denied_outcome.ok is False
    assert denied_outcome.reason == "group_denied"
    assert "my-custom-group" in denied_outcome.message


def test_connection_and_auth_diagnostics(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_open(
        target: LdapServerTarget,
        cfg: LdapEffectiveConfig,
        bind_dn: str | None,
        bind_password: str | None = None,
    ) -> Any:
        _ = (cfg, bind_dn, bind_password)
        if target.host == "ipa01.example.com":
            raise LDAPSocketOpenError("Timed out")
        conn = MagicMock()
        conn.entries = [
            _FakeEntry(
                "uid=bob,cn=users,dc=example,dc=com",
                {
                    "uid": ["bob"],
                    "mail": ["bob@example.com"],
                    "cn": ["Bob Smith"],
                    "memberOf": ["cn=netops-custom,cn=groups,dc=example,dc=com"],
                },
            )
        ]
        return conn

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)
    cfg = {
        "provider_type": "freeipa",
        "hosts": "ldaps://ipa01.example.com:636, ldaps://ipa02.example.com:636",
        "base_dn": "dc=example,dc=com",
        "bind_dn": "uid=svc,cn=users,dc=example,dc=com",
        "required_group": "netops-custom",
    }

    conn_res = check_ldap_servers_connection(raw_config=cfg, secret="pw")
    assert conn_res.ok is True
    assert conn_res.failover_occurred is True
    assert conn_res.active_server == "ldaps://ipa02.example.com:636"
    assert len(conn_res.servers) == 2
    assert conn_res.servers[0].ok is False
    assert conn_res.servers[1].ok is True

    auth_res = check_ldap_user_auth(
        username="bob", password="pw", raw_config=cfg, secret="pw"
    )
    assert auth_res.ok is True
    assert auth_res.group_check_passed is True
    assert auth_res.required_group == "netops-custom"
    assert auth_res.email == "bob@example.com"


def test_build_effective_config_defaults() -> None:
    eff = build_effective_ldap_config({"provider_type": "active_directory"}, "secret")
    assert eff.username_attr == "sAMAccountName"
    assert eff.full_name_attr == "displayName"


_BASE_CFG: dict[str, Any] = {
    "provider_type": "openldap",
    "hosts": "ldap://ldap01.example.com:389, ldap://ldap02.example.com:389",
    "base_dn": "dc=example,dc=com",
    "bind_dn": "cn=svc,dc=example,dc=com",
}


def _single_entry_open(
    entry: _FakeEntry,
    *,
    search_error: dict[str, Exception] | None = None,
    group_found: bool = False,
    visited: list[str] | None = None,
) -> Any:
    """Fake connection factory: the service conn finds `entry`; user binds succeed."""

    def fake_open(
        target: LdapServerTarget,
        cfg: LdapEffectiveConfig,
        bind_dn: str | None,
        bind_password: str | None = None,
    ) -> Any:
        _ = bind_password
        if visited is not None:
            visited.append(target.host)
        conn = MagicMock()
        if bind_dn != cfg.bind_dn:
            return conn

        def fake_search(**kwargs: Any) -> bool:
            if search_error and target.host in search_error:
                raise search_error[target.host]
            is_user_search = kwargs.get("search_base") == cfg.user_base_dn and (
                "objectClass=inetOrgPerson" in kwargs.get("search_filter", "")
            )
            if is_user_search:
                conn.entries = [entry]
            else:
                conn.entries = (
                    [_FakeEntry("cn=g,dc=example,dc=com", {})] if group_found else []
                )
            return True

        conn.search.side_effect = fake_search
        return conn

    return fake_open


def _alice(
    attrs: dict[str, Any] | None = None, raw: dict[str, list[bytes]] | None = None
) -> _FakeEntry:
    return _FakeEntry(
        "uid=alice,ou=people,dc=example,dc=com",
        {"uid": ["alice"], "mail": ["alice@example.com"], **(attrs or {})},
        raw,
    )


def test_required_group_dn_must_match_exactly(monkeypatch: pytest.MonkeyPatch) -> None:
    """A same-named group in another OU must not satisfy a DN gate."""
    required = "cn=admins,ou=groups,dc=example,dc=com"
    cfg = {**_BASE_CFG, "required_group": required}

    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(
            _alice({"memberOf": ["cn=admins,ou=evil,dc=example,dc=com"]})
        ),
    )
    denied = authenticate_ldap_user(
        username="alice", password="pw", raw_config=cfg, secret="s"
    )
    assert denied.reason == "group_denied"

    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(_alice({"memberOf": [required.upper()]})),
    )
    allowed = authenticate_ldap_user(
        username="alice", password="pw", raw_config=cfg, secret="s"
    )
    assert allowed.ok is True


def test_search_error_is_misconfigured_not_a_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str] = []
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(
            _alice(),
            search_error={"ldap01.example.com": LDAPNoSuchObjectResult("noSuchObject")},
            visited=visited,
        ),
    )
    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=_BASE_CFG, secret="s"
    )
    assert outcome.ok is False
    assert outcome.reason == "misconfigured"
    # A wrong base DN is wrong on every replica: no failover.
    assert "ldap02.example.com" not in visited


def test_connection_drop_during_search_fails_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(
            _alice(),
            search_error={"ldap01.example.com": LDAPSocketOpenError("reset by peer")},
        ),
    )
    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=_BASE_CFG, secret="s"
    )
    assert outcome.ok is True
    assert outcome.server_used == "ldap://ldap02.example.com:389"
    assert outcome.failover_occurred is True


def test_ambiguous_username_is_refused_before_any_user_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    binds: list[str | None] = []

    def fake_open(
        target: LdapServerTarget,
        cfg: LdapEffectiveConfig,
        bind_dn: str | None,
        bind_password: str | None = None,
    ) -> Any:
        _ = (target, cfg, bind_password)
        binds.append(bind_dn)
        conn = MagicMock()
        conn.entries = [
            _FakeEntry("uid=alice,ou=a,dc=example,dc=com", {"uid": ["alice"]}),
            _FakeEntry("uid=alice,ou=b,dc=example,dc=com", {"uid": ["alice"]}),
        ]
        return conn

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)
    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=_BASE_CFG, secret="s"
    )
    assert outcome.reason == "ambiguous_user"
    assert binds == [_BASE_CFG["bind_dn"]]


def test_ldap_id_is_the_immutable_directory_id(monkeypatch: pytest.MonkeyPatch) -> None:
    guid = uuid.UUID("b6e4c3a2-1f0e-4d5c-9b8a-7f6e5d4c3b2a")
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(_alice(raw={"entryUUID": [str(guid).upper().encode()]})),
    )
    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=_BASE_CFG, secret="s"
    )
    assert outcome.identity is not None
    assert outcome.identity.ldap_id == str(guid)

    # AD's objectGUID is 16 raw bytes, little-endian, shown as a GUID string.
    ad_cfg = {**_BASE_CFG, "unique_id_attr": "objectGUID"}
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(_alice(raw={"objectGUID": [guid.bytes_le]})),
    )
    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=ad_cfg, secret="s"
    )
    assert outcome.identity is not None
    assert outcome.identity.ldap_id == str(guid)

    # An explicit empty attribute keys the account on the username.
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(_alice(raw={"entryUUID": [str(guid).encode()]})),
    )
    outcome = authenticate_ldap_user(
        username="alice",
        password="pw",
        raw_config={**_BASE_CFG, "unique_id_attr": ""},
        secret="s",
    )
    assert outcome.identity is not None
    assert outcome.identity.ldap_id == "alice"


@pytest.mark.parametrize("fallback", ["", "ldap.local"])
def test_no_usable_email_is_refused(
    monkeypatch: pytest.MonkeyPatch, fallback: str
) -> None:
    """`.local` is rejected by EmailStr: storing it would break /users/me."""
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(_FakeEntry("uid=bob,dc=example,dc=com", {"uid": ["bob"]})),
    )
    outcome = authenticate_ldap_user(
        username="bob",
        password="pw",
        raw_config={**_BASE_CFG, "fallback_email_domain": fallback},
        secret="s",
    )
    assert outcome.ok is False
    assert outcome.reason == "no_email"


def test_bare_group_name_in_member_of_must_sit_under_group_base_dn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A same-named group outside the Group Base DN must not satisfy the gate."""
    cfg = {
        **_BASE_CFG,
        "required_group": "netops",
        "group_base_dn": "ou=groups,dc=example,dc=com",
    }

    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(
            _alice({"memberOf": ["cn=netops,ou=contractors,dc=example,dc=com"]})
        ),
    )
    denied = authenticate_ldap_user(
        username="alice", password="pw", raw_config=cfg, secret="s"
    )
    assert denied.reason == "group_denied"

    # Under the base, in the directory's own spelling of the DN.
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        _single_entry_open(
            _alice({"memberOf": ["CN=NetOps, OU=Groups,DC=example,DC=com"]})
        ),
    )
    allowed = authenticate_ldap_user(
        username="alice", password="pw", raw_config=cfg, secret="s"
    )
    assert allowed.ok is True


def test_group_search_error_is_misconfigured_not_group_denied(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    visited: list[str] = []

    def fake_open(
        target: LdapServerTarget,
        cfg: LdapEffectiveConfig,
        bind_dn: str | None,
        bind_password: str | None = None,
    ) -> Any:
        _ = (cfg, bind_dn, bind_password)
        visited.append(target.host)
        conn = MagicMock()

        def fake_search(**kwargs: Any) -> bool:
            if kwargs.get("attributes") == ["cn"]:
                raise LDAPNoSuchObjectResult("noSuchObject")
            conn.entries = [_alice()]
            return True

        conn.search.side_effect = fake_search
        return conn

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)
    outcome = authenticate_ldap_user(
        username="alice",
        password="pw",
        raw_config={**_BASE_CFG, "required_group": "cn=gone,dc=example,dc=com"},
        secret="s",
    )
    assert outcome.reason == "misconfigured"
    # Wrong on every replica: no failover.
    assert "ldap02.example.com" not in visited


def test_bad_server_port_is_dropped_not_a_crash() -> None:
    servers = parse_ldap_servers(
        {
            "servers_json": (
                '[{"url": "ldap://dc2.example.com:99999", "priority": 1},'
                ' {"url": "ldaps://dc1.example.com:636", "priority": 2}]'
            )
        }
    )
    # The bad entry no longer drops every entry after it.
    assert [s.host for s in servers] == ["dc1.example.com"]

    assert parse_ldap_servers({"hosts": "ldap://dc2.example.com:99999"}) == []
    assert parse_ldap_servers({"hosts": "ldap://dc2.example.com:abc"}) == []

    outcome = authenticate_ldap_user(
        username="alice",
        password="pw",
        raw_config={"hosts": "ldap://dc2.example.com:99999", "base_dn": "dc=x"},
        secret=None,
    )
    assert outcome.reason == "misconfigured"


def test_invalid_ldap_server_entries_names_each_bad_entry() -> None:
    assert invalid_ldap_server_entries(
        {
            "hosts": "ldaps://dc1.example.com:636, ldap://dc2.example.com:99999",
            "servers_json": '[{"url": "ldap://dc2.example.com:99999"}]',
        }
    ) == ["ldap://dc2.example.com:99999"]
    assert invalid_ldap_server_entries({"hosts": "http://dc1.example.com"}) == [
        "http://dc1.example.com"
    ]
    assert invalid_ldap_server_entries({"servers_json": "not json"}) == [
        "servers_json (not valid JSON)"
    ]
    assert invalid_ldap_server_entries({"hosts": "dc1.example.com, [::1]:389"}) == []


def test_bind_dn_without_password_is_misconfigured_not_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_open(**_kwargs: Any) -> Any:
        raise AssertionError("no connection without a bind password")

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)
    monkeypatch.setattr("app.core.ldap_auth.settings.LDAP_BIND_PASSWORD", "")

    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=_BASE_CFG, secret=None
    )
    assert outcome.reason == "misconfigured"
    conn_res = check_ldap_servers_connection(raw_config=_BASE_CFG, secret=None)
    assert conn_res.ok is False
    assert "Bind Password" in conn_res.message


def test_connection_test_fails_when_first_answering_server_rejects_bind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Sign-in stops at a rejected service bind, so the test must not pass."""

    def fake_open(
        target: LdapServerTarget,
        cfg: LdapEffectiveConfig,
        bind_dn: str | None,
        bind_password: str | None = None,
    ) -> Any:
        _ = (cfg, bind_dn, bind_password)
        if target.host == "ldap01.example.com":
            raise LDAPInvalidCredentialsResult("invalidCredentials")
        return MagicMock()

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)
    res = check_ldap_servers_connection(raw_config=_BASE_CFG, secret="s")
    assert res.ok is False
    assert res.failover_occurred is False
    assert res.active_server is None
    assert "rejected the service bind" in res.message
    # Every server is still probed and reported.
    assert [s.ok for s in res.servers] == [False, True]


def test_one_connection_per_server_and_password_checked_by_rebind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str | None] = []
    conns: list[Any] = []

    def fake_open(
        target: LdapServerTarget,
        cfg: LdapEffectiveConfig,
        bind_dn: str | None,
        bind_password: str | None = None,
    ) -> Any:
        _ = (target, cfg, bind_password)
        opened.append(bind_dn)
        conn = MagicMock()
        conn.entries = [_alice()]
        conns.append(conn)
        return conn

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)
    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=_BASE_CFG, secret="s"
    )
    assert outcome.ok is True
    assert opened == [_BASE_CFG["bind_dn"]]
    conns[0].rebind.assert_called_once_with(
        user="uid=alice,ou=people,dc=example,dc=com", password="pw"
    )


def test_wrong_password_never_learns_group_membership(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The group is checked before the rebind, but reported only after it."""

    def fake_open(**_kwargs: Any) -> Any:
        conn = MagicMock()

        def fake_search(**kwargs: Any) -> bool:
            conn.entries = [] if kwargs.get("attributes") == ["cn"] else [_alice()]
            return True

        conn.search.side_effect = fake_search
        conn.rebind.side_effect = LDAPInvalidCredentialsResult("invalidCredentials")
        return conn

    monkeypatch.setattr("app.core.ldap_auth._open_server_connection", fake_open)
    outcome = authenticate_ldap_user(
        username="alice",
        password="wrong",
        raw_config={**_BASE_CFG, "required_group": "admins"},
        secret="s",
    )
    assert outcome.reason == "invalid_credentials"


def test_connections_never_follow_referrals(monkeypatch: pytest.MonkeyPatch) -> None:
    """A referral would re-bind with the same password on a host nobody set."""
    from app.core import ldap_auth

    captured: dict[str, Any] = {}

    def fake_connection(server: Any, **kwargs: Any) -> Any:
        _ = server
        captured.update(kwargs)
        return MagicMock()

    monkeypatch.setattr(ldap_auth, "Connection", fake_connection)
    cfg = build_effective_ldap_config(_BASE_CFG, "s")
    ldap_auth._open_server_connection(
        target=cfg.servers[0], cfg=cfg, bind_dn=cfg.bind_dn, bind_password="s"
    )
    assert captured["auto_referrals"] is False


def test_saved_empty_field_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core.config import settings

    monkeypatch.setattr(settings, "LDAP_REQUIRED_GROUP", "netops")
    monkeypatch.setattr(settings, "LDAP_BIND_DN", "cn=env,dc=x")
    monkeypatch.setattr(settings, "LDAP_HOSTS", "ldap://env.example.com")

    cleared = build_effective_ldap_config(
        {"required_group": "", "bind_dn": "", "hosts": ""}, None
    )
    assert cleared.required_group == ""
    assert cleared.bind_dn == ""
    assert cleared.servers == []

    from_env = build_effective_ldap_config({}, None)
    assert from_env.required_group == "netops"
    assert from_env.bind_dn == "cn=env,dc=x"
    assert [s.host for s in from_env.servers] == ["env.example.com"]


def test_service_bind_answer_ends_sign_in_but_busy_fails_over(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ldap3.core.exceptions import LDAPBusyResult, LDAPInvalidDNSyntaxResult

    def opener(first_error: Exception, visited: list[str]) -> Any:
        def fake_open(
            target: LdapServerTarget,
            cfg: LdapEffectiveConfig,
            bind_dn: str | None,
            bind_password: str | None = None,
        ) -> Any:
            _ = (cfg, bind_dn, bind_password)
            visited.append(target.host)
            if target.host == "ldap01.example.com":
                raise first_error
            conn = MagicMock()
            conn.entries = [_alice()]
            return conn

        return fake_open

    visited: list[str] = []
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        opener(LDAPInvalidDNSyntaxResult("invalidDNSyntax"), visited),
    )
    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=_BASE_CFG, secret="s"
    )
    assert outcome.reason == "misconfigured"
    assert visited == ["ldap01.example.com"]
    conn_res = check_ldap_servers_connection(raw_config=_BASE_CFG, secret="s")
    assert conn_res.ok is False
    assert "invalidDNSyntax" in conn_res.message

    visited = []
    monkeypatch.setattr(
        "app.core.ldap_auth._open_server_connection",
        opener(LDAPBusyResult("busy"), visited),
    )
    outcome = authenticate_ldap_user(
        username="alice", password="pw", raw_config=_BASE_CFG, secret="s"
    )
    assert outcome.ok is True
    assert outcome.failover_occurred is True
