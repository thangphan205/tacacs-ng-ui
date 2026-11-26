"""Unit tests for non-superuser response redaction helpers (no DB required)."""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

from app.api.routes.configuration_options import _option_for_user
from app.api.routes.hosts import _host_for_user
from app.api.routes.mavises import _mavis_for_user
from app.api.routes.notification_channels import _channel_for_user
from app.mcp_server.redact import REDACTED
from app.models import ConfigurationOption, Host, Mavis, NotificationChannel

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


def test_notification_channel_for_user_redacts_secrets_for_non_superuser_only() -> None:
    tg = NotificationChannel(
        id=uuid.uuid4(),
        name="tacacs-ng-ui-community",
        channel_type="telegram",
        config_json=json.dumps(
            {
                "bot_token": "8688903638:AAEMJPok7QSwjl-X9rNa1uKu6IXifrjb95o",
                "chat_id": "-1003904987198",
                "topic_id": "2",
            }
        ),
        enabled=True,
        created_at=NOW,
        updated_at=NOW,
    )
    normal_pub = _channel_for_user(tg, NORMAL)  # type: ignore[arg-type]
    parsed = json.loads(normal_pub.config_json)
    assert parsed["bot_token"] == REDACTED
    assert parsed["chat_id"] == "-1003904987198"
    assert parsed["topic_id"] == "2"
    assert "8688903638" not in normal_pub.config_json
    # Original ORM instance must not be mutated
    assert "8688903638" in tg.config_json

    super_pub = _channel_for_user(tg, SUPER)  # type: ignore[arg-type]
    assert "8688903638:AAEMJPok7QSwjl-X9rNa1uKu6IXifrjb95o" in super_pub.config_json

    # Slack/webhook/email channels also mask webhook_url, token, smtp_password
    email_ch = NotificationChannel(
        id=uuid.uuid4(),
        name="ops-email",
        channel_type="email",
        config_json=json.dumps(
            {
                "smtp_host": "smtp.example.com",
                "smtp_password": "app-secret-password",
                "webhook_url": "https://hooks.slack.com/services/T00/B00/XXXX",
                "token": "bearer-xyz",
            }
        ),
        enabled=True,
        created_at=NOW,
        updated_at=NOW,
    )
    email_normal = json.loads(_channel_for_user(email_ch, NORMAL).config_json)  # type: ignore[arg-type]
    assert email_normal["smtp_host"] == "smtp.example.com"
    assert email_normal["smtp_password"] == REDACTED
    assert email_normal["webhook_url"] == REDACTED
    assert email_normal["token"] == REDACTED
