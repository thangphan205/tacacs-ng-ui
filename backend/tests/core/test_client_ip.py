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


def test_every_x_forwarded_for_line_is_read_in_order() -> None:
    """A proxy that adds its own line (HAProxy ``option forwardfor``) instead
    of appending leaves the caller's forged line first; it must not win."""
    request = Request(
        {
            "type": "http",
            "headers": [
                (b"x-forwarded-for", b"6.6.6.6"),  # caller-written
                (b"x-forwarded-for", b"203.0.113.5"),  # added by our proxy
            ],
            "client": ("172.18.0.3", 1234),
            "raw_client": ("172.18.0.3", 1234),
        }
    )
    assert get_client_ip(request) == "203.0.113.5"


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


def test_a_scope_without_a_recorded_peer_never_trusts_the_rewritten_client() -> None:
    """Without RawPeerMiddleware, scope["client"] may hold the address a proxy
    middleware took from a caller-written X-Forwarded-For."""
    request = Request(
        {
            "type": "http",
            "headers": [(b"x-forwarded-for", b"8.8.8.8")],
            "client": ("172.18.0.3", 1234),  # would look like a trusted proxy
        }
    )
    assert get_client_ip(request) is None


# --- TRUSTED_PROXIES=auto ----------------------------------------------------

# /proc/net/route of a backend on two compose networks: `default`
# (172.18.0.0/16, default route via 172.18.0.1) and `traefik-public`
# (10.0.5.0/24, a Swarm-style range).
_ROUTE_TABLE = (
    "Iface\tDestination\tGateway \tFlags\tRefCnt\tUse\tMetric\tMask\t\tMTU\tWindow\tIRTT\n"
    "eth0\t00000000\t010012AC\t0003\t0\t0\t0\t00000000\t0\t0\t0\n"
    "eth0\t000012AC\t00000000\t0001\t0\t0\t0\t0000FFFF\t0\t0\t0\n"
    "eth1\t0005000A\t00000000\t0001\t0\t0\t0\t00FFFFFF\t0\t0\t0\n"
    "eth2\t0000A8C0\t00000000\t0000\t0\t0\t0\t00FFFFFF\t0\t0\t0\n"  # down
)


def test_attached_networks_reads_the_compose_networks() -> None:
    from app.api.deps import attached_networks

    networks, excluded = attached_networks(_ROUTE_TABLE, ["lo", "eth0", "eth1"])
    assert [str(n) for n in networks] == ["172.18.0.0/16", "10.0.5.0/24"]
    # Each network's gateway (the host) is not a proxy.
    assert {str(a) for a in excluded} == {"172.18.0.1", "10.0.5.1"}


def test_attached_networks_trusts_nothing_under_host_networking() -> None:
    from app.api.deps import attached_networks

    networks, excluded = attached_networks(
        _ROUTE_TABLE, ["lo", "eth0", "docker0", "br-1a2b3c"]
    )
    assert networks == () and excluded == frozenset()


@pytest.fixture
def _auto(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.api import deps

    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "auto")
    monkeypatch.setattr(deps, "_auto_cache", None)
    monkeypatch.setattr(
        deps,
        "_read_attached_networks",
        lambda: deps.attached_networks(_ROUTE_TABLE, ["lo", "eth0", "eth1"]),
    )


@pytest.mark.usefixtures("_auto")
@pytest.mark.parametrize(
    ("header", "expected"),
    [
        # Traefik on traefik-public, nginx on default: the client is found.
        ("6.6.6.6, 203.0.113.5, 10.0.5.7", "203.0.113.5"),
        # An office client in another 172.x range is a client, not a proxy
        # hop, so the address it wrote to its left is never believed.
        ("6.6.6.6, 172.20.5.5", "172.20.5.5"),
        ("6.6.6.6, 172.20.5.5, 10.0.5.7", "172.20.5.5"),
        # Nor is the host behind a network's gateway.
        ("6.6.6.6, 172.18.0.1", "172.18.0.1"),
        ("6.6.6.6, 10.0.5.1, 10.0.5.7", "10.0.5.1"),
        ("203.0.113.5, 127.0.0.1", "203.0.113.5"),
    ],
)
def test_auto_trusts_only_the_attached_networks(header: str, expected: str) -> None:
    assert _forwarded_client_ip(header) == expected


@pytest.mark.usefixtures("_auto")
def test_auto_believes_a_proxy_on_any_attached_network() -> None:
    """A 10.x or 192.168.x compose network works without configuration, so
    users do not all share the proxy's throttle bucket."""
    forged = {"X-Forwarded-For": "203.0.113.5"}
    assert get_client_ip(_request(forged, peer="10.0.5.7")) == "203.0.113.5"
    assert get_client_ip(_request(forged, peer="172.18.0.3")) == "203.0.113.5"
    # A caller outside them is itself, whatever it sends.
    assert get_client_ip(_request(forged, peer="172.20.5.5")) == "172.20.5.5"
    assert get_client_ip(_request(forged, peer="172.18.0.1")) == "172.18.0.1"


@pytest.mark.usefixtures("_auto")
def test_auto_can_be_combined_with_explicit_entries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    header = "6.6.6.6, 198.51.100.20, 104.16.0.1, 10.0.5.7"
    assert _forwarded_client_ip(header) == "104.16.0.1"
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "auto, 104.16.0.0/13")
    assert _forwarded_client_ip(header) == "198.51.100.20"
    # An explicit entry wins over auto's gateway exclusion.
    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "auto,172.18.0.1")
    assert (
        get_client_ip(_request({"X-Forwarded-For": "203.0.113.5"}, peer="172.18.0.1"))
        == "203.0.113.5"
    )


def test_auto_is_loopback_only_without_a_routing_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.api import deps

    monkeypatch.setattr(settings, "TRUSTED_PROXIES", "auto")
    monkeypatch.setattr(deps, "_auto_cache", None)
    monkeypatch.setattr(deps, "_ROUTE_FILE", "/nonexistent/route")
    forged = {"X-Forwarded-For": "203.0.113.5"}
    assert get_client_ip(_request(forged, peer="127.0.0.1")) == "203.0.113.5"
    assert get_client_ip(_request(forged, peer="172.18.0.3")) == "172.18.0.3"


def test_the_default_is_auto() -> None:
    from app.core.config import Settings

    assert Settings.model_fields["TRUSTED_PROXIES"].default == "auto"
