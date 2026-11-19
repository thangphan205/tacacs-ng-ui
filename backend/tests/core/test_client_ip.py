"""Client address behind reverse proxies: a forged X-Forwarded-For is ignored."""

import pytest
from starlette.requests import Request

from app.api.deps import _forwarded_client_ip, get_client_ip
from app.core.config import settings


def _request(headers: dict[str, str], peer: str = "172.18.0.3") -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": (peer, 1234),
            "raw_client": (peer, 1234),
        }
    )


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        # Traefik -> nginx -> backend: the forged leftmost entry is ignored.
        ("6.6.6.6, 203.0.113.5, 172.18.0.2", "203.0.113.5"),
        # One proxy only (nginx alone): the real address is the last entry.
        ("6.6.6.6, 203.0.113.5", "203.0.113.5"),
        ("203.0.113.5", "203.0.113.5"),
        # Any number of trusted hops after the client.
        ("203.0.113.5, 172.20.0.1, 172.18.0.2, 127.0.0.1", "203.0.113.5"),
        # Office LAN addresses are clients, never skipped as proxies.
        ("8.8.8.8, 10.1.1.5, 172.18.0.2", "10.1.1.5"),
        ("8.8.8.8, 192.168.1.9", "192.168.1.9"),
        # A dual-stack proxy hop is still a proxy.
        ("203.0.113.5, ::ffff:172.18.0.2", "203.0.113.5"),
        # LAN client: 10.x is not a proxy range by default.
        ("10.1.2.3, 172.18.0.2", "10.1.2.3"),
        ("2001:db8::7, ::1", "2001:db8::7"),
        # Every entry trusted: the rightmost, which our proxy appended -- never
        # the leftmost, which the caller wrote.
        ("172.20.9.9, 172.21.0.5, 172.18.0.2", "172.18.0.2"),
        ("172.20.9.9", "172.20.9.9"),
        # Ports and brackets some proxies add are tolerated.
        ("6.6.6.6, 203.0.113.5:51234, 172.18.0.2", "203.0.113.5"),
        ("6.6.6.6, [2001:db8::7]:443, 172.18.0.2", "2001:db8::7"),
        ("6.6.6.6, [2001:db8::7], 172.18.0.2", "2001:db8::7"),
        # A non-address entry is skipped, not trusted.
        ("203.0.113.9, junk, 172.18.0.2", "203.0.113.9"),
        ("junk", None),
        ("", None),
    ],
)
def test_forwarded_client_ip(header: str, expected: str | None) -> None:
    assert _forwarded_client_ip(header) == expected


def test_a_cdn_range_can_be_added_to_the_trusted_proxies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    header = "6.6.6.6, 198.51.100.20, 104.16.0.1, 172.18.0.2"
    # Unknown edge address is taken for the client...
    assert _forwarded_client_ip(header) == "104.16.0.1"
    # ...until the CDN's range is trusted.
    monkeypatch.setattr(
        settings, "TRUSTED_PROXIES", settings.TRUSTED_PROXIES + ",104.16.0.0/13"
    )
    assert _forwarded_client_ip(header) == "198.51.100.20"


def test_get_client_ip_falls_back_without_a_usable_header() -> None:
    assert get_client_ip(_request({})) == "172.18.0.3"
    assert get_client_ip(_request({"X-Real-IP": "203.0.113.8"})) == "203.0.113.8"
    # Present but unusable: the caller-writable X-Real-IP is never consulted.
    unusable = _request({"X-Forwarded-For": "junk", "X-Real-IP": "6.6.6.6"})
    assert get_client_ip(unusable) == "172.18.0.3"


def test_x_forwarded_for_is_ignored_unless_the_peer_is_a_trusted_proxy() -> None:
    forged = {"X-Forwarded-For": "8.8.8.8", "X-Real-IP": "9.9.9.9"}
    # A LAN host, or anyone hitting the backend port: it is the client.
    assert get_client_ip(_request(forged, peer="10.1.1.5")) == "10.1.1.5"
    assert get_client_ip(_request(forged, peer="203.0.113.50")) == "203.0.113.50"
    # Behind our proxy the same header is believed.
    assert get_client_ip(_request(forged, peer="172.18.0.3")) == "8.8.8.8"
    # Dual-stack socket for the proxy itself.
    assert get_client_ip(_request(forged, peer="::ffff:172.18.0.3")) == "8.8.8.8"


def test_the_socket_peer_survives_uvicorn_style_rewriting() -> None:
    """ProxyHeadersMiddleware overwrites scope["client"]; raw_client is kept."""
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"8.8.8.8")],
            "client": ("8.8.8.8", 0),  # rewritten from the forged header
            "raw_client": ("10.1.1.5", 1234),
        }
    )
    assert get_client_ip(request) == "10.1.1.5"


def test_untrusted_proxy_forwarding_is_logged_once_per_peer(
    caplog: pytest.LogCaptureFixture,
) -> None:
    from app.api import deps

    deps._warned_peers.clear()
    request = _request({"X-Forwarded-For": "203.0.113.5"}, peer="192.168.176.4")
    with caplog.at_level("WARNING", logger=deps.logger.name):
        assert get_client_ip(request) == "192.168.176.4"
        assert get_client_ip(request) == "192.168.176.4"
    warnings = [r for r in caplog.records if "TRUSTED_PROXIES" in r.getMessage()]
    assert len(warnings) == 1
    assert "192.168.176.4" in warnings[0].getMessage()
    # A trusted peer never triggers it.
    caplog.clear()
    with caplog.at_level("WARNING", logger=deps.logger.name):
        get_client_ip(_request({"X-Forwarded-For": "203.0.113.5"}))
    assert not [r for r in caplog.records if "TRUSTED_PROXIES" in r.getMessage()]
