import json
import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.crud import notification_channels as crud_channels
from app.models import NotificationChannel, NotificationChannelCreate


def _make_channel(session: Session, **kwargs) -> NotificationChannel:
    defaults = dict(
        name=f"test-channel-{uuid.uuid4().hex[:8]}",
        channel_type="webhook",
        config_json=json.dumps({"webhook_url": "https://example.com/hook"}),
        enabled=True,
    )
    defaults.update(kwargs)
    ch_in = NotificationChannelCreate(**defaults)
    return crud_channels.create_notification_channel(session=session, channel_in=ch_in)


def _cleanup(session: Session, *channels: NotificationChannel) -> None:
    for ch in channels:
        session.refresh(ch)
        session.delete(ch)
    session.commit()


# ---------------------------------------------------------------------------
# CRUD — Notification Channels
# ---------------------------------------------------------------------------

class TestNotificationChannelCRUD:
    def test_create_and_read(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        ch = _make_channel(db, name="read-channel")
        try:
            resp = client.get(
                f"{settings.API_V1_STR}/notification_channels/{ch.id}",
                headers=superuser_token_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["id"] == str(ch.id)
            assert data["name"] == "read-channel"
            assert data["channel_type"] == "webhook"
        finally:
            _cleanup(db, ch)

    def test_list_includes_channel(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        ch = _make_channel(db)
        try:
            resp = client.get(
                f"{settings.API_V1_STR}/notification_channels/",
                headers=superuser_token_headers,
            )
            assert resp.status_code == 200
            ids = [c["id"] for c in resp.json()["data"]]
            assert str(ch.id) in ids
        finally:
            _cleanup(db, ch)

    def test_create_via_api(self, client: TestClient, superuser_token_headers: dict) -> None:
        payload = {
            "name": "api-webhook-channel",
            "channel_type": "webhook",
            "config_json": json.dumps({"webhook_url": "https://example.com/hook"}),
            "enabled": True,
        }
        resp = client.post(
            f"{settings.API_V1_STR}/notification_channels/",
            headers=superuser_token_headers,
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["channel_type"] == "webhook"
        assert data["enabled"] is True
        client.delete(f"{settings.API_V1_STR}/notification_channels/{data['id']}", headers=superuser_token_headers)

    def test_update_channel(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        ch = _make_channel(db)
        try:
            resp = client.patch(
                f"{settings.API_V1_STR}/notification_channels/{ch.id}",
                headers=superuser_token_headers,
                json={"enabled": False, "name": "updated-name"},
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["enabled"] is False
            assert data["name"] == "updated-name"
        finally:
            _cleanup(db, ch)

    def test_delete_channel(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        ch = _make_channel(db)
        resp = client.delete(
            f"{settings.API_V1_STR}/notification_channels/{ch.id}",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 200
        resp2 = client.get(
            f"{settings.API_V1_STR}/notification_channels/{ch.id}",
            headers=superuser_token_headers,
        )
        assert resp2.status_code == 404

    def test_read_not_found(self, client: TestClient, superuser_token_headers: dict) -> None:
        resp = client.get(
            f"{settings.API_V1_STR}/notification_channels/{uuid.uuid4()}",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 404

    def test_disabled_channel_excluded_from_enabled_only(self, db: Session) -> None:
        ch = _make_channel(db, enabled=False)
        try:
            channels, _ = crud_channels.get_notification_channels(session=db, enabled_only=True)
            ids = [c.id for c in channels]
            assert ch.id not in ids
        finally:
            _cleanup(db, ch)

    def test_enabled_channel_included_in_enabled_only(self, db: Session) -> None:
        ch = _make_channel(db, enabled=True)
        try:
            channels, _ = crud_channels.get_notification_channels(session=db, enabled_only=True)
            ids = [c.id for c in channels]
            assert ch.id in ids
        finally:
            _cleanup(db, ch)


# ---------------------------------------------------------------------------
# Dispatcher — unit tests with mocked HTTP
# ---------------------------------------------------------------------------

class TestNotificationDispatcher:
    def _channel(self, channel_type: str, config: dict) -> NotificationChannel:
        return NotificationChannel(
            name="test",
            channel_type=channel_type,
            config_json=json.dumps(config),
            enabled=True,
        )

    def test_dispatch_unknown_type(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("unknown_type", {})
        ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is False
        assert "Unknown channel_type" in (err or "")

    def test_dispatch_invalid_json(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = NotificationChannel(
            name="bad-json", channel_type="webhook", config_json="not-json", enabled=True
        )
        ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is False
        assert "Invalid config_json" in (err or "")

    def test_telegram_missing_config(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("telegram", {"bot_token": ""})
        ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is False
        assert "bot_token" in (err or "")

    def test_slack_missing_webhook_url(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("slack", {})
        ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is False
        assert "webhook_url" in (err or "")

    def test_discord_missing_webhook_url(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("discord", {})
        ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is False
        assert "webhook_url" in (err or "")

    def test_teams_missing_webhook_url(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("teams", {})
        ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is False
        assert "webhook_url" in (err or "")

    def test_webhook_missing_url(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("webhook", {})
        ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is False
        assert "webhook_url" in (err or "")

    def test_webhook_success(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("webhook", {"webhook_url": "https://example.com/hook"})
        mock_resp = MagicMock()
        mock_resp.is_success = True
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            ok, err = dispatch_notification(channel=ch, subject="Alert", body="Details here")
        assert ok is True
        assert err is None
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs.kwargs["json"]["subject"] == "Alert"
        assert call_kwargs.kwargs["json"]["body"] == "Details here"

    def test_webhook_with_bearer_token(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("webhook", {"webhook_url": "https://example.com/hook", "token": "secret123"})
        mock_resp = MagicMock()
        mock_resp.is_success = True
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is True
        headers = mock_post.call_args.kwargs["headers"]
        assert headers.get("Authorization") == "Bearer secret123"

    def test_webhook_http_error(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("webhook", {"webhook_url": "https://example.com/hook"})
        mock_resp = MagicMock()
        mock_resp.is_success = False
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        with patch("httpx.post", return_value=mock_resp):
            ok, err = dispatch_notification(channel=ch, subject="s", body="b")
        assert ok is False
        assert "500" in (err or "")

    def test_slack_success(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("slack", {"webhook_url": "https://hooks.slack.com/T000/B000/xxx"})
        mock_resp = MagicMock()
        mock_resp.is_success = True
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            ok, err = dispatch_notification(channel=ch, subject="Slack Alert", body="msg")
        assert ok is True
        payload = mock_post.call_args.kwargs["json"]
        assert "Slack Alert" in payload["text"]

    def test_telegram_success(self) -> None:
        from app.crud.notification_dispatcher import dispatch_notification
        ch = self._channel("telegram", {"bot_token": "fake_token", "chat_id": "-100123"})
        mock_resp = MagicMock()
        mock_resp.is_success = True
        with patch("httpx.post", return_value=mock_resp) as mock_post:
            ok, err = dispatch_notification(channel=ch, subject="TG Alert", body="msg")
        assert ok is True
        url = mock_post.call_args.args[0]
        assert "fake_token" in url
        payload = mock_post.call_args.kwargs["json"]
        assert payload["chat_id"] == "-100123"
        assert "TG Alert" in payload["text"]


# ---------------------------------------------------------------------------
# Test endpoint — POST /{id}/test
# ---------------------------------------------------------------------------

class TestChannelTestEndpoint:
    def test_test_endpoint_success(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        ch = _make_channel(db, channel_type="webhook", config_json=json.dumps({"webhook_url": "https://example.com/hook"}))
        try:
            mock_resp = MagicMock()
            mock_resp.is_success = True
            with patch("httpx.post", return_value=mock_resp):
                resp = client.post(
                    f"{settings.API_V1_STR}/notification_channels/{ch.id}/test",
                    headers=superuser_token_headers,
                )
            assert resp.status_code == 200
            assert "message" in resp.json()
        finally:
            _cleanup(db, ch)

    def test_test_endpoint_failure_returns_502(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        ch = _make_channel(db, channel_type="webhook", config_json=json.dumps({"webhook_url": "https://example.com/hook"}))
        try:
            mock_resp = MagicMock()
            mock_resp.is_success = False
            mock_resp.status_code = 503
            mock_resp.text = "Service Unavailable"
            with patch("httpx.post", return_value=mock_resp):
                resp = client.post(
                    f"{settings.API_V1_STR}/notification_channels/{ch.id}/test",
                    headers=superuser_token_headers,
                )
            assert resp.status_code == 502
            assert "Test failed" in resp.json()["detail"]
        finally:
            _cleanup(db, ch)

    def test_test_endpoint_not_found(self, client: TestClient, superuser_token_headers: dict) -> None:
        resp = client.post(
            f"{settings.API_V1_STR}/notification_channels/{uuid.uuid4()}/test",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 404
