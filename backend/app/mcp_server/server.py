import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core.config import settings

log = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "Inspect TACACS+ (tac_plus-ng) entities from the tacacs-ng-ui database and "
    "generate or validate tac_plus-ng configuration text. This server is "
    "read-only: it never modifies the database, never writes the live config "
    "file, and never reloads the daemon. Read the tacacs://syntax/reference "
    "resource before authoring config text."
)

# The live server for the current lifespan. Rebuilt on every lifespan run
# because StreamableHTTPSessionManager.run() may only be called once per
# instance, and lifespan runs more than once under --reload and in tests.
_active: FastMCP | None = None


def build_mcp() -> FastMCP:
    """Construct a fully-populated FastMCP instance."""
    server = FastMCP(
        name="tacacs-ng",
        instructions=_INSTRUCTIONS,
        # Required: supervisord runs `uvicorn --workers 4`, four separate
        # processes with no shared memory. In stateful mode a client that
        # initializes on one worker would be round-robined to another and get
        # "session not found". Flipping this off means also adding a dedicated
        # single-process supervisord program or sticky sessions.
        stateless_http=True,
        # No SSE streams: keeps traefik/uvicorn connection accounting simple.
        json_response=True,
        # The mount path already carries the "/mcp" segment.
        streamable_http_path="/",
        # FastMCP auto-enables DNS-rebinding protection when `host` is a
        # loopback name, and `host` defaults to 127.0.0.1. Behind traefik the
        # Host header is api.<domain>, which that guard would reject.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )

    from app.mcp_server import tools

    tools.register(server)
    return server


class MCPMountApp:
    """ASGI shim resolving the live session manager per request.

    Kept separate from the FastMCP instance so the app object can be mounted
    once at import time while the session manager is rebuilt per lifespan.
    """

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if _active is None:
            response = JSONResponse(
                {"error": "unavailable", "detail": "MCP server is not running."},
                status_code=503,
            )
            await response(scope, receive, send)
            return
        await _active.session_manager.handle_request(scope, receive, send)


@asynccontextmanager
async def mcp_lifespan() -> AsyncIterator[None]:
    global _active
    server = build_mcp()
    # Side effect: lazily constructs the session manager, which the
    # `session_manager` property refuses to hand out before this call.
    server.streamable_http_app()
    async with server.session_manager.run():
        _active = server
        log.info("MCP server mounted at %s", settings.MCP_PATH)
        try:
            yield
        finally:
            _active = None
