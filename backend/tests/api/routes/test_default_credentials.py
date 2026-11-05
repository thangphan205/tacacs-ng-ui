import uuid
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core import db as db_module
from app.core.config import settings
from app.crud.default_credentials import DEMO_PASSWORD
from app.crud.tacacs_users import hash_tacacs_password
from app.models import Host, TacacsUser

URL = f"{settings.API_V1_STR}/tacacs_configs/default_credentials"


def _names(client: TestClient, headers: dict[str, str]) -> set[tuple[str, str]]:
    r = client.get(URL, headers=headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["count"] == len(body["data"])
    return {(f["kind"], f["name"]) for f in body["data"]}


@pytest.fixture()
def user_admin(db: Session) -> Generator[TacacsUser, None, None]:
    db_module._seed_demo_data(db)
    db.commit()
    user = db.exec(select(TacacsUser).where(TacacsUser.username == "user_admin")).one()
    original = (user.password_type, user.password, user.generate_config)
    yield user
    db.refresh(user)
    user.password_type, user.password, user.generate_config = original
    db.add(user)
    db.commit()


def test_demo_user_with_demo_password_is_flagged(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    user_admin: TacacsUser,
) -> None:
    user_admin.password_type = "crypt"
    user_admin.password = hash_tacacs_password(DEMO_PASSWORD)
    user_admin.generate_config = True
    db.add(user_admin)
    db.commit()
    assert ("tacacs_user", "user_admin") in _names(client, superuser_token_headers)

    # Left out of the generated config: cannot reach a device.
    user_admin.generate_config = False
    db.add(user_admin)
    db.commit()
    assert ("tacacs_user", "user_admin") not in _names(client, superuser_token_headers)

    user_admin.generate_config = True
    user_admin.password = hash_tacacs_password(uuid.uuid4().hex)
    db.add(user_admin)
    db.commit()
    assert ("tacacs_user", "user_admin") not in _names(client, superuser_token_headers)


def test_any_clear_text_user_with_demo_password_is_flagged(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    user = TacacsUser(
        username=f"clear-{uuid.uuid4().hex[:8]}",
        password_type="clear",
        password=DEMO_PASSWORD,
        member="tacacs_read_only",
    )
    db.add(user)
    db.commit()
    try:
        assert ("tacacs_user", user.username) in _names(client, superuser_token_headers)
    finally:
        db.delete(user)
        db.commit()


def test_host_with_demo_key_is_flagged(
    client: TestClient, superuser_token_headers: dict[str, str], db: Session
) -> None:
    host = Host(
        name=f"demo-key-{uuid.uuid4().hex[:8]}",
        ipv4_address="192.0.2.1/32",
        secret_key=DEMO_PASSWORD,
    )
    db.add(host)
    db.commit()
    try:
        assert ("host", host.name) in _names(client, superuser_token_headers)
        host.secret_key = uuid.uuid4().hex
        db.add(host)
        db.commit()
        assert ("host", host.name) not in _names(client, superuser_token_headers)
    finally:
        db.delete(host)
        db.commit()


def test_requires_authentication(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
