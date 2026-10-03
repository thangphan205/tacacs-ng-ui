from collections.abc import Generator
from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.crud import auth_providers as auth_providers_crud
from app.models import AuthProviderConfig


@pytest.fixture(autouse=True)
def clean_providers(db: Session) -> Generator[None, None, None]:
    """The table is a singleton per provider — leave it as we found it."""
    yield
    db.execute(delete(AuthProviderConfig))
    db.commit()


def _authorize_params(client: TestClient) -> dict[str, list[str]]:
    r = client.get(f"{settings.API_V1_STR}/oauth/google/authorize")
    assert r.status_code == 200, r.text
    return parse_qs(urlparse(r.json()["url"]).query)


def test_google_authorize_unconfigured_returns_503(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/oauth/google/authorize")
    assert r.status_code == 503
    assert r.json()["detail"] == "Google OAuth is not configured"


def test_google_authorize_uses_db_config(client: TestClient, db: Session) -> None:
    """The admin UI writes to the DB, so the flow must read it back.

    Regression test: the routes used to read settings.GOOGLE_* only, so a
    provider configured entirely through the UI answered 503 while the login
    page — which does read the DB — still offered the button.
    """
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="google",
        enabled=True,
        config={
            "client_id": "db-client-id.apps.googleusercontent.com",
            "redirect_uri": "https://tacacs.example.com/api/v1/oauth/google/callback",
        },
        secret="db-client-secret",
    )

    params = _authorize_params(client)
    assert params["client_id"] == ["db-client-id.apps.googleusercontent.com"]
    assert params["redirect_uri"] == [
        "https://tacacs.example.com/api/v1/oauth/google/callback"
    ]


def test_google_authorize_disabled_provider_returns_503(
    client: TestClient, db: Session
) -> None:
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="google",
        enabled=False,
        config={"client_id": "db-client-id"},
        secret="db-client-secret",
    )

    r = client.get(f"{settings.API_V1_STR}/oauth/google/authorize")
    assert r.status_code == 503
    assert r.json()["detail"] == "Google sign-in is disabled"


def test_google_authorize_falls_back_to_env_per_field(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A half-filled form must not blank out what the environment supplies."""
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "env-client-id", raising=False)
    monkeypatch.setattr(
        settings,
        "GOOGLE_REDIRECT_URI",
        "https://env.example.com/api/v1/oauth/google/callback",
        raising=False,
    )
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="google",
        enabled=True,
        config={"client_id": "db-client-id"},  # no redirect_uri
    )

    params = _authorize_params(client)
    assert params["client_id"] == ["db-client-id"]
    assert params["redirect_uri"] == [
        "https://env.example.com/api/v1/oauth/google/callback"
    ]


def test_keycloak_authorize_builds_urls_from_db_config(
    client: TestClient, db: Session
) -> None:
    """server_url and realm are stored separately and must compose the endpoint."""
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="keycloak",
        enabled=True,
        config={
            "server_url": "https://kc.example.com/",  # trailing slash on purpose
            "realm": "tacacs",
            "client_id": "kc-client",
            "redirect_uri": "https://tacacs.example.com/api/v1/oauth/keycloak/callback",
        },
        secret="kc-secret",
    )

    r = client.get(f"{settings.API_V1_STR}/oauth/keycloak/authorize")
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith(
        "https://kc.example.com/realms/tacacs/protocol/openid-connect/auth?"
    )


def test_provider_secret_is_never_exposed_by_admin_api(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="google",
        enabled=True,
        config={"client_id": "db-client-id"},
        secret="top-secret-value",
    )

    r = client.get(
        f"{settings.API_V1_STR}/admin/auth-providers/google",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["secret_is_set"] is True
    assert "top-secret-value" not in r.text
    assert "secret" not in body or body.get("secret") is None


def _fake_id_token(claims: dict[str, object]) -> str:
    import base64
    import json

    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip("=")
    return f"e30.{body}.sig"


def _configure_microsoft(db: Session, tenant: str) -> None:
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="microsoft",
        enabled=True,
        config={
            "client_id": "ms-client",
            "tenant": tenant,
            "redirect_uri": "https://tacacs.example.com/api/v1/oauth/microsoft/callback",
        },
        secret="ms-secret",
    )


def test_microsoft_authorize_unconfigured_returns_503(client: TestClient) -> None:
    r = client.get(f"{settings.API_V1_STR}/oauth/microsoft/authorize")
    assert r.status_code == 503
    assert r.json()["detail"] == "Microsoft is not configured"


def test_microsoft_authorize_uses_tenant(client: TestClient, db: Session) -> None:
    _configure_microsoft(db, "contoso.onmicrosoft.com")
    r = client.get(f"{settings.API_V1_STR}/oauth/microsoft/authorize")
    assert r.status_code == 200, r.text
    assert r.json()["url"].startswith(
        "https://login.microsoftonline.com/contoso.onmicrosoft.com/oauth2/v2.0/authorize?"
    )


def _microsoft_callback(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, claims: dict[str, object]
) -> Any:
    import httpx

    from app.api.routes import oauth

    def fake_post(self: httpx.Client, url: str, **kwargs: Any) -> httpx.Response:
        return httpx.Response(
            200,
            json={"id_token": _fake_id_token(claims)},
            request=httpx.Request("POST", url),
        )

    monkeypatch.setattr(httpx.Client, "post", fake_post)
    return client.get(
        f"{settings.API_V1_STR}/oauth/microsoft/callback",
        params={"code": "abc", "state": oauth._make_state()},
        follow_redirects=False,
    )


def test_microsoft_callback_creates_user(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_microsoft(db, "contoso.onmicrosoft.com")
    r = _microsoft_callback(
        client,
        monkeypatch,
        {
            "aud": "ms-client",
            "sub": "sub-1",
            "preferred_username": "New.User@Contoso.com",
            "name": "New User",
        },
    )
    assert r.status_code == 307, r.text
    assert "/oauth-callback?token=" in r.headers["location"]


def test_microsoft_multitenant_refuses_email_link(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_microsoft(db, "organizations")
    r = _microsoft_callback(
        client,
        monkeypatch,
        {
            "aud": "ms-client",
            "sub": "sub-2",
            "tid": "11111111-1111-1111-1111-111111111111",
            "email": settings.FIRST_SUPERUSER,
        },
    )
    assert r.status_code == 403, r.text


def test_microsoft_callback_rejects_wrong_audience(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _configure_microsoft(db, "contoso.onmicrosoft.com")
    r = _microsoft_callback(
        client, monkeypatch, {"aud": "other", "sub": "s", "email": "a@b.com"}
    )
    assert r.status_code == 400


def test_microsoft_redirect_uri_defaults_from_frontend_host(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "FRONTEND_HOST", "https://tacacs.example.com/")
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="microsoft",
        enabled=True,
        config={"client_id": "ms-client"},
        secret="ms-secret",
    )
    r = client.get(f"{settings.API_V1_STR}/oauth/microsoft/authorize")
    assert r.status_code == 200, r.text
    params = parse_qs(urlparse(r.json()["url"]).query)
    assert params["redirect_uri"] == [
        "https://tacacs.example.com/api/v1/oauth/microsoft/callback"
    ]


@pytest.mark.parametrize("provider", ["google", "keycloak"])
def test_google_keycloak_redirect_uri_defaults_from_frontend_host(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
) -> None:
    monkeypatch.setattr(settings, "FRONTEND_HOST", "https://tacacs.example.com")
    monkeypatch.setattr(settings, f"{provider.upper()}_REDIRECT_URI", "")
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider=provider,
        enabled=True,
        config={
            "client_id": "cid",
            "server_url": "https://kc.example.com",
            "realm": "r",
        },
        secret="s",
    )
    r = client.get(f"{settings.API_V1_STR}/oauth/{provider}/authorize")
    assert r.status_code == 200, r.text
    params = parse_qs(urlparse(r.json()["url"]).query)
    assert params["redirect_uri"] == [
        f"https://tacacs.example.com/api/v1/oauth/{provider}/callback"
    ]
