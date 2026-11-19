"""Keep the socket peer: uvicorn's proxy-header handling overwrites it.

``ProxyHeadersMiddleware`` replaces ``scope["client"]`` with the address taken
from X-Forwarded-For, so afterwards nothing can tell a caller that went through
our proxy from one that wrote the header itself. ``get_client_ip`` needs that
difference: it believes X-Forwarded-For only when the *socket* peer is one of
``TRUSTED_PROXIES``. This middleware must be the outermost one, so it runs
before the rewrite.
"""

from starlette.types import ASGIApp, Receive, Scope, Send


class RawPeerMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] in ("http", "websocket"):
            scope["raw_client"] = scope.get("client")
        await self.app(scope, receive, send)
