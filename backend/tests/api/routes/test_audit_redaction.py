"""Writes through the API leave no secret in the audit log (REST, MCP, direct)."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.audit_redact import CHANGED, REDACTED
from app.core.config import settings
from app.crud import audit_logs as audit_logs_crud
from app.models import AuditLog, AuditLogCreate

API = settings.API_V1_STR
SECRETS = (
    "Sup3rSecretPw!",
    "shared-secret-777",
    "radius-secret-888",
    "bind-pw-xyz",
    "rounds=",
)


def entries(db: Session, entity_type: str, entity_id: str) -> list[AuditLog]:
    db.expire_all()
    rows = db.exec(
        select(AuditLog)
        .where(AuditLog.entity_type == entity_type, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.created_at)  # type: ignore[arg-type]
    ).all()
    return list(rows)


def no_secret(rows: list[AuditLog]) -> None:
    text = " ".join((r.old_values or "") + (r.new_values or "") for r in rows)
    for secret in SECRETS:
        assert secret not in text, secret


@pytest.fixture()
def cleanup(db: Session) -> Generator[list[str], None, None]:
    ids: list[str] = []
    yield ids
    for entity_id in ids:
        for row in db.exec(select(AuditLog).where(AuditLog.entity_id == entity_id)):
            db.delete(row)
    db.commit()


def test_tacacs_user_password_is_redacted_create_update_delete(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    cleanup: list[str],
) -> None:
    name = f"redact-{uuid.uuid4().hex[:8]}"
    r = client.post(
        f"{API}/tacacs_users/",
        headers=superuser_token_headers,
        json={
            "username": name,
            "password_type": "crypt",
            "password": "Sup3rSecretPw!",
            "member": "tacacs_super_user",
        },
    )
    assert r.status_code == 200, r.text
    uid = r.json()["id"]
    cleanup.append(uid)
    r = client.put(
        f"{API}/tacacs_users/{uid}",
        headers=superuser_token_headers,
        json={"password": "An0therSecret!", "description": "changed"},
    )
    assert r.status_code == 200, r.text
    r = client.delete(f"{API}/tacacs_users/{uid}", headers=superuser_token_headers)
    assert r.status_code == 200

    rows = entries(db, "TacacsUser", uid)
    assert [x.action for x in rows] == ["CREATE", "UPDATE", "DELETE"]
    no_secret(rows)
    assert "An0therSecret!" not in " ".join((x.new_values or "") for x in rows)
    create, update, delete = rows
    assert f'"username":"{name}"' in (create.new_values or "")
    assert f'"password":"{REDACTED}"' in (create.new_values or "")
    assert f'"password":"{CHANGED}"' in (update.new_values or "")  # a change is visible
    assert f'"password":"{REDACTED}"' in (delete.old_values or "")


def test_host_secret_key_is_redacted(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    cleanup: list[str],
) -> None:
    name = f"redact-host-{uuid.uuid4().hex[:8]}"
    r = client.post(
        f"{API}/hosts/",
        headers=superuser_token_headers,
        json={
            "name": name,
            "ipv4_address": "192.0.2.77/32",
            "secret_key": "shared-secret-777",
            "radius_secret_key": "radius-secret-888",
        },
    )
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    cleanup.append(hid)
    client.delete(f"{API}/hosts/{hid}", headers=superuser_token_headers)

    rows = entries(db, "Host", hid)
    assert len(rows) == 2
    no_secret(rows)
    assert f'"name":"{name}"' in (rows[0].new_values or "")  # the rest is still there
    assert f'"radius_secret_key":"{REDACTED}"' in (rows[0].new_values or "")


def test_mavis_secret_value_is_redacted_but_plain_values_are_not(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    cleanup: list[str],
) -> None:
    ids = []
    for key, value in (
        (f"TEST_LDAP_PASSWD_{uuid.uuid4().hex[:6]}", "bind-pw-xyz"),
        (f"TEST_LDAP_HOSTS_{uuid.uuid4().hex[:6]}", "ldaps://ipa.example.com:636"),
    ):
        r = client.post(
            f"{API}/mavises/",
            headers=superuser_token_headers,
            json={"mavis_key": key, "mavis_value": value},
        )
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
        cleanup.append(r.json()["id"])
    secret_rows = entries(db, "Mavis", ids[0])
    plain_rows = entries(db, "Mavis", ids[1])
    no_secret(secret_rows)
    assert "ldaps://ipa.example.com:636" in (plain_rows[0].new_values or "")
    for mid in ids:
        client.delete(f"{API}/mavises/{mid}", headers=superuser_token_headers)


def test_any_caller_is_covered_not_only_the_routes(
    db: Session, cleanup: list[str]
) -> None:
    """MCP writes and future callers hand raw dumps to log_entity_action."""
    entity_id = str(uuid.uuid4())
    cleanup.append(entity_id)
    audit_logs_crud.create_audit_log(
        session=db,
        audit_log_in=AuditLogCreate(
            action="CREATE",
            entity_type="TacacsConfig",
            entity_id=entity_id,
            new_values='{"filename":"c.cfg","active":false,'
            '"config_text":"key = shared-secret-777"}',
        ),
        user_id=None,
        user_email="t@example.com",
        ip_address=None,
    )
    [row] = entries(db, "TacacsConfig", entity_id)
    no_secret([row])
    assert '"filename":"c.cfg"' in (row.new_values or "")


def test_audit_log_endpoints_require_authentication(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
    db: Session,
    cleanup: list[str],
) -> None:
    entity_id = str(uuid.uuid4())
    cleanup.append(entity_id)
    row = audit_logs_crud.create_audit_log(
        session=db,
        audit_log_in=AuditLogCreate(
            action="CREATE",
            entity_type="Host",
            entity_id=entity_id,
            description="auth check",
        ),
        user_id=None,
        user_email="t@example.com",
        ip_address=None,
    )
    assert row is not None

    # Anonymous access must be rejected with 401.
    assert client.get(f"{API}/audit_logs/").status_code == 401
    assert client.get(f"{API}/audit_logs/{row.id}").status_code == 401

    # Superusers can read any audit record; unbounded limit is rejected.
    assert (
        client.get(
            f"{API}/audit_logs/?limit=1", headers=superuser_token_headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"{API}/audit_logs/{row.id}", headers=superuser_token_headers
        ).status_code
        == 200
    )
    assert (
        client.get(
            f"{API}/audit_logs/?limit=1000", headers=superuser_token_headers
        ).status_code
        == 422
    )

    # Non-superusers cannot read other users' audit records.
    assert (
        client.get(
            f"{API}/audit_logs/{row.id}", headers=normal_user_token_headers
        ).status_code
        == 403
    )
    list_resp = client.get(
        f"{API}/audit_logs/?limit=100", headers=normal_user_token_headers
    )
    assert list_resp.status_code == 200
    returned_ids = {item["id"] for item in list_resp.json()["data"]}
    assert str(row.id) not in returned_ids


def test_configuration_option_cleartext_passwords_never_appear_in_audit_api(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    cleanup: list[str],
) -> None:
    sentinel = "SENTINEL-ClearPw-998877"
    name = f"redact-cfgopt-{uuid.uuid4().hex[:8]}"
    config_block = (
        "user radclear {\n"
        f'    password login = clear "{sentinel}"\n'
        "    password pap = login\n"
        f'    password chap = clear "{sentinel}"\n'
        f'    password ms-chap = clear "{sentinel}"\n'
        "    member = tacacs_super_user\n"
        "}"
    )
    r = client.post(
        f"{API}/configuration_options/",
        headers=superuser_token_headers,
        json={"name": name, "config_option": config_block, "description": "test"},
    )
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    cleanup.append(cid)

    r = client.put(
        f"{API}/configuration_options/{cid}",
        headers=superuser_token_headers,
        json={
            "name": name,
            "config_option": config_block.replace(sentinel, "SENTINEL-Updated-112233"),
            "description": "updated",
        },
    )
    assert r.status_code == 200, r.text
    r = client.delete(
        f"{API}/configuration_options/{cid}", headers=superuser_token_headers
    )
    assert r.status_code == 200

    rows = entries(db, "ConfigurationOption", cid)
    assert [x.action for x in rows] == ["CREATE", "UPDATE", "DELETE"]
    for row in rows:
        resp = client.get(f"{API}/audit_logs/{row.id}", headers=superuser_token_headers)
        assert resp.status_code == 200
        body = resp.text
        assert sentinel not in body
        assert "SENTINEL-Updated-112233" not in body
        assert REDACTED in body
        assert "password pap = login" in body


def test_audit_description_inline_secrets_are_scrubbed(
    db: Session, cleanup: list[str]
) -> None:
    entity_id = str(uuid.uuid4())
    cleanup.append(entity_id)
    audit_logs_crud.create_audit_log(
        session=db,
        audit_log_in=AuditLogCreate(
            action="CREATE",
            entity_type="ConfigurationOption",
            entity_id=entity_id,
            description='Failed with Authorization: Bearer secret-bearer-999 and tngk_abc123456789',
        ),
        user_id=None,
        user_email="t@example.com",
        ip_address=None,
    )
    [row] = entries(db, "ConfigurationOption", entity_id)
    assert row.description is not None
    assert "secret-bearer-999" not in row.description
    assert "tngk_abc123456789" not in row.description
    assert REDACTED in row.description
