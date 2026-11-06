"""Raw-script profiles (#359): validation, the one-mode invariant, generation."""

import os
import uuid
from collections.abc import Callable, Generator

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.core.raw_script import check_raw_script, profile_names_in
from app.crud import profiles as profiles_crud
from app.crud import profilescripts as profilescripts_crud
from app.crud.tacacs_configs import generate_tacacs_ng_config, validate_config_text
from app.mcp_server import write_service
from app.models import (
    ConfigurationOption,
    Profile,
    ProfileCreate,
    ProfileScriptCreate,
    ProfileScriptUpdate,
    ProfileUpdate,
)

TAC_PLUS_NG_BIN = "/usr/local/sbin/tac_plus-ng"
needs_binary = pytest.mark.skipif(
    not os.path.exists(TAC_PLUS_NG_BIN),
    reason="tac_plus-ng binary only present inside the backend container",
)

# The reporter's per-command authorization profile, as the script body.
RO_CMD = """\
if (service == shell) {
    if (cmd == "") { set priv-lvl = 1  if (device.name =~ /C55-/) { add task = "#read-only-tg" }  permit }
    if (cmd =~ /^(show|display|ping|traceroute|terminal|exit|quit)(\\s|$)/) permit
    deny
}
if (service == junos-exec) { set local-user-name = tacacs_read_only  permit }
deny"""


@pytest.fixture
def tag(db: Session) -> Generator[str, None, None]:
    """Unique name prefix; removes the profiles and options it names."""
    t = f"raw{uuid.uuid4().hex[:8]}"
    yield t
    rows = db.exec(select(Profile).where(Profile.name.like(f"{t}%"))).all()
    for row in rows:
        db.delete(row)
    db.commit()


@pytest.fixture
def profile_option(db: Session) -> Generator[Callable[[str], None], None, None]:
    """Set the (unique) `profile` Configuration Option; restore it afterwards."""
    existing = db.exec(
        select(ConfigurationOption).where(ConfigurationOption.name == "profile")
    ).first()
    original = existing.config_option if existing else None

    def set_text(text: str) -> None:
        row = db.exec(
            select(ConfigurationOption).where(ConfigurationOption.name == "profile")
        ).first() or ConfigurationOption(name="profile", config_option="")
        row.config_option = text
        db.add(row)
        db.commit()

    yield set_text
    if original is None:
        db.exec(
            delete(ConfigurationOption).where(ConfigurationOption.name == "profile")
        )  # type: ignore[call-overload]
        db.commit()
    else:
        set_text(original)


def _raw(db: Session, name: str, text: str = RO_CMD, **kw: object) -> Profile:
    return profiles_crud.create_profile(
        session=db,
        profile_create=ProfileCreate(name=name, action="deny", raw_script=text, **kw),
    )


# --- text checks ------------------------------------------------------------


def test_reporter_profile_passes_the_checks() -> None:
    assert check_raw_script(RO_CMD) == []


@pytest.mark.parametrize(
    ("text", "needle"),
    [
        ("profile x { script { deny } }", "script body"),
        ("script {\n  deny\n}", "inside `script { }`"),
        ("permit\n}\nhost evil { }", "closes more blocks"),
        ("if (service == shell) {\n  permit", "left unclosed"),
        ('set a = "abc\n', "unterminated string"),
        ("if (cmd =~ /abc) deny", "unterminated regex"),
        ("include = /etc/passwd", "`include` is not allowed"),
    ],
)
def test_bad_text_is_refused(text: str, needle: str) -> None:
    assert needle in " ".join(check_raw_script(text))


def test_braces_inside_regex_strings_and_comments_are_ignored() -> None:
    text = (
        "if (cmd =~ /^show\\s{2}x/) { set a = \"}{\" set b = '{' }  # }}}\n"
        "if (cmd =~ /a\\/}/) permit\n"
        "deny"
    )
    assert check_raw_script(text) == []


# Each case below was run through tac_plus-ng -P (backend image): the guard
# must see exactly the braces tac_plus-ng sees, or text can close the profile
# early and inject top-level config.
@pytest.mark.parametrize(
    ("text", "needle"),
    [
        # `1#}`: for tac_plus-ng `#` after a word character is not a comment,
        # so this `}` closes a block; the guard used to skip it as a comment.
        ("if (service == shell) {\n set priv-lvl = 1#}\n}\n}", "space before `#`"),
        ("set priv-lvl = 1#x\ndeny", "space before `#`"),
        # after `)` it is a comment for tac_plus-ng; refused too, not guessed
        ("if (service == shell)#}\n{ permit }\ndeny", "space before `#`"),
        # '...' is a string for tac_plus-ng: its `{` is hidden, so the second
        # `}` really does close the script
        ("if (service == shell) {\n set x = '{'\n permit\n}\n}\ndeny", "closes more"),
        # `\}` outside a string is still a brace for tac_plus-ng
        ("if (service == shell) {\n set x = a\\}\n permit\n}\ndeny", "closes more"),
    ],
)
def test_guard_matches_tac_plus_ng_tokenizer(text: str, needle: str) -> None:
    assert needle in " ".join(check_raw_script(text))


def test_escapes_and_multiline_strings_are_accepted() -> None:
    assert check_raw_script("set x = 'a\\'}'\nset y = \"a\\\"}\"\ndeny") == []
    assert check_raw_script('set banner = "line1\n   line2"\ndeny') == []


def test_dto_normalizes_and_rejects() -> None:
    assert ProfileCreate(name="p", action="deny", raw_script=" \n ").raw_script is None
    assert (
        ProfileCreate(name="p", action="deny", raw_script="\n\ndeny  \n").raw_script
        == "deny"
    )
    with pytest.raises(ValidationError, match="closes more blocks"):
        ProfileCreate(name="p", action="deny", raw_script="deny }")
    # Update only cleans; the check runs in update_profile when text changes.
    assert ProfileUpdate(name="p", action="deny", raw_script=" \n").raw_script is None


def test_update_checks_changed_text_but_not_stored_text(db: Session, tag: str) -> None:
    row = _raw(db, f"{tag}-old", text="deny")
    # Stored text a newer check would reject (or written outside the API).
    row.raw_script = "set x = 1#}\ndeny"
    db.add(row)
    db.commit()

    # A partial update that resends the stored text, like MCP update_entity
    # does, still renames and disables the profile.
    updated = profiles_crud.update_profile(
        session=db,
        db_profile=row,
        profile_in=ProfileUpdate(
            name=f"{tag}-new",
            action="deny",
            generate_config=False,
            raw_script=row.raw_script,
        ),
    )
    assert updated.name == f"{tag}-new" and updated.generate_config is False

    with pytest.raises(ValueError, match="closes more blocks"):
        profiles_crud.update_profile(
            session=db,
            db_profile=updated,
            profile_in=ProfileUpdate(
                name=updated.name, action="deny", raw_script="deny }"
            ),
        )


def test_profile_names_in_finds_blocks() -> None:
    text = (
        "profile a {\n script { deny }\n}\n  profile b-2 {\n}\n"
        'profile "quoted" {\n}\n# profile c {'
    )
    assert profile_names_in(text) == {"a", "b-2", "quoted"}


# --- generation ---------------------------------------------------------------


def test_raw_profile_is_emitted_verbatim_without_action(db: Session, tag: str) -> None:
    _raw(db, f"{tag}-ro")
    out = profiles_crud.profile_generator(db)
    block = profiles_crud.render_raw_profile(f"{tag}-ro", RO_CMD)
    assert block in out
    # verbatim: the text's own lines and indentation, untouched
    assert f"        script {{\n{RO_CMD}\n        }}\n    }}\n" in block
    # the raw text's own last line closes the script: no fall-through action
    assert block.endswith("\ndeny\n        }\n    }\n")


def test_multiline_string_values_are_not_reindented(db: Session, tag: str) -> None:
    text = 'if (service == shell) {\n    set banner = "line1\n   line2"\n    permit\n}\ndeny'
    _raw(db, f"{tag}-ml", text=text)
    assert '"line1\n   line2"' in profiles_crud.profile_generator(db)


def test_raw_profile_with_generate_config_off_is_left_out(
    db: Session, tag: str
) -> None:
    _raw(db, f"{tag}-off", generate_config=False)
    assert f"profile {tag}-off" not in profiles_crud.profile_generator(db)


def test_override_renders_unsaved_text(db: Session, tag: str) -> None:
    row = _raw(db, f"{tag}-ov", text="deny")
    out = profiles_crud.profile_generator(db, override=(row.id, row.name, "permit"))
    assert out.count(f"profile {tag}-ov ") == 1
    assert profiles_crud.render_raw_profile(row.name, "permit") in out
    new = profiles_crud.profile_generator(db, override=(None, f"{tag}-new", "deny"))
    assert f"profile {tag}-new " in new


def test_script_line_maps_back_into_the_script(db: Session, tag: str) -> None:
    name = f"{tag}-ln"
    config = generate_tacacs_ng_config(
        session=db, profile_override=(None, name, RO_CMD)
    )
    lines = config.split("\n")
    # find the config line holding the script's third line
    third = RO_CMD.split("\n")[2].strip()
    config_line = next(i for i, ln in enumerate(lines, 1) if ln.strip() == third)
    assert (
        profiles_crud.script_line_of(
            config=config, name=name, raw_script=RO_CMD, config_line=config_line
        )
        == 3
    )
    assert (
        profiles_crud.script_line_of(
            config=config, name=name, raw_script=RO_CMD, config_line=1
        )
        is None
    )


# --- one mode per profile -------------------------------------------------------


def test_scripts_cannot_be_added_to_a_raw_profile(db: Session, tag: str) -> None:
    row = _raw(db, f"{tag}-r")
    with pytest.raises(ValueError, match="uses a raw script"):
        profilescripts_crud.create_profilescript(
            session=db,
            profilescript_create=ProfileScriptCreate(
                condition="if",
                key="service",
                value="shell",
                action="permit",
                profile_id=row.id,
            ),
        )


def test_raw_script_cannot_be_set_on_a_profile_with_scripts(
    db: Session, tag: str
) -> None:
    row = profiles_crud.create_profile(
        session=db, profile_create=ProfileCreate(name=f"{tag}-s", action="deny")
    )
    profilescripts_crud.create_profilescript(
        session=db,
        profilescript_create=ProfileScriptCreate(
            condition="if",
            key="service",
            value="shell",
            action="permit",
            profile_id=row.id,
        ),
    )
    with pytest.raises(ValueError, match="has 1 structured script;"):
        profiles_crud.update_profile(
            session=db,
            db_profile=row,
            profile_in=ProfileUpdate(name=row.name, action="deny", raw_script="deny"),
        )


def test_script_cannot_move_to_a_raw_profile(db: Session, tag: str) -> None:
    plain = profiles_crud.create_profile(
        session=db, profile_create=ProfileCreate(name=f"{tag}-m1", action="deny")
    )
    raw = _raw(db, f"{tag}-m2")
    script = profilescripts_crud.create_profilescript(
        session=db,
        profilescript_create=ProfileScriptCreate(
            condition="if",
            key="service",
            value="shell",
            action="permit",
            profile_id=plain.id,
        ),
    )
    with pytest.raises(ValueError, match="uses a raw script"):
        profilescripts_crud.update_profilescript(
            session=db,
            db_profilescript=script,
            profilescript_in=ProfileScriptUpdate(
                condition="if",
                key="service",
                value="shell",
                action="permit",
                profile_id=raw.id,
            ),
        )


# --- duplicate definitions ------------------------------------------------------


def test_duplicate_names_counts_only_emitted_rows(
    db: Session, tag: str, profile_option: Callable[[str], None]
) -> None:
    profile_option(
        f"profile {tag}-dup {{\n script {{ deny }}\n}}\n"
        f"profile {tag}-ph {{\n script {{ deny }}\n}}"
    )
    _raw(db, f"{tag}-dup", text="deny")  # emitted: clashes
    profiles_crud.create_profile(  # script-less placeholder: not emitted
        session=db, profile_create=ProfileCreate(name=f"{tag}-ph", action="deny")
    )
    assert profiles_crud.duplicate_profile_names(session=db) == [f"{tag}-dup"]


# --- MCP and HTTP -----------------------------------------------------------------


def test_mcp_create_and_refusal(db: Session, tag: str) -> None:
    write_service.create_entity(
        session=db,
        entity_type="profile",
        data={"name": f"{tag}-mcp", "action": "deny", "raw_script": RO_CMD},
    )
    assert profiles_crud.get_profile_by_name(session=db, name=f"{tag}-mcp")
    with pytest.raises(ValueError, match="closes more blocks"):
        write_service.create_entity(
            session=db,
            entity_type="profile",
            data={"name": f"{tag}-bad", "action": "deny", "raw_script": "deny }"},
        )


def test_api_create_update_and_check(
    client: TestClient, superuser_token_headers: dict[str, str], tag: str
) -> None:
    url = f"{settings.API_V1_STR}/profiles/"
    r = client.post(
        url,
        headers=superuser_token_headers,
        json={"name": f"{tag}-api", "action": "deny", "raw_script": RO_CMD},
    )
    assert r.status_code == 200, r.text
    assert r.json()["raw_script"] == RO_CMD
    pid = r.json()["id"]

    r = client.post(
        url,
        headers=superuser_token_headers,
        json={"name": f"{tag}-api2", "action": "deny", "raw_script": "profile x {}"},
    )
    assert r.status_code == 422

    r = client.post(
        f"{settings.API_V1_STR}/profilescripts/",
        headers=superuser_token_headers,
        json={
            "condition": "if",
            "key": "service",
            "value": "shell",
            "action": "permit",
            "profile_id": pid,
        },
    )
    assert r.status_code == 400
    assert "uses a raw script" in r.json()["detail"]

    r = client.post(
        f"{settings.API_V1_STR}/profiles/check",
        headers=superuser_token_headers,
        json={"id": pid, "name": f"{tag}-api", "raw_script": "deny }"},
    )
    assert r.status_code == 422


def test_generate_refuses_a_duplicate_definition(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    db: Session,
    tag: str,
    profile_option: Callable[[str], None],
) -> None:
    profile_option(f"profile {tag}-gen {{\n script {{ deny }}\n}}")
    _raw(db, f"{tag}-gen", text="deny")
    r = client.post(
        f"{settings.API_V1_STR}/tacacs_configs/",
        headers=superuser_token_headers,
        json={"filename": f"{tag}.cfg"},
    )
    assert r.status_code == 400
    assert f"'{tag}-gen' is defined both" in r.json()["detail"]


@needs_binary
def test_reporter_profile_passes_tac_plus_ng(db: Session, tag: str) -> None:
    config = generate_tacacs_ng_config(
        session=db, profile_override=(None, f"{tag}-bin", RO_CMD)
    )
    result = validate_config_text(text=config)
    assert result["status"] == "success", result["raw_output"]


@needs_binary
def test_check_endpoint_maps_the_error_line(
    client: TestClient, superuser_token_headers: dict[str, str], tag: str
) -> None:
    r = client.post(
        f"{settings.API_V1_STR}/profiles/check",
        headers=superuser_token_headers,
        json={
            "name": f"{tag}-chk",
            "raw_script": "if (service == shell) {\n  frobnicate\n}",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "error"
    assert "frobnicate" in body["message"]
    # tac_plus-ng reports the line of the last token it accepted (the `{` on
    # line 1), not always the line of the token it rejects (line 2).
    assert body["script_line"] in (1, 2)
