"""GET /hosts ordering and search, which the Parent Host picker relies on (#360)."""

import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.models import Host

URL = f"{settings.API_V1_STR}/hosts/"


@pytest.fixture
def tag(db: Session) -> Generator[str, None, None]:
    """Hosts named <tag>-*, inserted out of name order; removed afterwards."""
    t = f"hl{uuid.uuid4().hex[:8]}"
    for name, ip in [
        ("charlie", "10.9.0.3"),
        ("alpha", "10.9.0.1"),
        ("bravo", "10.9.0.2"),
    ]:
        db.add(Host(name=f"{t}-{name}", ipv4_address=ip, secret_key="k"))
    db.commit()
    yield t
    db.exec(delete(Host).where(Host.name.like(f"{t}-%")))  # type: ignore[call-overload]
    db.commit()


def _names(client: TestClient, headers: dict[str, str], **params: str) -> list[str]:
    r = client.get(URL, headers=headers, params=params)
    assert r.status_code == 200
    return [h["name"] for h in r.json()["data"]]


def test_hosts_are_sorted_by_name_by_default(
    client: TestClient, superuser_token_headers: dict[str, str], tag: str
) -> None:
    assert _names(client, superuser_token_headers, search=tag) == [
        f"{tag}-alpha",
        f"{tag}-bravo",
        f"{tag}-charlie",
    ]


def test_hosts_sort_order_desc(
    client: TestClient, superuser_token_headers: dict[str, str], tag: str
) -> None:
    assert _names(client, superuser_token_headers, search=tag, sort_order="desc") == [
        f"{tag}-charlie",
        f"{tag}-bravo",
        f"{tag}-alpha",
    ]


def test_hosts_unknown_sort_by_falls_back_to_name(
    client: TestClient, superuser_token_headers: dict[str, str], tag: str
) -> None:
    names = _names(client, superuser_token_headers, search=tag, sort_by="secret_key")
    assert names == sorted(names)


def test_hosts_search_matches_ip(
    client: TestClient, superuser_token_headers: dict[str, str], tag: str
) -> None:
    assert f"{tag}-bravo" in _names(client, superuser_token_headers, search="10.9.0.2")
