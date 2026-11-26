"""Unit tests for non-superuser response redaction helpers (no DB required)."""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.routes.configuration_options import _option_for_user
from app.api.routes.hosts import _host_for_user
from app.api.routes.mavises import _mavis_for_user
from app.mcp_server.redact import REDACTED
from app.models import ConfigurationOption, Host, Mavis

NOW = datetime(2026, 11, 26, tzinfo=timezone.utc)
SUPER = SimpleNamespace(is_superuser=True)
NORMAL = SimpleNamespace(is_superuser=False)


def test_host_for_user_masks_keys_for_non_superuser_only() -> None:
    host = Host(
        id=uuid.uuid4(),
        name="clab-mikrotik",
        ipv4_address="172.19.0.1/32",
        secret_key="tacacs-shared-secret",
        radius_secret_key="radius-shared-secret",
        created_at=NOW,
        updated_at=NOW,
    )
    normal_pub = _host_for_user(host, NORMAL)  # type: ignore[arg-type]
    assert normal_pub.secret_key == REDACTED
    assert normal_pub.radius_secret_key == REDACTED
    # Original ORM instance must not be mutated
    assert host.secret_key == "tacacs-shared-secret"

    super_pub = _host_for_user(host, SUPER)  # type: ignore[arg-type]
    assert super_pub.secret_key == "tacacs-shared-secret"
    assert super_pub.radius_secret_key == "radius-shared-secret"


def test_mavis_for_user_masks_secret_keys_for_non_superuser_only() -> None:
    secret_mavis = Mavis(
        id=uuid.uuid4(),
        mavis_key="LDAP_PASSWD",
        mavis_value="wKwLx3QtsOz6xPUkgKzIrz%9",
        created_at=NOW,
        updated_at=NOW,
    )
    plain_mavis = Mavis(
        id=uuid.uuid4(),
        mavis_key="LDAP_HOSTS",
        mavis_value="ldaps://ipa.example.com:636",
        created_at=NOW,
        updated_at=NOW,
    )
    assert _mavis_for_user(secret_mavis, NORMAL).mavis_value == REDACTED  # type: ignore[arg-type]
    assert (
        _mavis_for_user(plain_mavis, NORMAL).mavis_value  # type: ignore[arg-type]
        == "ldaps://ipa.example.com:636"
    )
    assert (
        _mavis_for_user(secret_mavis, SUPER).mavis_value  # type: ignore[arg-type]
        == "wKwLx3QtsOz6xPUkgKzIrz%9"
    )


def test_option_for_user_scrubs_inline_secrets_for_non_superuser_only() -> None:
    opt = ConfigurationOption(
        id=uuid.uuid4(),
        name="custom_users",
        config_option='user radtest {\n    password login = clear "Rad-e5743209427b"\n    password pap = login\n}',
        created_at=NOW,
        updated_at=NOW,
    )
    normal_pub = _option_for_user(opt, NORMAL, [])  # type: ignore[arg-type]
    assert "Rad-e5743209427b" not in normal_pub.config_option
    assert REDACTED in normal_pub.config_option
    assert "password pap = login" in normal_pub.config_option

    super_pub = _option_for_user(opt, SUPER, [])  # type: ignore[arg-type]
    assert "Rad-e5743209427b" in super_pub.config_option
