"""
A TACACS+ user's password type and clear password end up in the generated
config as `password login = <type> "<password>"` (plus the chap / ms-chap
lines for `clear`). Neither may be able to end its token and add config
inside the `user { }` block (#437).
"""

import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.crud.tacacs_configs import generate_tacacs_ng_config
from app.models import TacacsUser

API = settings.API_V1_STR
INJECTED = 'x"\n        member = tacacs_super_user\n        password pap = clear "y'


@pytest.fixture
def created(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> Iterator[list[str]]:
    ids: list[str] = []
    yield ids
    for uid in ids:
        client.delete(f"{API}/tacacs_users/{uid}", headers=superuser_token_headers)


def _create(
    client: TestClient, headers: dict[str, str], **fields: str
) -> tuple[int, dict]:
    body = {
        "username": f"pwsafe-{uuid.uuid4().hex[:8]}",
        "member": "tacacs_super_user",
        **fields,
    }
    r = client.post(f"{API}/tacacs_users/", headers=headers, json=body)
    return r.status_code, r.json()


@pytest.mark.parametrize("password", ['ab"cd', "ab\\cd", "ab\ncd", "ab\rcd"])
def test_clear_password_refuses_characters_that_end_the_string(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    password: str,
) -> None:
    code, body = _create(
        client, superuser_token_headers, password_type="clear", password=password
    )
    assert code == 422, body
    assert "clear password" in str(body)


def test_crypt_password_may_contain_them(
    client: TestClient, superuser_token_headers: dict[str, str], created: list[str]
) -> None:
    """A crypt password is hashed before it is stored; only the hash is written."""
    code, body = _create(
        client, superuser_token_headers, password_type="crypt", password='ab"c\\d'
    )
    assert code == 200, body
    created.append(body["id"])


@pytest.mark.parametrize("password_type", ['clear "x"', "clear\n", "plain"])
def test_password_type_is_one_of_the_known_types(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    created: list[str],
    password_type: str,
) -> None:
    code, body = _create(
        client, superuser_token_headers, password_type=password_type, password="pw"
    )
    assert code == 422, body
    uid = _create(
        client, superuser_token_headers, password_type="crypt", password="pw1234"
    )[1]["id"]
    created.append(uid)
    r = client.put(
        f"{API}/tacacs_users/{uid}",
        headers=superuser_token_headers,
        json={"password_type": password_type},
    )
    assert r.status_code == 422, r.text


def test_update_checks_the_merged_row(
    client: TestClient, superuser_token_headers: dict[str, str], created: list[str]
) -> None:
    """The PUT is partial: a new password on a clear user, and a switch to
    clear together with a new password, are both checked."""
    code, body = _create(
        client, superuser_token_headers, password_type="clear", password="ok-pw"
    )
    assert code == 200, body
    created.append(body["id"])
    url = f"{API}/tacacs_users/{body['id']}"

    r = client.put(url, headers=superuser_token_headers, json={"password": INJECTED})
    assert r.status_code == 400, r.text

    code, body = _create(
        client, superuser_token_headers, password_type="crypt", password="ok-pw"
    )
    assert code == 200, body
    created.append(body["id"])
    url = f"{API}/tacacs_users/{body['id']}"
    r = client.put(
        url,
        headers=superuser_token_headers,
        json={"password_type": "clear", "password": INJECTED},
    )
    assert r.status_code == 400, r.text
    # an unrelated edit of a user is still accepted
    r = client.put(url, headers=superuser_token_headers, json={"description": "x"})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize(
    "password_type, password",
    [("clear", INJECTED), ('clear "a"\n        member = admins\n#', "pw")],
)
def test_a_bad_stored_user_is_left_out_of_the_config(
    db: Session, password_type: str, password: str
) -> None:
    """Rows stored before these checks, or written around the API."""
    user = TacacsUser(
        username=f"pwsafe-{uuid.uuid4().hex[:8]}",
        password_type=password_type,
        password=password,
        member="tacacs_super_user",
        generate_config=True,
    )
    db.add(user)
    db.commit()
    try:
        config = generate_tacacs_ng_config(session=db)
        assert f"user {user.username} {{" not in config
        assert "member = admins" not in config
        assert 'password pap = clear "y' not in config
    finally:
        db.delete(user)
        db.commit()
