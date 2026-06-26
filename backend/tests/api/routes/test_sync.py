from datetime import datetime, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes.sync import _get_or_create_ha_state
from app.core.config import settings
from app.main import _seed_ha_config
from app.models import HaPeerNode, HaState


def test_get_ha_info_primary(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    with patch("app.api.routes.sync.settings.NODE_ROLE", "primary"):
        r = client.get(
            f"{settings.API_V1_STR}/sync/ha-info",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["node_role"] == "primary"
        assert "peers" in data
        assert "last_sync_at" in data


def test_get_ha_info_standby_no_hastate_row(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    # Simulate missing HaState row — standby must not attempt a DB write
    for hs in db.exec(select(HaState)).all():
        db.delete(hs)
    db.commit()

    with patch("app.api.routes.sync.settings.NODE_ROLE", "standby"):
        r = client.get(
            f"{settings.API_V1_STR}/sync/ha-info",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["node_role"] == "standby"
        assert data["peers"] == []
        assert data["last_sync_at"] is None

        # HaState row must NOT have been written (standby DB is read-only)
        assert db.exec(select(HaState)).first() is None


def test_get_ha_info_standby_last_sync_at(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    # Pre-populate HaState with a last_received_at timestamp
    for hs in db.exec(select(HaState)).all():
        db.delete(hs)
    ts = datetime(2026, 6, 26, 10, 0, 0, tzinfo=timezone.utc)
    db.add(HaState(id=1, last_received_at=ts))
    db.commit()

    with patch("app.api.routes.sync.settings.NODE_ROLE", "standby"):
        r = client.get(
            f"{settings.API_V1_STR}/sync/ha-info",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["last_sync_at"] is not None
        assert "2026-06-26" in data["last_sync_at"]


def test_get_ha_info_standby_peer_backend_url_from_env(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    with (
        patch("app.api.routes.sync.settings.NODE_ROLE", "standby"),
        patch("app.api.routes.sync.settings.PEER_BACKEND_URL", "http://primary:8000"),
    ):
        r = client.get(
            f"{settings.API_V1_STR}/sync/ha-info",
            headers=superuser_token_headers,
        )
        assert r.status_code == 200
        data = r.json()
        assert data["peer_backend_url"] == "http://primary:8000"


def test_get_or_create_ha_state_standby_no_write(db: Session) -> None:
    # When HaState row is missing and NODE_ROLE=standby, must return unsaved instance
    for hs in db.exec(select(HaState)).all():
        db.delete(hs)
    db.commit()

    with patch("app.api.routes.sync.settings.NODE_ROLE", "standby"):
        state = _get_or_create_ha_state(db)

    assert state is not None
    assert state.last_received_at is None
    # Row must NOT have been committed
    assert db.exec(select(HaState)).first() is None


def test_seed_ha_config_upserts_new_peer_urls(db: Session) -> None:
    # Pre-populate with one existing peer (simulates replicated data after promotion)
    for p in db.exec(select(HaPeerNode)).all():
        db.delete(p)
    db.commit()
    db.add(HaPeerNode(name="existing", url="http://standby:8000"))
    db.commit()

    # Patch underlying fields — peer_urls is a computed_field and cannot be
    # patched directly as an attribute (delattr fails on cleanup).
    with (
        patch("app.main.settings.NODE_ROLE", "primary"),
        patch("app.main.settings.PEER_BACKEND_URL", "http://primary:8000"),
        patch("app.main.settings.PEER_NODES", ""),
    ):
        _seed_ha_config(db)

    urls = {p.url for p in db.exec(select(HaPeerNode)).all()}
    assert "http://standby:8000" in urls   # existing preserved
    assert "http://primary:8000" in urls   # new URL added


def test_seed_ha_config_no_duplicate_peers(db: Session) -> None:
    for p in db.exec(select(HaPeerNode)).all():
        db.delete(p)
    db.commit()
    db.add(HaPeerNode(name="peer", url="http://standby:8000"))
    db.commit()

    with (
        patch("app.main.settings.NODE_ROLE", "primary"),
        patch("app.main.settings.PEER_BACKEND_URL", "http://standby:8000"),
        patch("app.main.settings.PEER_NODES", ""),
    ):
        _seed_ha_config(db)

    peers = db.exec(select(HaPeerNode)).all()
    assert sum(1 for p in peers if p.url == "http://standby:8000") == 1
