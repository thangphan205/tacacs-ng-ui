import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.types import Receive, Scope, Send

from app.core.config import settings

log = logging.getLogger(__name__)

_INSTRUCTIONS = (
    "Inspect TACACS+ (tac_plus-ng) entities from the tacacs-ng-ui database, "
    "render and validate tac_plus-ng configuration text, and — with an API key "
    "carrying the mcp:write scope — create, update and delete entities. "
    "Deployment is never yours to do: this server cannot save a config file, "
    "cannot activate one, and cannot reload the daemon. Entity changes sit in "
    "the database until a person opens the TACACS Configs page in the web UI "
    "and presses Generate, then Activate. Say so whenever you make a change. "
    "Read the tacacs://syntax/reference resource before authoring config text."
)

# The live server for the current lifespan. Rebuilt on every lifespan run
# because StreamableHTTPSessionManager.run() may only be called once per
# instance, and lifespan runs more than once under --reload and in tests.
_active: MCPServer | None = None


def build_mcp() -> MCPServer:
    """Construct a fully-populated MCPServer instance."""
    server = MCPServer(
        name="tacacs-ng",
        instructions=_INSTRUCTIONS,
    )

    from app.mcp_server import tools

    tools.register(server)
    return server


def build_http_app(server: MCPServer) -> Starlette:
    """Build the streamable-HTTP app, and with it the session manager.

    These four settings lived on the `FastMCP` constructor before mcp 2.0.
    `MCPServer` takes them here instead, and this call is also what lazily
    constructs the session manager, which the `session_manager` property
    refuses to hand out beforehand.
    """
    return server.streamable_http_app(
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
        # DNS-rebinding protection is auto-enabled when `host` is a loopback
        # name, and `host` defaults to 127.0.0.1. Behind traefik the Host
        # header is api.<domain>, which that guard would reject.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False
        ),
    )


class MCPMountApp:
    """ASGI shim resolving the live session manager per request.

    Kept separate from the MCPServer instance so the app object can be mounted
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
    build_http_app(server)
    async with server.session_manager.run():
        _active = server
        log.info("MCP server mounted at %s", settings.MCP_PATH)
        try:
            yield
        finally:
            _active = None
