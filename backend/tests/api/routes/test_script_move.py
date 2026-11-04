import uuid

from fastapi.testclient import TestClient

from app.core.config import settings

API = settings.API_V1_STR


def _profile(client: TestClient, headers: dict[str, str]) -> str:
    r = client.post(
        f"{API}/profiles/",
        headers=headers,
        json={"name": f"mv-{uuid.uuid4().hex[:8]}", "action": "deny"},
    )
    assert r.status_code == 200, r.text
    return str(r.json()["id"])


def _script(
    client: TestClient,
    headers: dict[str, str],
    profile_id: str,
    value: str,
    condition: str = "if",
) -> dict[str, object]:
    r = client.post(
        f"{API}/profilescripts/",
        headers=headers,
        json={
            "condition": condition,
            "key": "device",
            "value": value,
            "action": "permit",
            "profile_id": profile_id,
        },
    )
    assert r.status_code == 200, r.text
    body: dict[str, object] = r.json()
    return body


def test_profilescript_move_endpoint(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    profile_id = _profile(client, superuser_token_headers)
    a = _script(client, superuser_token_headers, profile_id, "a")
    b = _script(client, superuser_token_headers, profile_id, "b")
    assert (a["position"], b["position"]) == (0, 1)

    r = client.post(
        f"{API}/profilescripts/{b['id']}/move",
        headers=superuser_token_headers,
        json={"position": 0},
    )
    assert r.status_code == 200, r.text
    assert r.json()["position"] == 0

    r = client.get(
        f"{API}/profilescripts/",
        headers=superuser_token_headers,
        params={"limit": 1000},
    )
    mine = [s["value"] for s in r.json()["data"] if s["profile_id"] == profile_id]
    assert mine == ["b", "a"]

    # A move that leaves an `else` first is refused and changes nothing.
    e = _script(client, superuser_token_headers, profile_id, "z", condition="else")
    r = client.post(
        f"{API}/profilescripts/{e['id']}/move",
        headers=superuser_token_headers,
        json={"position": 0},
    )
    assert r.status_code == 400
    assert "else" in r.json()["detail"]

    r = client.post(
        f"{API}/profilescripts/{uuid.uuid4()}/move",
        headers=superuser_token_headers,
        json={"position": 0},
    )
    assert r.status_code == 404

    r = client.post(
        f"{API}/profilescripts/{a['id']}/move",
        headers=superuser_token_headers,
        json={"position": -1},
    )
    assert r.status_code == 422

    client.delete(f"{API}/profiles/{profile_id}", headers=superuser_token_headers)


def test_move_requires_superuser(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    normal_user_token_headers: dict[str, str],
) -> None:
    profile_id = _profile(client, superuser_token_headers)
    a = _script(client, superuser_token_headers, profile_id, "a")
    r = client.post(
        f"{API}/profilescripts/{a['id']}/move",
        headers=normal_user_token_headers,
        json={"position": 0},
    )
    assert r.status_code in (401, 403)
    client.delete(f"{API}/profiles/{profile_id}", headers=superuser_token_headers)


def test_ruleset_move_endpoint(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    tag = uuid.uuid4().hex[:8]
    ids = []
    for n in ("one", "two"):
        r = client.post(
            f"{API}/rulesets/",
            headers=superuser_token_headers,
            json={"name": f"mv-{tag}-{n}", "action": "deny"},
        )
        assert r.status_code == 200, r.text
        ids.append(r.json()["id"])

    r = client.post(
        f"{API}/rulesets/{ids[1]}/move",
        headers=superuser_token_headers,
        json={"position": 0},
    )
    assert r.status_code == 200, r.text
    r = client.get(
        f"{API}/rulesets/", headers=superuser_token_headers, params={"limit": 1000}
    )
    names = [x["name"] for x in r.json()["data"]]
    assert names.index(f"mv-{tag}-two") < names.index(f"mv-{tag}-one")
    assert [x["position"] for x in r.json()["data"]] == list(range(len(names)))

    for rid in ids:
        client.delete(f"{API}/rulesets/{rid}", headers=superuser_token_headers)
