from sqlmodel import Session

from app.crud.tacacs_configs import generate_tacacs_ng_config
from app.mcp_server.redact import (
    REDACTED,
    collect_secrets,
    is_secret_mavis_key,
    redact_config_text,
)

SAMPLE = """    host = SW {
        address = 10.0.0.0/24
        key = "sup3rs3cr3t"
    }
    user alice {
        password login = crypt "$6$rounds=656000$abc$def"
        member = g1
    }
        setenv LDAP_PASSWD="ldap-pw-value"
        setenv LDAP_BASE="dc=example,dc=com"
"""

SECRETS = ["sup3rs3cr3t", "$6$rounds=656000$abc$def", "ldap-pw-value"]


def test_value_pass_removes_every_secret() -> None:
    out, count = redact_config_text(SAMPLE, secrets=SECRETS)
    for secret in SECRETS:
        assert secret not in out
    assert count == 3


def test_redaction_preserves_structure() -> None:
    out, _ = redact_config_text(SAMPLE, secrets=SECRETS)
    for marker in (
        "host = SW",
        "user alice",
        "key = ",
        "password login = crypt",
        "setenv LDAP_BASE",
        "address = 10.0.0.0/24",
    ):
        assert marker in out


def test_non_secret_setenv_is_preserved() -> None:
    out, _ = redact_config_text(SAMPLE, secrets=SECRETS)
    assert "dc=example,dc=com" in out


def test_pattern_pass_catches_secrets_without_db_values() -> None:
    out, count = redact_config_text(SAMPLE, secrets=[])
    assert "sup3rs3cr3t" not in out
    assert "ldap-pw-value" not in out
    assert count == 3


def test_redaction_is_idempotent() -> None:
    once, _ = redact_config_text(SAMPLE, secrets=SECRETS)
    twice, count = redact_config_text(once, secrets=SECRETS)
    assert twice == once
    assert count == 0


def test_short_values_are_not_value_replaced() -> None:
    # "ab" is under the minimum length, so pass A skips it; pass B still masks
    # it because of the `key = "..."` shape.
    out, count = redact_config_text('group = ab\nkey = "ab"\n', secrets=["ab"])
    assert "group = ab" in out
    assert f'key = "{REDACTED}"' in out
    assert count == 1


def test_empty_secret_values_do_not_corrupt_output() -> None:
    out, count = redact_config_text("group = g1\n", secrets=["", None])  # type: ignore[list-item]
    assert out == "group = g1\n"
    assert count == 0


def test_generated_config_has_no_secrets_after_redaction(db: Session) -> None:
    config = generate_tacacs_ng_config(session=db)
    secrets = collect_secrets(session=db)
    out, _ = redact_config_text(config, secrets=secrets)
    for secret in secrets:
        if len(secret) >= 4:
            assert secret not in out


def test_pattern_pass_catches_radius_key_chap_mschap_and_setenv_variants() -> None:
    sample = """    host = clab-mikrotik {
        address = 172.19.0.1/32
        key = "16ebc4ef462e198c41a76e9289aca34b"
        radius.key = "06a8632ed458b930390cdc4b299208b1"
    }
    user radtest {
        password login = clear "Rad-e5743209427b"
        password pap = login
        password chap = clear "Rad-e5743209427b"
        password ms-chap = clear "Rad-e5743209427b"
        member = tacacs_super_user
    }
    user rawuser {
        password login = clear unquotedSecret42
    }
    setenv BIND_PW="bind-secret-99"
    setenv LDAP_HOSTS="ldaps://ipa.example.com:636"
"""
    out, count = redact_config_text(sample, secrets=[])
    for leaked in (
        "16ebc4ef462e198c41a76e9289aca34b",
        "06a8632ed458b930390cdc4b299208b1",
        "Rad-e5743209427b",
        "unquotedSecret42",
        "bind-secret-99",
    ):
        assert leaked not in out
    assert "password pap = login" in out
    assert 'setenv LDAP_HOSTS="ldaps://ipa.example.com:636"' in out
    assert count >= 7
    # Idempotent
    twice, count2 = redact_config_text(out, secrets=[])
    assert twice == out
    assert count2 == 0


def test_is_secret_mavis_key() -> None:
    assert is_secret_mavis_key("LDAP_PASSWD")
    assert is_secret_mavis_key("BIND_PW")
    assert is_secret_mavis_key("TLS_KEY")
    assert not is_secret_mavis_key("LDAP_HOSTS")
    assert not is_secret_mavis_key("LDAP_BASE")
    assert not is_secret_mavis_key(None)
