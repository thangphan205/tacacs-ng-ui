"""SIEM Integration API: config CRUD, token handling, test send, status."""

import json
from collections.abc import Generator
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.core.security import decrypt_secret
from app.crud import audit_logs as audit_logs_crud
from app.crud import siem_tailer, tacacs_siem
from app.models import AuditLog, AuditLogCreate, SiemConfig, SiemSinkTestResult

URL = f"{settings.API_V1_STR}/siem"


@pytest.fixture(autouse=True)
def clean_config(db: Session) -> Generator[None, None, None]:
    saved = db.get(SiemConfig, 1)
    saved_copy = saved.model_dump() if saved else None
    db.exec(delete(SiemConfig))  # type: ignore[call-overload]
    db.commit()
    yield
    db.rollback()
    db.exec(delete(SiemConfig))  # type: ignore[call-overload]
    if saved_copy:
        db.add(SiemConfig(**saved_copy))
    db.commit()


def _put(client: TestClient, headers: dict[str, str], body: dict[str, Any]) -> Any:
    return client.put(f"{URL}/config", headers=headers, json=body)


def test_requires_superuser(
    client: TestClient, normal_user_token_headers: dict[str, str]
) -> None:
    for method, path in (
        ("get", "/config"),
        ("put", "/config"),
        ("post", "/test"),
        ("get", "/status"),
    ):
        r = client.request(
            method, f"{URL}{path}", headers=normal_user_token_headers, json={}
        )
        assert r.status_code == 403, (method, path)


def test_defaults_when_no_row(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    body = client.get(f"{URL}/config", headers=superuser_token_headers).json()
    assert body["enabled"] is False
    assert body["webhook_token_is_set"] is False
    assert body["syslog_port"] == 514


def test_update_stores_encrypted_token_and_never_returns_it(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    r = _put(
        client,
        superuser_token_headers,
        {
            "enabled": True,
            "webhook_url": "https://splunk.example:8088/services/collector/event",
            "webhook_token": "s3cret",
            "syslog_host": "syslog.example",
            "syslog_protocol": "tcp",
            "ship_authentication": True,
            "ship_audit": True,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["webhook_token_is_set"] is True
    assert "s3cret" not in r.text and "webhook_token" not in body
    db.expire_all()
    cfg = db.get(SiemConfig, 1)
    assert cfg is not None and cfg.webhook_token_encrypted
    assert decrypt_secret(cfg.webhook_token_encrypted) == "s3cret"

    # Omitted token keeps it, "" clears it.
    _put(client, superuser_token_headers, {"syslog_port": 6514})
    db.expire_all()
    assert db.get(SiemConfig, 1).webhook_token_encrypted  # type: ignore[union-attr]
    body = _put(client, superuser_token_headers, {"webhook_token": ""}).json()
    assert body["webhook_token_is_set"] is False

    # "" clears a URL / host.
    body = _put(client, superuser_token_headers, {"syslog_host": ""}).json()
    assert body["syslog_host"] is None


def test_update_is_audit_logged_without_token(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    _put(client, superuser_token_headers, {"webhook_token": "s3cret", "enabled": True})
    entry = db.exec(
        select(AuditLog)
        .where(AuditLog.entity_type == "SiemConfig")
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    assert entry is not None
    assert "s3cret" not in (entry.new_values or "")
    assert json.loads(entry.new_values or "{}")["webhook_token_is_set"] is True


@pytest.mark.parametrize(
    "body",
    [
        {"syslog_port": 0},
        {"syslog_port": 70000},
        {"syslog_protocol": "tls"},
        {"webhook_url": "ftp://x.example"},
        {"webhook_url": "javascript:alert(1)"},
        {"syslog_host": "bad host;rm"},
    ],
)
def test_validation(
    client: TestClient, superuser_token_headers: dict[str, str], body: dict[str, Any]
) -> None:
    assert _put(client, superuser_token_headers, body).status_code == 422


def test_standby_refuses_update(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "NODE_ROLE", "standby")
    assert _put(client, superuser_token_headers, {"enabled": True}).status_code == 403


def test_test_send_needs_a_destination(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.post(f"{URL}/test", headers=superuser_token_headers)
    assert r.status_code == 400


def test_test_send_reports_results(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Saved but disabled: the test still uses the saved destination.
    _put(client, superuser_token_headers, {"syslog_host": "127.0.0.1"})
    seen: list[tacacs_siem.SiemTarget] = []

    def fake(target: tacacs_siem.SiemTarget) -> list[SiemSinkTestResult]:
        seen.append(target)
        return [SiemSinkTestResult(sink="syslog", ok=False, error="refused")]

    monkeypatch.setattr(tacacs_siem, "send_test_event", fake)
    r = client.post(f"{URL}/test", headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json() == {
        "results": [{"sink": "syslog", "ok": False, "error": "refused"}]
    }
    assert seen[0].syslog_host == "127.0.0.1"


def test_status_reads_the_local_status_file(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "status.json"
    real = siem_tailer.read_status
    monkeypatch.setattr(siem_tailer, "read_status", lambda: real(str(path)))

    body = client.get(f"{URL}/status", headers=superuser_token_headers).json()
    assert body["running"] is False

    now = datetime.now(timezone.utc)
    path.write_text(
        json.dumps(
            {
                "node_name": "primary",
                "running": True,
                "updated_at": now.isoformat(),
                "events_sent": {"authentication": 3},
            }
        )
    )
    body = client.get(f"{URL}/status", headers=superuser_token_headers).json()
    assert body["running"] is True
    assert body["events_sent"] == {"authentication": 3}

    stale = (now - timedelta(minutes=5)).isoformat()
    path.write_text(json.dumps({"running": True, "updated_at": stale}))
    body = client.get(f"{URL}/status", headers=superuser_token_headers).json()
    assert body["running"] is False


def test_audit_entries_follow_ship_audit(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[AuditLog] = []
    whens: list[datetime | None] = []

    def fake_forward(
        _t: tacacs_siem.SiemTarget, log: AuditLog, *, when: datetime | None = None
    ) -> None:
        sent.append(log)
        whens.append(when)

    monkeypatch.setattr(tacacs_siem, "forward_audit_log", fake_forward)

    def write() -> None:
        audit_logs_crud.create_audit_log(
            session=db,
            audit_log_in=AuditLogCreate(action="UPDATE", entity_type="Host"),
            user_id=None,
            user_email="a@example.com",
            ip_address=None,
        )

    db.add(SiemConfig(id=1, enabled=True, syslog_host="127.0.0.1", ship_audit=False))
    db.commit()
    write()
    assert sent == []

    cfg = db.get(SiemConfig, 1)
    assert cfg is not None
    cfg.ship_audit = True
    db.add(cfg)
    db.commit()
    write()
    assert len(sent) == 1
    # The time sent is the aware creation time, not the naive value read back.
    when = whens[0]
    assert when is not None and when.tzinfo is not None
    assert abs((datetime.now(timezone.utc) - when).total_seconds()) < 60

    cfg.enabled = False
    db.add(cfg)
    db.commit()
    write()
    assert len(sent) == 1
