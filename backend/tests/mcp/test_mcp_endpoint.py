"""End-to-end tests against the mounted MCP app.

Stateless mode puts the ServerSession straight into the Initialized state, so a
single synchronous JSON-RPC POST is a complete interaction — no `initialize`
handshake and no async test client are needed.
"""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.crud import api_keys
from app.models import ApiKeyCreate, User
from tests.utils.user import create_random_user

pytestmark = pytest.mark.skipif(
    not settings.MCP_ENABLED,
    reason="MCP server is disabled (set MCP_ENABLED=true to run these tests)",
)

MCP_URL = "/mcp/"

EXPECTED_TOOLS = {
    "describe_entity",
    "diff_generated_vs_active",
    "generate_config_preview",
    "generate_config_section",
    "get_tacacs_settings",
    "list_entities",
    "list_saved_configs",
    "read_saved_config",
    "validate_config_text",
    "validate_generated_config",
    "validate_saved_config",
    "whoami",
}


def _rpc(
    client: TestClient, headers: dict[str, str], method: str, params: dict[str, Any]
) -> dict[str, Any]:
    r = client.post(
        MCP_URL,
        headers=headers,
        json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
    )
    assert r.status_code == 200, r.text
    return r.json()["result"]


def _call(
    client: TestClient, headers: dict[str, str], name: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    return _rpc(client, headers, "tools/call", {"name": name, "arguments": arguments})


def _error_text(result: dict[str, Any]) -> str:
    assert result.get("isError") is True, result
    return result["content"][0]["text"]


def _headers_for(db: Session, user: User, scopes: str) -> dict[str, str]:
    _, plaintext = api_keys.create_api_key(
        session=db,
        api_key_create=ApiKeyCreate(name="pytest-scoped", scopes=scopes),
        owner_id=user.id,
        created_by_id=user.id,
    )
    return {
        "Authorization": f"Bearer {plaintext}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


# --- authentication ---


def test_missing_authorization_is_rejected(client: TestClient) -> None:
    r = client.post(MCP_URL, headers={"Content-Type": "application/json"}, json={})
    assert r.status_code == 401
    assert r.headers.get("www-authenticate", "").startswith("Bearer")


def test_garbage_bearer_is_rejected(client: TestClient) -> None:
    r = client.post(
        MCP_URL,
        headers={
            "Authorization": "Bearer not-a-key",
            "Content-Type": "application/json",
        },
        json={},
    )
    assert r.status_code == 401


def test_revoked_key_is_rejected(
    client: TestClient, db: Session, mcp_api_key: str
) -> None:
    principal = api_keys.resolve_api_key(mcp_api_key)
    assert principal is not None
    row = api_keys.get_api_key_by_id(session=db, id=principal.api_key_id)
    assert row is not None
    api_keys.revoke_api_key(session=db, db_api_key=row)

    r = client.post(
        MCP_URL,
        headers={
            "Authorization": f"Bearer {mcp_api_key}",
            "Content-Type": "application/json",
        },
        json={},
    )
    assert r.status_code == 401


# --- surface ---


def test_tools_list_is_exactly_the_expected_surface(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    result = _rpc(client, mcp_headers, "tools/list", {})
    assert {t["name"] for t in result["tools"]} == EXPECTED_TOOLS


def test_context_parameter_is_not_exposed_to_the_model(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    result = _rpc(client, mcp_headers, "tools/list", {})
    for tool in result["tools"]:
        assert "ctx" not in tool["inputSchema"].get("properties", {})


def test_resources_and_prompt_are_registered(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    resources = _rpc(client, mcp_headers, "resources/list", {})
    assert {r["uri"] for r in resources["resources"]} == {
        "tacacs://syntax/reference",
        "tacacs://schema/entities",
        "tacacs://config/active",
    }

    prompts = _rpc(client, mcp_headers, "prompts/list", {})
    assert {p["name"] for p in prompts["prompts"]} == {"author_tacacs_config"}


def test_whoami_reports_the_bound_identity(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    result = _call(client, mcp_headers, "whoami", {})
    payload = result["structuredContent"]
    assert payload["user_email"] == settings.FIRST_SUPERUSER
    assert payload["is_superuser"] is True
    assert payload["mcp_read_only"] is True
    assert "mcp:read" in payload["scopes"]


# --- behaviour ---


def test_generate_config_preview_redacts_secrets(
    client: TestClient, db: Session, mcp_headers: dict[str, str]
) -> None:
    from app.mcp_server.redact import collect_secrets

    result = _call(client, mcp_headers, "generate_config_preview", {})
    payload = result["structuredContent"]
    assert payload["redacted"] is True
    assert payload["line_count"] > 0
    for secret in collect_secrets(session=db):
        if len(secret) >= 4:
            assert secret not in payload["config"]


def test_list_entities_masks_host_secret_key(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    result = _call(client, mcp_headers, "list_entities", {"entity_type": "host"})
    payload = result["structuredContent"]
    for item in payload["items"]:
        assert item.get("secret_key") in (None, "", "***REDACTED***")


def test_describe_unknown_entity_is_an_error(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    result = _call(
        client,
        mcp_headers,
        "describe_entity",
        {"entity_type": "host", "name": "no-such-host-xyz"},
    )
    assert "no-such-host-xyz" in _error_text(result)


def test_list_saved_configs_reports_active(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    result = _call(client, mcp_headers, "list_saved_configs", {})
    payload = result["structuredContent"]
    assert "active_filename" in payload
    assert payload["count"] == len(payload["items"])


# --- authorization ---


def test_missing_scope_is_refused_by_name(client: TestClient, db: Session) -> None:
    user = create_random_user(db=db)
    user.is_superuser = True
    db.add(user)
    db.commit()
    headers = _headers_for(db, user, "mcp:read")

    result = _call(client, headers, "validate_config_text", {"text": "group = g1\n"})
    assert "mcp:validate" in _error_text(result)


def test_unredacted_output_requires_superuser(client: TestClient, db: Session) -> None:
    user = create_random_user(db=db)  # not a superuser
    headers = _headers_for(db, user, "mcp:generate,mcp:secrets")

    result = _call(
        client, headers, "generate_config_preview", {"redact_secrets": False}
    )
    assert "superuser" in _error_text(result).lower()


def test_unredacted_output_requires_the_secrets_scope(
    client: TestClient, db: Session
) -> None:
    user = create_random_user(db=db)
    user.is_superuser = True
    db.add(user)
    db.commit()
    headers = _headers_for(db, user, "mcp:generate")

    result = _call(
        client, headers, "generate_config_preview", {"redact_secrets": False}
    )
    assert "mcp:secrets" in _error_text(result)


def test_validate_config_text_refuses_include_directives(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    result = _call(
        client, mcp_headers, "validate_config_text", {"text": "#include /etc/passwd\n"}
    )
    assert "include" in _error_text(result)


def test_validate_config_text_rejects_oversized_input(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    oversized = "#\n" * (settings.MCP_MAX_CONFIG_TEXT_BYTES // 2 + 10)
    result = _call(client, mcp_headers, "validate_config_text", {"text": oversized})
    assert "limit" in _error_text(result)


def test_pagination_bounds_are_declared_in_the_schema(
    client: TestClient, mcp_headers: dict[str, str]
) -> None:
    result = _rpc(client, mcp_headers, "tools/list", {})
    tool = next(t for t in result["tools"] if t["name"] == "list_entities")
    props = tool["inputSchema"]["properties"]
    assert props["limit"]["minimum"] == 1
    assert props["limit"]["maximum"] == 500
    assert props["offset"]["minimum"] == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {"entity_type": "host", "limit": -1},
        {"entity_type": "host", "limit": 0},
        {"entity_type": "host", "limit": 10**9},
        {"entity_type": "host", "offset": -1},
    ],
)
def test_out_of_range_pagination_never_reaches_the_database(
    client: TestClient, mcp_headers: dict[str, str], arguments: dict[str, Any]
) -> None:
    """Rejected by pydantic, so no raw SQL error is handed back to the client."""
    text = _error_text(_call(client, mcp_headers, "list_entities", arguments))
    assert "validation error" in text
    assert "[SQL:" not in text
    assert "psycopg" not in text
