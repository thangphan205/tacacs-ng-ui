"""Secrets never stay in an audit entry's before/after values."""

import json

import pytest

from app.core.audit_redact import CHANGED, REDACTED, redact_audit_values, redact_text


def j(**kw: object) -> str:
    return json.dumps(kw, separators=(",", ":"))


def loaded(raw: str | None) -> dict[str, object]:
    assert raw is not None
    return json.loads(raw)  # type: ignore[no-any-return]


def test_create_and_delete_redact_the_secret_keep_the_rest() -> None:
    new = j(username="abc", password="$6$rounds=1$salt$hash", password_type="crypt")
    _, out = redact_audit_values("TacacsUser", None, new)
    assert loaded(out) == {
        "username": "abc",
        "password": REDACTED,
        "password_type": "crypt",  # not a secret
    }
    old_out, _ = redact_audit_values("TacacsUser", new, None)
    assert loaded(old_out)["password"] == REDACTED


def test_update_flags_a_changed_secret_only_on_the_new_side() -> None:
    old = j(username="abc", password="hash-1")
    same = redact_audit_values("TacacsUser", old, j(username="abc", password="hash-1"))
    assert [loaded(v)["password"] for v in same] == [REDACTED, REDACTED]

    diff = redact_audit_values("TacacsUser", old, j(username="abc", password="hash-2"))
    assert [loaded(v)["password"] for v in diff] == [REDACTED, CHANGED]
    assert "hash-" not in "".join(v for v in diff if v)


def test_a_secret_set_for_the_first_time_is_not_flagged_as_changed() -> None:
    out = redact_audit_values(
        "TacacsUser", j(username="a", password=None), j(username="a", password="h")
    )
    assert loaded(out[0])["password"] is None  # nothing to hide
    assert loaded(out[1])["password"] == REDACTED


@pytest.mark.parametrize(
    ("entity_type", "field"),
    [
        ("Host", "secret_key"),
        ("Host", "radius_secret_key"),
        ("TacacsUser", "password"),
        ("User", "hashed_password"),
        ("ApiKey", "key_hash"),
        ("AuthProviderConfig", "encrypted_secret"),
        ("SiemConfig", "webhook_token"),
        ("Anything", "secret_key"),  # by field name, whatever the type
    ],
)
def test_secret_field_names_are_masked_for_any_entity(
    entity_type: str, field: str
) -> None:
    _, out = redact_audit_values(entity_type, None, j(name="x", **{field: "S3CRET"}))
    assert loaded(out)[field] == REDACTED
    assert "S3CRET" not in (out or "")


def test_null_and_empty_secrets_are_left_alone() -> None:
    raw = j(name="h", secret_key=None, parent="core")
    assert redact_audit_values("Host", None, raw) == (None, raw)
    raw = j(name="h", secret_key="")
    assert redact_audit_values("Host", None, raw) == (None, raw)


def test_config_text_is_masked_but_filename_and_state_stay() -> None:
    new = j(filename="cfg-1.cfg", active=True, config_text="host { key = hunter2 }")
    _, out = redact_audit_values("TacacsConfig", None, new)
    assert loaded(out) == {
        "filename": "cfg-1.cfg",
        "active": True,
        "config_text": REDACTED,
    }


@pytest.mark.parametrize(
    "key", ["LDAP_PASSWD", "ldap_password", "BIND_PW", "API_TOKEN", "TLS_KEY", "SECRET"]
)
def test_mavis_value_is_masked_for_secret_looking_keys(key: str) -> None:
    _, out = redact_audit_values("Mavis", None, j(mavis_key=key, mavis_value="pw"))
    assert loaded(out) == {"mavis_key": key, "mavis_value": REDACTED}


@pytest.mark.parametrize(
    "key",
    ["LDAP_HOSTS", "LDAP_BASE", "LDAP_USER", "LDAP_FILTER", "TACACS_GROUP_PREFIX"],
)
def test_mavis_value_is_kept_for_other_keys(key: str) -> None:
    raw = j(mavis_key=key, mavis_value="ldaps://ipa.example.com:636")
    assert redact_audit_values("Mavis", None, raw) == (None, raw)


def test_nothing_to_hide_returns_the_same_strings() -> None:
    old, new = j(name="a", description="x"), j(name="b", description="x")
    out = redact_audit_values("Host", old, new)
    assert out[0] is old and out[1] is new


@pytest.mark.parametrize("raw", [None, "", "not json", "[1,2]", "null", '"s"'])
def test_values_that_are_not_a_json_object_pass_through(raw: str | None) -> None:
    assert redact_audit_values("TacacsUser", raw, raw) == (raw, raw)


def test_config_option_cleartext_and_crypt_passwords_are_scrubbed() -> None:
    block = """user radclear {
        password login = clear "Rad-e5743209427b"
        password pap = login
        password chap = clear "Rad-e5743209427b"
        password ms-chap = clear "Rad-e5743209427b"
        password enable = crypt "$6$rounds=656000$salt$hash"
        member = tacacs_super_user
    }"""
    raw = j(name="custom_users", config_option=block, description="temp block")
    old_out, new_out = redact_audit_values("ConfigurationOption", raw, None)
    assert new_out is None
    assert "Rad-e5743209427b" not in (old_out or "")
    assert "$6$rounds=656000$salt$hash" not in (old_out or "")
    parsed = loaded(old_out)
    assert parsed["name"] == "custom_users"
    assert 'password login = clear "[redacted]"' in str(parsed["config_option"])
    assert "password pap = login" in str(parsed["config_option"])
    assert 'password chap = clear "[redacted]"' in str(parsed["config_option"])
    assert 'password ms-chap = clear "[redacted]"' in str(parsed["config_option"])
    assert 'password enable = crypt "[redacted]"' in str(parsed["config_option"])
    assert "member = tacacs_super_user" in str(parsed["config_option"])


@pytest.mark.parametrize(
    ("snippet", "secret"),
    [
        ('password login = clear unquotedSecret99\n', "unquotedSecret99"),
        ('host sw1 { key = "host-key-123" }', "host-key-123"),
        ('host sw1 { radius.key = "rad-key-456" }', "rad-key-456"),
        ('host sw1 { key = unquotedKey789 }', "unquotedKey789"),
        ('shared-key = "shared-secret-abc"', "shared-secret-abc"),
        ('setenv LDAP_PASSWD = "ldap-bind-pw"', "ldap-bind-pw"),
        ("Authorization: Bearer super.secret.token", "super.secret.token"),
        ("created key tngk_abc123456789xyz", "tngk_abc123456789xyz"),
        (
            "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ1c2VyMSIsImV4cCI6MX0.signature12345",
            "signature12345",
        ),
        (
            "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA\n-----END RSA PRIVATE KEY-----",
            "MIIEpAIBAAKCAQEA",
        ),
    ],
)
def test_redact_text_scrubs_inline_secrets_and_is_idempotent(
    snippet: str, secret: str
) -> None:
    once = redact_text(snippet)
    assert secret not in once
    assert REDACTED in once
    assert redact_text(once) == once


def test_nested_config_json_secrets_are_scrubbed() -> None:
    nested = json.dumps({"bot_token": "123456:ABC-DEF", "chat_id": "-100999"})
    raw = j(name="ops-telegram", channel_type="telegram", config_json=nested)
    _, out = redact_audit_values("NotificationChannel", None, raw)
    assert "123456:ABC-DEF" not in (out or "")
    inner = json.loads(str(loaded(out)["config_json"]))
    assert inner == {"bot_token": REDACTED, "chat_id": "-100999"}


def test_free_text_fields_across_entities_are_scrubbed() -> None:
    for entity, field in (
        ("TacacsNgSetting", "radius_dictionary_extra"),
        ("ProfileScript", "value"),
        ("RulesetScript", "value"),
        ("SiemConfig", "webhook_url"),
    ):
        raw = j(name="x", **{field: 'password login = clear "SENTINEL_999"'})
        _, out = redact_audit_values(entity, None, raw)
        assert "SENTINEL_999" not in (out or "")
        assert REDACTED in (out or "")
