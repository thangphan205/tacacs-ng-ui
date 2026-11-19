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
        ("203.0.113.5, 10.0.0.1, 172.18.0.2, 192.168.1.1", "203.0.113.5"),
        # Internal client: every entry trusted, leftmost wins.
        ("10.1.2.3, 172.18.0.2", "10.1.2.3"),
        ("2001:db8::7, ::1", "2001:db8::7"),
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
