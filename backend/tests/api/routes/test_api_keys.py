from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.core.security import hash_api_key
from app.crud import api_keys
from app.models import ApiKey, AuditLog
from tests.utils.utils import random_lower_string

BASE = f"{settings.API_V1_STR}/api_keys"


def test_create_api_key_returns_plaintext_once(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    name = random_lower_string()
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": name, "scopes": "mcp:read,mcp:generate"},
    )
    assert r.status_code == 200, r.text
    created = r.json()
    plaintext = created["plaintext_key"]
    assert plaintext.startswith("tngk_")
    assert created["key_prefix"] == plaintext[:20]
    assert "key_hash" not in created

    # The stored row holds only the digest.
    row = db.exec(select(ApiKey).where(ApiKey.id == created["id"])).one()
    assert row.key_hash == hash_api_key(plaintext)

    # Reading it back never re-exposes the secret.
    r = client.get(f"{BASE}/{created['id']}", headers=superuser_token_headers)
    assert r.status_code == 200
    assert "plaintext_key" not in r.json()
    assert "key_hash" not in r.json()


def test_create_api_key_writes_audit_log_without_hash(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    )
    assert r.status_code == 200
    created = r.json()

    entry = db.exec(
        select(AuditLog)
        .where(AuditLog.entity_type == "ApiKey")
        .where(AuditLog.entity_id == created["id"])
        .where(AuditLog.action == "CREATE")
    ).first()
    assert entry is not None
    assert entry.new_values is not None
    assert "key_hash" not in entry.new_values
    assert "plaintext_key" not in entry.new_values


def test_create_api_key_rejects_unknown_user(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={
            "name": random_lower_string(),
            "user_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    assert r.status_code == 404


def test_read_api_keys_never_exposes_hash(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    )
    r = client.get(f"{BASE}/", headers=superuser_token_headers)
    assert r.status_code == 200
    payload = r.json()
    assert payload["count"] >= 1
    for item in payload["data"]:
        assert "key_hash" not in item
        assert "plaintext_key" not in item


def test_normal_user_cannot_manage_api_keys(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=normal_user_token_headers,
        json={"name": random_lower_string()},
    )
    assert r.status_code == 403

    r = client.get(f"{BASE}/", headers=normal_user_token_headers)
    assert r.status_code == 403


def test_normal_user_can_list_own_api_keys(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{BASE}/me", headers=normal_user_token_headers)
    assert r.status_code == 200
    assert "data" in r.json()


def test_revoke_api_key_stops_authentication(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    )
    created = r.json()
    plaintext = created["plaintext_key"]
    assert api_keys.resolve_api_key(plaintext) is not None

    r = client.delete(f"{BASE}/{created['id']}", headers=superuser_token_headers)
    assert r.status_code == 200

    assert api_keys.resolve_api_key(plaintext) is None

    r = client.get(f"{BASE}/{created['id']}", headers=superuser_token_headers)
    assert r.json()["revoked_at"] is not None


def test_revoke_missing_api_key_returns_404(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.delete(
        f"{BASE}/00000000-0000-0000-0000-000000000000",
        headers=superuser_token_headers,
    )
    assert r.status_code == 404


def test_create_api_key_rejects_invalid_allowed_ip(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": random_lower_string(), "allowed_ips": "not-an-ip"},
    )
    assert r.status_code == 422


def test_create_api_key_normalizes_allowed_ips(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": random_lower_string(), "allowed_ips": "  10.0.0.1 ,10.0.0.2"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["allowed_ips"] == "10.0.0.1,10.0.0.2"


def test_update_allowed_ips_only_changes_allowed_ips(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": "keep-my-name", "scopes": "mcp:read"},
    )
    created = r.json()

    r = client.patch(
        f"{BASE}/{created['id']}",
        headers=superuser_token_headers,
        json={"allowed_ips": "10.0.0.0/24"},
    )
    assert r.status_code == 200, r.text
    updated = r.json()
    assert updated["allowed_ips"] == "10.0.0.0/24"
    assert updated["name"] == "keep-my-name"
    assert updated["scopes"] == "mcp:read"


def test_update_allowed_ips_rejects_invalid_entry(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    )
    created = r.json()

    r = client.patch(
        f"{BASE}/{created['id']}",
        headers=superuser_token_headers,
        json={"allowed_ips": "garbage"},
    )
    assert r.status_code == 422


def test_update_allowed_ips_missing_key_returns_404(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.patch(
        f"{BASE}/00000000-0000-0000-0000-000000000000",
        headers=superuser_token_headers,
        json={"allowed_ips": "10.0.0.0/24"},
    )
    assert r.status_code == 404


def test_normal_user_cannot_update_allowed_ips(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    r = client.post(
        f"{BASE}/",
        headers=superuser_token_headers,
        json={"name": random_lower_string()},
    )
    created = r.json()

    r = client.patch(
        f"{BASE}/{created['id']}",
        headers=normal_user_token_headers,
        json={"allowed_ips": "10.0.0.0/24"},
    )
    assert r.status_code == 403
