"""RADIUS through the API: settings PUT is partial, hosts may be RADIUS-only."""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.models import TacacsNgSetting

API = settings.API_V1_STR
FIELDS = ("radius_enabled", "radius_auth_port", "radius_acct_port", "ipv4_port")


@pytest.fixture
def restore_settings(db: Session) -> Iterator[None]:
    row = db.exec(select(TacacsNgSetting)).first()
    assert row is not None
    saved = {k: getattr(row, k) for k in (*FIELDS, "radius_dictionary_extra")}
    yield
    db.expire_all()
    row = db.exec(select(TacacsNgSetting)).first()
    assert row is not None
    for k, v in saved.items():
        setattr(row, k, v)
    db.add(row)
    db.commit()


def _put(client: TestClient, headers: dict[str, str], body: dict) -> dict:
    r = client.put(f"{API}/tacacs_ng_settings/", headers=headers, json=body)
    return {"status": r.status_code, "body": r.json()}


@pytest.mark.usefixtures("restore_settings")
def test_radius_is_off_by_default_and_toggles(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{API}/tacacs_ng_settings/", headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.json()["radius_enabled"] is False
    assert (r.json()["radius_auth_port"], r.json()["radius_acct_port"]) == (1812, 1813)

    out = _put(client, superuser_token_headers, {"radius_enabled": True})
    assert out["status"] == 200 and out["body"]["radius_enabled"] is True
    out = _put(client, superuser_token_headers, {"radius_enabled": False})
    assert out["status"] == 200 and out["body"]["radius_enabled"] is False


@pytest.mark.usefixtures("restore_settings")
def test_ports_are_checked_against_the_stored_values(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    ok = _put(
        client,
        superuser_token_headers,
        {"radius_auth_port": 1912, "radius_acct_port": 1913},
    )
    assert ok["status"] == 200, ok
    # one port sent: collides with the stored acct port, not the default
    clash = _put(client, superuser_token_headers, {"radius_auth_port": 1913})
    assert clash["status"] == 400 and "must differ" in clash["body"]["detail"]
    # the default 1812 is free now that the stored ports moved
    assert (
        _put(client, superuser_token_headers, {"radius_auth_port": 1812})["status"]
        == 200
    )
    tacacs = _put(client, superuser_token_headers, {"ipv4_port": 1913})
    assert tacacs["status"] == 400 and "TACACS+" in tacacs["body"]["detail"]


@pytest.mark.usefixtures("restore_settings")
def test_bad_dictionary_is_refused(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    bad = _put(
        client,
        superuser_token_headers,
        {"radius_dictionary_extra": "}\nhost evil { address = 0.0.0.0/0 }"},
    )
    assert bad["status"] == 422


def test_radius_only_host(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    name = f"mikrotik-{uuid.uuid4().hex[:8]}"
    r = client.post(
        f"{API}/hosts/",
        headers=superuser_token_headers,
        json={
            "name": name,
            "ipv4_address": "192.0.2.88/32",
            "radius_secret_key": "r4dius",
        },
    )
    assert r.status_code == 200, r.text
    hid = r.json()["id"]
    try:
        assert r.json()["secret_key"] is None
        bad = client.post(
            f"{API}/hosts/",
            headers=superuser_token_headers,
            json={
                "name": f"{name}-q",
                "ipv4_address": "192.0.2.89/32",
                "radius_secret_key": 'a" }',
            },
        )
        assert bad.status_code == 422
    finally:
        client.delete(f"{API}/hosts/{hid}", headers=superuser_token_headers)


def test_hosts_filter_by_radius_secret(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    tag = uuid.uuid4().hex[:8]
    ids = []
    for suffix, body in (
        ("r", {"ipv4_address": "192.0.2.90/32", "radius_secret_key": "r4dius"}),
        (
            "t",
            {
                "ipv4_address": "192.0.2.91/32",
                "secret_key": "t",
                "radius_secret_key": "",
            },
        ),
    ):
        r = client.post(
            f"{API}/hosts/",
            headers=superuser_token_headers,
            json={"name": f"filter-{tag}-{suffix}"} | body,
        )
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])
    try:
        names = {
            flag: [
                h["name"]
                for h in client.get(
                    f"{API}/hosts/",
                    headers=superuser_token_headers,
                    params={"search": f"filter-{tag}", "has_radius_secret": flag},
                ).json()["data"]
            ]
            for flag in ("true", "false")
        }
        assert names == {"true": [f"filter-{tag}-r"], "false": [f"filter-{tag}-t"]}
    finally:
        for hid in ids:
            client.delete(f"{API}/hosts/{hid}", headers=superuser_token_headers)
