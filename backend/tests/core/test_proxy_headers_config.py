"""uvicorn must not rewrite the socket peer before RawPeerMiddleware sees it.

The unit tests build requests by hand and never go through uvicorn, so only
this guards the launch command: with uvicorn's own proxy handling still on, it
overwrites ``scope["client"]`` from a caller-written X-Forwarded-For and
``get_client_ip`` would treat that forged address as the real peer.
"""

import re
from pathlib import Path

SUPERVISORD = Path(__file__).resolve().parents[2] / "supervisord.conf"


def _fastapi_command() -> str:
    match = re.search(r"^command=(uvicorn .+)$", SUPERVISORD.read_text(), re.M)
    assert match, "no uvicorn command in supervisord.conf"
    return match.group(1)


def test_uvicorn_runs_without_its_own_proxy_header_handling() -> None:
    command = _fastapi_command()
    assert "--no-proxy-headers" in command
    assert "--forwarded-allow-ips" not in command
