"""
Names and actions written unquoted into the generated config (#442): the API
refuses unsafe new values, an update checks only what changes, and the
generator never writes a stored value that could change the config's
structure (core/config_names.py).
"""

import os
import uuid
from collections.abc import Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel

from app.core.config import settings
from app.crud.tacacs_configs import generate_tacacs_ng_config, validate_config_text
from app.models import (
    Host,
    Profile,
    ProfileScript,
    Ruleset,
    RulesetScript,
    TacacsGroup,
    TacacsUser,
)

API = settings.API_V1_STR
EVIL = "x } user evil { member = admins"


def _uid() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def api(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> Iterator[Callable[..., Any]]:
    """POST/PUT helper that deletes what it created, newest first."""
    created: list[str] = []

    def call(method: str, path: str, body: dict[str, Any]) -> Any:
        r = getattr(client, method)(
            f"{API}/{path}", headers=superuser_token_headers, json=body
        )
        if method == "post" and r.status_code == 200:
            created.append(f"{path.rstrip('/')}/{r.json()['id']}")
        return r

    yield call
    for path in reversed(created):
        client.delete(f"{API}/{path}", headers=superuser_token_headers)


def _bodies() -> dict[str, tuple[str, dict[str, Any], list[str]]]:
    """path -> (valid create body, the fields checked)."""
    return {
        "hosts/": (
            "hosts/",
            {
                "name": f"h-{_uid()}",
                "ipv4_address": "198.18.42.1/32",
                "secret_key": "k",
            },
            ["name", "parent"],
        ),
        "tacacs_groups/": (
            "tacacs_groups/",
            {"group_name": f"g-{_uid()}"},
            ["group_name"],
        ),
        "tacacs_users/": (
            "tacacs_users/",
            {
                "username": f"u-{_uid()}",
                "password_type": "crypt",
                "password": "pw-123456",
                "member": "tacacs_super_user",
            },
            ["username", "member"],
        ),
        "rulesets/": (
            "rulesets/",
            {"name": f"r-{_uid()}", "action": "deny"},
            ["name", "action"],
        ),
        "profiles/": (
            "profiles/",
            {"name": f"p-{_uid()}", "action": "deny"},
            ["action"],
        ),
    }


@pytest.mark.parametrize("path", sorted(_bodies()))
def test_create_and_update_refuse_unsafe_values(
    api: Callable[..., Any], path: str
) -> None:
    _, body, fields = _bodies()[path]
    for field in fields:
        r = api("post", path, {**body, field: EVIL})
        assert r.status_code == 422, (field, r.text)

    r = api("post", path, body)
    assert r.status_code == 200, r.text
    row = r.json()
    for field in fields:
        r = api("put", f"{path}{row['id']}", {**body, field: EVIL})
        assert r.status_code == 400, (field, r.text)
    # resending the unchanged row is fine
    r = api("put", f"{path}{row['id']}", {**body, "description": "edited"})
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("kind", ["profilescripts/", "rulesetscripts/"])
def test_script_actions_must_be_one_word(api: Callable[..., Any], kind: str) -> None:
    if kind == "profilescripts/":
        parent = api("post", "profiles/", {"name": f"p-{_uid()}", "action": "deny"})
        parent_field = "profile_id"
    else:
        parent = api("post", "rulesets/", {"name": f"r-{_uid()}", "action": "deny"})
        parent_field = "ruleset_id"
    assert parent.status_code == 200, parent.text
    body = {
        "condition": "if",
        "key": "device",
        "value": "core",
        "action": "permit",
        parent_field: parent.json()["id"],
    }
    assert api("post", kind, {**body, "action": "permit }"}).status_code == 422
    r = api("post", kind, body)
    assert r.status_code == 200, r.text
    r = api("put", f"{kind}{r.json()['id']}", {**body, "action": "deny\n}"})
    assert r.status_code == 400, r.text


def test_member_spaces_are_normalized(api: Callable[..., Any]) -> None:
    group = api("post", "tacacs_groups/", {"group_name": f"g-{_uid()}"})
    assert group.status_code == 200, group.text
    g = group.json()["group_name"]
    r = api(
        "post",
        "tacacs_users/",
        {
            "username": f"u-{_uid()}",
            "password_type": "crypt",
            "password": "pw-123456",
            "member": f"tacacs_super_user, {g}",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json()["member"] == f"tacacs_super_user,{g}"


def test_an_existing_row_with_an_old_name_stays_editable(
    db: Session, api: Callable[..., Any]
) -> None:
    """`o'brien` parses today, so a stored user with it is not locked out of edits."""
    user = TacacsUser(
        username=f"o'brien-{_uid()}",
        password_type="crypt",
        password="$6$rounds=5000$abcdefgh$" + "a" * 86,
        member="tacacs_super_user",
    )
    db.add(user)
    db.commit()
    try:
        r = api(
            "put",
            f"tacacs_users/{user.id}",
            {"username": user.username, "description": "edited"},
        )
        assert r.status_code == 200, r.text
        r = api("put", f"tacacs_users/{user.id}", {"username": f"new'name-{_uid()}"})
        assert r.status_code == 400, r.text
    finally:
        db.delete(user)
        db.commit()


# --- the generator, for rows stored before these checks ------------------------


@pytest.fixture
def stored(db: Session) -> Iterator[Callable[[SQLModel], SQLModel]]:
    rows: list[SQLModel] = []

    def add(row: SQLModel) -> SQLModel:
        db.add(row)
        db.commit()
        db.refresh(row)
        rows.append(row)
        return row

    yield add
    for row in reversed(rows):
        db.delete(row)
    db.commit()


def test_unsafe_stored_names_never_reach_the_config(
    db: Session, stored: Callable[[SQLModel], SQLModel]
) -> None:
    s = _uid()
    bad_group = stored(TacacsGroup(group_name=f"g{s} }} user evil{s} {{"))
    stored(
        TacacsUser(
            username=f"evil{s} {{ member = admins }} user x{s}",
            password_type="clear",
            password="pw",
            member="tacacs_super_user",
        )
    )
    stored(
        TacacsUser(
            username=f"via-group-{s}",
            password_type="clear",
            password="pw",
            member=f"tacacs_super_user,{bad_group.group_name}",  # type: ignore[attr-defined]
        )
    )
    stored(
        Host(
            name=f"h{s} {{ address = 192.0.2.250/32 }} host = x{s}",
            ipv4_address="198.18.43.1/32",
            secret_key="k",
        )
    )
    config = generate_tacacs_ng_config(session=db)
    assert f"evil{s}" not in config
    assert f"via-group-{s}" not in config
    assert f"x{s}" not in config
    assert "192.0.2.250/32" not in config


def test_unsafe_stored_rules_and_actions_fail_closed(
    db: Session, stored: Callable[[SQLModel], SQLModel]
) -> None:
    """A rule keeps its place under a substitute label; an unsafe action is
    written as deny, so nothing is let through that the admin meant to stop."""
    s = _uid()
    rule = stored(Ruleset(name=f"r{s} {{ }} rule evil{s}", action="deny }"))
    stored(
        RulesetScript(
            condition="if",
            key="device",
            value=f"dev{s}",
            action="permit } permit",
            ruleset_id=rule.id,  # type: ignore[attr-defined]
        )
    )
    profile = stored(Profile(name=f"p{s}", action="permit\n}"))
    stored(
        ProfileScript(
            condition="if",
            key="device",
            value=f"dev{s}",
            action="permit }",
            profile_id=profile.id,  # type: ignore[attr-defined]
        )
    )
    config = generate_tacacs_ng_config(session=db)
    assert f"evil{s}" not in config
    assert f"rule ruleset_{rule.id} {{" in config  # type: ignore[attr-defined]
    rule_block = config.split(f"rule ruleset_{rule.id} {{", 1)[1]  # type: ignore[attr-defined]
    rule_block = rule_block.split("rule ", 1)[0]
    assert "permit" not in rule_block
    profile_block = config.split(f"profile p{s} {{", 1)[1]
    profile_block = profile_block.split("\n    }\n", 1)[0]
    assert "permit" not in profile_block
    assert profile_block.count("deny") == 2


TAC_PLUS_NG_BIN = "/usr/local/sbin/tac_plus-ng"


@pytest.mark.skipif(
    not os.path.exists(TAC_PLUS_NG_BIN),
    reason="tac_plus-ng binary only present inside the backend container",
)
def test_names_that_parse_today_still_pass_the_syntax_check(
    db: Session, stored: Callable[[SQLModel], SQLModel]
) -> None:
    """Stored `o'brien` / `DOMAIN\\user` rows, the unsafe rows above and an
    unsafe rule: the generated config passes `tac_plus-ng -P`."""
    s = _uid()
    stored(TacacsGroup(group_name=f"grp'{s}"))
    for name in (f"o'brien{s}", f"DOMAIN\\user{s}", f"a#b{s}"):
        stored(
            TacacsUser(
                username=name,
                password_type="clear",
                password="pw",
                member=f"grp'{s}",
            )
        )
    stored(
        TacacsUser(
            username=f"evil{s} {{ x",
            password_type="clear",
            password="pw",
            member="tacacs_super_user",
        )
    )
    rule = stored(Ruleset(name=f"r{s} {{ }}", action="deny }"))
    stored(
        RulesetScript(
            condition="if",
            key="user",
            value=f"nobody{s}",
            action="permit",
            ruleset_id=rule.id,  # type: ignore[attr-defined]
        )
    )
    config = generate_tacacs_ng_config(session=db)
    assert f"user o'brien{s} {{" in config
    assert f"user DOMAIN\\user{s} {{" in config
    result = validate_config_text(text=config)
    assert result["status"] == "success", result["raw_output"]
