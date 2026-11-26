"""Unit tests for session-bound, random, single-use OAuth state (no DB required)."""

import time
from urllib.parse import parse_qs, urlparse

import pytest
from fastapi.testclient import TestClient

from app.api.routes import oauth
from app.main import app


def test_state_is_random_and_distinct_across_calls_and_providers() -> None:
    s1 = oauth._make_state("google")
    s2 = oauth._make_state("google")
    s3 = oauth._make_state("microsoft")
    assert s1 != s2
    assert s1 != s3
    assert s2 != s3


def test_state_requires_matching_session_cookie() -> None:
    state = oauth._make_state("google")
    # Attacker-obtained, cookie-less state must be rejected.
    assert not oauth._verify_state(state, expected_provider="google", cookie_state=None)
    assert not oauth._verify_state(state, expected_provider="google", cookie_state="")
    # Mismatched cookie must be rejected.
    other = oauth._make_state("google")
    assert not oauth._verify_state(
        state, expected_provider="google", cookie_state=other
    )


def test_state_is_provider_bound() -> None:
    state = oauth._make_state("google")
    assert not oauth._verify_state(
        state, expected_provider="microsoft", cookie_state=state
    )
    assert not oauth._verify_state(
        state, expected_provider="keycloak", cookie_state=state
    )


def test_state_is_single_use() -> None:
    state = oauth._make_state("google")
    assert oauth._verify_state(state, expected_provider="google", cookie_state=state)
    # Replaying the exact same state + cookie must fail.
    assert not oauth._verify_state(
        state, expected_provider="google", cookie_state=state
    )


def test_expired_or_tampered_state_is_rejected() -> None:
    state = oauth._make_state("google")
    provider, _, nonce, sig = state.split(".")
    old_ts = str(int(time.time()) - 700)
    expired = f"{provider}.{old_ts}.{nonce}.{sig}"
    assert not oauth._verify_state(
        expired, expected_provider="google", cookie_state=expired
    )
    tampered = f"{provider}.{int(time.time())}.{nonce}.{'0' * 64}"
    assert not oauth._verify_state(
        tampered, expected_provider="google", cookie_state=tampered
    )


def test_callback_rejects_cookieless_state_before_provider_exchange() -> None:
    """Regression test for login-CSRF: attacker-minted state without cookie -> 400."""
    client = TestClient(app)
    state = oauth._make_state("google")
    r = client.get(
        "/api/v1/oauth/google/callback",
        params={"code": "bogus", "state": state},
    )
    assert r.status_code == 400
    assert r.json()["detail"] == "Invalid OAuth state"


def test_authorize_sets_httponly_samesite_cookie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Authorize endpoint must bind the minted state to an HttpOnly SameSite=Lax cookie."""
    monkeypatch.setattr(
        oauth,
        "_google_creds",
        lambda _session: oauth._Creds(
            client_id="cid",
            client_secret="csec",
            redirect_uri="https://tacacs.example.com/api/v1/oauth/google/callback",
            auth_url=oauth.GOOGLE_AUTH_URL,
            token_url=oauth.GOOGLE_TOKEN_URL,
            userinfo_url=oauth.GOOGLE_USERINFO_URL,
        ),
    )
    from app.api.deps import get_db

    app.dependency_overrides[get_db] = lambda: iter([None])
    try:
        client = TestClient(app)
        r = client.get("/api/v1/oauth/google/authorize")
        assert r.status_code == 200, r.text
        set_cookie = r.headers.get("set-cookie", "")
        assert "oauth_state=" in set_cookie
        assert "HttpOnly" in set_cookie
        assert "samesite=lax" in set_cookie.lower()
        assert "Path=/api/v1/oauth" in set_cookie

        url_state = parse_qs(urlparse(r.json()["url"]).query)["state"][0]
        assert r.cookies.get(oauth.OAUTH_STATE_COOKIE) == url_state
    finally:
        app.dependency_overrides.pop(get_db, None)
