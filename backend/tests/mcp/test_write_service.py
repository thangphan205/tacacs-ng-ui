"""Unit tests for the MCP entity write layer.

Exercises `write_service` directly with the session fixture — no MCP transport,
no authorization. Scope and superuser gating live in `tools.py` and are covered
by `test_mcp_endpoint.py`.
"""

from typing import Any

import pytest
from sqlmodel import Session

from app.crud import tacacs_users as tacacs_users_crud
from app.mcp_server import write_service
from app.models import TacacsUser
from tests.utils.utils import random_lower_string


def _name(prefix: str) -> str:
    return f"{prefix}-{random_lower_string()[:10]}"


# One minimal valid create payload per writable entity type, keyed the same way
# `write_service.WRITABLE` is.
def _payloads() -> dict[str, tuple[str, dict[str, Any]]]:
    """entity_type -> (name_field, create payload)."""
    return {
        "host": (
            "name",
            {"name": _name("h"), "ipv4_address": "10.1.2.0/24", "secret_key": "s3cr3t"},
        ),
        "user": (
            "username",
            {
                "username": _name("u"),
                "password_type": "clear",
                "member": "some-group",
                "password": "plaintext-pw",
            },
        ),
        "group": ("group_name", {"group_name": _name("g")}),
        "profile": ("name", {"name": _name("p"), "action": "deny"}),
        "ruleset": ("name", {"name": _name("r"), "action": "permit"}),
        "mavis": ("mavis_key", {"mavis_key": _name("m"), "mavis_value": "ldap-value"}),
        "configuration_option": (
            "name",
            {"name": _name("c"), "config_option": "# nothing"},
        ),
        "tacacs_service": ("name", {"name": _name("svc")}),
    }


@pytest.mark.parametrize("entity_type", sorted(write_service.WRITABLE))
def test_create_update_delete_round_trip(db: Session, entity_type: str) -> None:
    name_field, payload = _payloads()[entity_type]
    name = payload[name_field]

    created = write_service.create_entity(
        session=db, entity_type=entity_type, data=payload
    )
    assert created.item is not None
    assert created.item[name_field] == name
    assert created.entity_id is not None
    assert created.new_values is not None

    # Partial payload: everything not named keeps its current value.
    renamed = f"{name}-2"
    updated = write_service.update_entity(
        session=db,
        entity_type=entity_type,
        name=name,
        data={name_field: renamed},
    )
    assert updated.item is not None
    assert updated.item[name_field] == renamed
    assert updated.entity_id == created.entity_id
    assert updated.old_values is not None

    deleted = write_service.delete_entity(
        session=db, entity_type=entity_type, name=renamed
    )
    assert deleted.entity_id == created.entity_id
    assert deleted.old_values is not None

    with pytest.raises(LookupError):
        write_service.update_entity(
            session=db, entity_type=entity_type, name=renamed, data={}
        )


def test_create_rejects_a_duplicate_name(db: Session) -> None:
    name_field, payload = _payloads()["group"]
    write_service.create_entity(session=db, entity_type="group", data=payload)
    try:
        with pytest.raises(ValueError, match="already exists"):
            write_service.create_entity(session=db, entity_type="group", data=payload)
    finally:
        write_service.delete_entity(
            session=db, entity_type="group", name=payload[name_field]
        )


def test_update_rejects_renaming_onto_another_row(db: Session) -> None:
    first = _payloads()["group"][1]
    second = _payloads()["group"][1]
    write_service.create_entity(session=db, entity_type="group", data=first)
    write_service.create_entity(session=db, entity_type="group", data=second)
    try:
        with pytest.raises(ValueError, match="already exists"):
            write_service.update_entity(
                session=db,
                entity_type="group",
                name=first["group_name"],
                data={"group_name": second["group_name"]},
            )
    finally:
        for row in (first, second):
            write_service.delete_entity(
                session=db, entity_type="group", name=row["group_name"]
            )


def test_delete_of_a_missing_row_is_a_lookup_error(db: Session) -> None:
    with pytest.raises(LookupError):
        write_service.delete_entity(
            session=db, entity_type="group", name="no-such-group-xyz"
        )


def test_unwritable_entity_type_is_rejected(db: Session) -> None:
    with pytest.raises(LookupError, match="not writable"):
        write_service.create_entity(
            session=db, entity_type="tacacs_config", data={"filename": "x"}
        )


def test_validation_errors_name_the_offending_field(db: Session) -> None:
    with pytest.raises(ValueError, match="password_type"):
        write_service.create_entity(
            session=db, entity_type="user", data={"username": _name("u")}
        )


def test_user_password_is_hashed_and_never_returned(db: Session) -> None:
    payload = {
        "username": _name("u"),
        "password_type": "crypt",
        "member": "some-group",
        "password": "plaintext-pw",
    }
    created = write_service.create_entity(
        session=db, entity_type="user", data=payload
    )
    assert created.item is not None
    assert created.item["password"] == "***REDACTED***"

    row = tacacs_users_crud.get_tacacs_user_by_username(
        session=db, username=payload["username"]
    )
    assert row is not None
    assert row.password is not None
    assert row.password.startswith("$6$")

    write_service.delete_entity(
        session=db, entity_type="user", name=payload["username"]
    )


def test_partial_update_does_not_rehash_an_untouched_password(db: Session) -> None:
    """The merge seeds the payload from the row, so the stored hash round-trips."""
    payload = {
        "username": _name("u"),
        "password_type": "crypt",
        "member": "some-group",
        "password": "plaintext-pw",
    }
    write_service.create_entity(session=db, entity_type="user", data=payload)
    before = tacacs_users_crud.get_tacacs_user_by_username(
        session=db, username=payload["username"]
    )
    assert before is not None
    hash_before = before.password

    write_service.update_entity(
        session=db,
        entity_type="user",
        name=payload["username"],
        data={"description": "edited"},
    )
    after = db.get(TacacsUser, before.id)
    assert after is not None
    assert after.password == hash_before
    assert after.description == "edited"

    write_service.delete_entity(
        session=db, entity_type="user", name=payload["username"]
    )
