"""Secrets never stay in an audit entry's before/after values."""

import json

import pytest

from app.core.audit_redact import CHANGED, REDACTED, redact_audit_values


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
