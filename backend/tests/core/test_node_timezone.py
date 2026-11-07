"""HA nodes must run in the log time zone; mismatches are detected and shown."""

import logging
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes import sync
from app.core import node_timezone as nt
from app.core.config import settings
from app.main import _warn_on_timezone_mismatch
from app.models import TacacsNgSetting

NOW = datetime(2026, 11, 7, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    ("a", "b", "same"),
    [
        ("Asia/Ho_Chi_Minh", "Asia/Ho_Chi_Minh", True),
        ("Asia/Saigon", "Asia/Ho_Chi_Minh", True),  # alias
        ("UTC", "Etc/UTC", True),
        (None, "UTC", True),
        ("Asia/Ho_Chi_Minh", "Asia/Bangkok", True),  # same offset, no DST
        ("Asia/Ho_Chi_Minh", "UTC", False),
        # Same offset in November, different in summer (DST rules differ).
        ("America/New_York", "America/Bogota", False),
        ("Not/AZone", "Not/AZone", True),
        ("Not/AZone", "UTC", False),
    ],
)
def test_same_zone(a: str | None, b: str | None, same: bool) -> None:
    assert nt.same_zone(a, b, now=NOW) is same


def test_node_timezone_reads_tz(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TZ", ":Asia/Ho_Chi_Minh")
    assert nt.node_timezone() == "Asia/Ho_Chi_Minh"


@pytest.fixture()
def log_zone(db: Session):  # type: ignore[no-untyped-def]
    setting = db.exec(select(TacacsNgSetting)).first()
    assert setting is not None
    original = setting.timezone

    def set_zone(zone: str | None) -> None:
        setting.timezone = zone  # type: ignore[assignment]
        db.add(setting)
        db.commit()

    yield set_zone
    set_zone(original)


def test_ha_info_reports_zone_mismatch(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    log_zone,  # type: ignore[no-untyped-def]
) -> None:
    monkeypatch.setenv("TZ", "UTC")
    log_zone("Asia/Ho_Chi_Minh")
    body = client.get(
        f"{settings.API_V1_STR}/sync/ha-info", headers=superuser_token_headers
    ).json()
    assert body["timezone"] == "UTC"
    assert body["log_timezone"] == "Asia/Ho_Chi_Minh"
    assert body["timezone_ok"] is False

    log_zone("Etc/UTC")
    body = client.get(
        f"{settings.API_V1_STR}/sync/ha-info", headers=superuser_token_headers
    ).json()
    assert body["timezone_ok"] is True


def test_peer_zone_is_compared_with_the_log_zone(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    log_zone,  # type: ignore[no-untyped-def]
) -> None:
    from app.models import HaPeerNode

    monkeypatch.setenv("TZ", "Asia/Ho_Chi_Minh")
    log_zone("Asia/Ho_Chi_Minh")
    peer = HaPeerNode(name="tz-peer", url="http://tz-peer.invalid:8000")
    db.add(peer)
    db.commit()
    try:
        sync._peers_cache[peer.url] = {
            "available": True,
            "timezone": "UTC",
            "ts": float("inf"),  # fresh: no network call
        }
        body = client.get(
            f"{settings.API_V1_STR}/sync/ha-info", headers=superuser_token_headers
        ).json()
        [out] = [p for p in body["peers"] if p["url"] == peer.url]
        assert out["timezone"] == "UTC"
        assert out["timezone_ok"] is False
    finally:
        sync._peers_cache.pop(peer.url, None)
        db.delete(peer)
        db.commit()


def test_internal_node_info_requires_the_token(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    url = f"{settings.API_V1_STR}/sync/internal/node-info"
    monkeypatch.setattr(settings, "INTERNAL_SYNC_TOKEN", "s3cret")
    monkeypatch.setenv("TZ", "Asia/Ho_Chi_Minh")
    assert client.get(url).status_code == 403
    assert client.get(url, headers={"X-Internal-Token": "nope"}).status_code == 403
    r = client.get(url, headers={"X-Internal-Token": "s3cret"})
    assert r.status_code == 200
    assert r.json()["timezone"] == "Asia/Ho_Chi_Minh"


def test_startup_warns_on_mismatch(
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    log_zone,  # type: ignore[no-untyped-def]
) -> None:
    log_zone("Asia/Ho_Chi_Minh")
    monkeypatch.setenv("TZ", "UTC")
    with caplog.at_level(logging.WARNING, logger="app.main"):
        _warn_on_timezone_mismatch(db)
    assert "log time zone" in caplog.text

    caplog.clear()
    monkeypatch.setenv("TZ", "Asia/Saigon")
    with caplog.at_level(logging.WARNING, logger="app.main"):
        _warn_on_timezone_mismatch(db)
    assert caplog.text == ""


def test_peer_check_fetches_zone_with_token() -> None:
    calls: list[tuple[str, dict[str, str]]] = []

    class Resp:
        def __init__(self, status: int, body: object) -> None:
            self.status_code = status
            self._body = body

        def json(self) -> object:
            return self._body

    class FakeClient:
        def __init__(self, *a: object, **k: object) -> None: ...
        def __enter__(self) -> "FakeClient":
            return self

        def __exit__(self, *a: object) -> None: ...
        def get(self, url: str, headers: dict[str, str] | None = None) -> Resp:
            calls.append((url, headers or {}))
            if url.endswith("/health-check/"):
                return Resp(200, True)
            return Resp(200, {"timezone": "Asia/Ho_Chi_Minh"})

    url = "http://peer-zone.invalid:8000"
    sync._peers_cache.pop(url, None)
    with (
        patch.object(sync.httpx, "Client", FakeClient),
        patch.object(settings, "INTERNAL_SYNC_TOKEN", "tok"),
    ):
        assert sync._check_peers_available([url]) == {url: True}
    try:
        assert sync._peers_cache[url]["timezone"] == "Asia/Ho_Chi_Minh"
        assert calls[1] == (
            f"{url}/api/v1/sync/internal/node-info",
            {"X-Internal-Token": "tok"},
        )
    finally:
        sync._peers_cache.pop(url, None)
