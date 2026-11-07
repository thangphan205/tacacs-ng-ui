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
SECRETS = ("Sup3rSecretPw!", "shared-secret-777", "bind-pw-xyz", "rounds=")


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
