"""API-key authentication for the mounted MCP app.

Two layers are needed because MCP tools are not FastAPI routes and therefore
cannot use `Depends`:

1. An ASGI middleware wrapping the mount, so unauthenticated traffic is rejected
   with a real HTTP 401 before any MCP protocol handling happens.
2. A helper that reads the resolved principal back out inside a tool. The
   streamable-HTTP transport threads the Starlette ``Request`` through per
   JSON-RPC message, and that request carries the very same ``scope`` dict the
   middleware mutated.
"""

import logging
from typing import Any

from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from app.crud.api_keys import ApiKeyPrincipal, resolve_api_key

log = logging.getLogger(__name__)

SCOPE_KEY = "tacacs_mcp_principal"

_WWW_AUTHENTICATE = {"WWW-Authenticate": 'Bearer realm="tacacs-ng-mcp"'}


class McpAuthError(Exception):
    """Raised inside a tool when the caller lacks identity or a required scope."""


def _client_ip(scope: Scope) -> str | None:
    headers = Headers(scope=scope)
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = headers.get("x-real-ip")
    if real_ip:
        return real_ip
    client = scope.get("client")
    return client[0] if client else None


async def _unauthorized(
    scope: Scope, receive: Receive, send: Send, detail: str
) -> None:
    response = JSONResponse(
        {"error": "unauthorized", "detail": detail},
        status_code=401,
        headers=_WWW_AUTHENTICATE,
    )
    await response(scope, receive, send)


class ApiKeyAuthMiddleware:
    """Reject requests without a usable API key, and attach the principal."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        header = Headers(scope=scope).get("authorization", "")
        raw = header[7:].strip() if header[:7].lower() == "bearer " else ""
        if not raw:
            await _unauthorized(scope, receive, send, "Missing bearer API key.")
            return

        principal = await run_in_threadpool(resolve_api_key, raw, _client_ip(scope))
        if principal is None:
            await _unauthorized(
                scope, receive, send, "Invalid, expired or revoked API key."
            )
            return

        scope[SCOPE_KEY] = principal
        await self.app(scope, receive, send)


def principal_from(ctx: Any) -> ApiKeyPrincipal:
    """Read the authenticated principal out of the MCP request context."""
    request = getattr(ctx.request_context, "request", None)
    principal = getattr(request, "scope", {}).get(SCOPE_KEY) if request else None
    if not isinstance(principal, ApiKeyPrincipal):
        raise McpAuthError("Unauthenticated: no API key principal on this request.")
    return principal


def require_scope(principal: ApiKeyPrincipal, scope: str) -> None:
    if not principal.has(scope):
        raise McpAuthError(f"API key is missing the required scope '{scope}'.")


def require_superuser(principal: ApiKeyPrincipal, action: str) -> None:
    if not principal.is_superuser:
        raise McpAuthError(f"{action} requires an API key bound to a superuser.")
