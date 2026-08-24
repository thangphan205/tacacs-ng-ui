import pytest
from sqlmodel import Session

from app.mcp_server import service
from app.models import (
    Host,
    Profile,
    ProfileScript,
    ProfileScriptSet,
    Ruleset,
    RulesetScript,
    RulesetScriptSet,
    TacacsUser,
)
from tests.utils.utils import random_lower_string


@pytest.fixture
def sample_host(db: Session) -> Host:
    host = Host(
        name=f"h-{random_lower_string()[:10]}",
        ipv4_address="10.9.8.0/24",
        secret_key="mcp-test-host-secret",
        generate_config=True,
    )
    db.add(host)
    db.commit()
    db.refresh(host)
    yield host
    db.delete(host)
    db.commit()


@pytest.fixture
def sample_profile(db: Session) -> Profile:
    profile = Profile(
        name=f"p-{random_lower_string()[:10]}", action="deny", generate_config=True
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)

    script = ProfileScript(
        condition="if",
        key="service",
        value="shell",
        action="permit",
        profile_id=profile.id,
    )
    db.add(script)
    db.commit()
    db.refresh(script)

    script_set = ProfileScriptSet(
        key="priv-lvl", value="15", profilescript_id=script.id
    )
    db.add(script_set)
    db.commit()

    yield profile

    db.delete(script_set)
    db.delete(script)
    db.delete(profile)
    db.commit()


@pytest.fixture
def sample_ruleset(db: Session) -> Ruleset:
    ruleset = Ruleset(
        name=f"r-{random_lower_string()[:10]}", action="deny", generate_config=True
    )
    db.add(ruleset)
    db.commit()
    db.refresh(ruleset)

    script = RulesetScript(
        condition="if",
        key="group",
        value="g1",
        action="permit",
        ruleset_id=ruleset.id,
    )
    db.add(script)
    db.commit()
    db.refresh(script)

    script_set = RulesetScriptSet(key="profile", value="p1", rulesetscript_id=script.id)
    db.add(script_set)
    db.commit()

    yield ruleset

    db.delete(script_set)
    db.delete(script)
    db.delete(ruleset)
    db.commit()


# --- list_entities ---


def test_list_entities_masks_host_secret(db: Session, sample_host: Host) -> None:
    result = service.list_entities(session=db, entity_type="host")
    assert result["entity_type"] == "host"
    assert result["total"] >= 1
    match = next(i for i in result["items"] if i["name"] == sample_host.name)
    assert match["secret_key"] == "***REDACTED***"
    assert match["ipv4_address"] == "10.9.8.0/24"


def test_list_entities_search_narrows_results(db: Session, sample_host: Host) -> None:
    result = service.list_entities(
        session=db, entity_type="host", search=sample_host.name
    )
    assert result["count"] == 1
    assert result["items"][0]["name"] == sample_host.name


def test_list_entities_only_generated_filter(db: Session, sample_host: Host) -> None:
    included = service.list_entities(
        session=db, entity_type="host", search=sample_host.name, only_generated=True
    )
    excluded = service.list_entities(
        session=db, entity_type="host", search=sample_host.name, only_generated=False
    )
    assert included["count"] == 1
    assert excluded["count"] == 0


def test_list_entities_pagination(db: Session) -> None:
    page = service.list_entities(session=db, entity_type="host", limit=1, offset=0)
    assert page["count"] <= 1
    assert page["total"] >= page["count"]


def test_list_entities_masks_user_password(db: Session) -> None:
    user = TacacsUser(
        username=f"u-{random_lower_string()[:10]}",
        password_type="clear",
        password="mcp-test-user-password",
        member="g1",
        generate_config=True,
    )
    db.add(user)
    db.commit()
    try:
        result = service.list_entities(
            session=db, entity_type="user", search=user.username
        )
        assert result["items"][0]["password"] == "***REDACTED***"
    finally:
        db.delete(user)
        db.commit()


def test_list_entities_covers_every_declared_type(db: Session) -> None:
    for entity_type in service.ENTITY_TYPES:
        result = service.list_entities(session=db, entity_type=entity_type, limit=1)
        assert result["entity_type"] == entity_type
        assert "items" in result


# --- describe_entity ---


def test_describe_profile_includes_nested_scripts_and_sets(
    db: Session, sample_profile: Profile
) -> None:
    result = service.describe_entity(
        session=db, entity_type="profile", name=sample_profile.name
    )
    scripts = result["children"]["scripts"]
    assert len(scripts) == 1
    assert scripts[0]["value"] == "shell"
    assert scripts[0]["sets"][0]["key"] == "priv-lvl"


def test_describe_ruleset_includes_nested_scripts_and_sets(
    db: Session, sample_ruleset: Ruleset
) -> None:
    result = service.describe_entity(
        session=db, entity_type="ruleset", name=sample_ruleset.name
    )
    scripts = result["children"]["scripts"]
    assert len(scripts) == 1
    assert scripts[0]["sets"][0]["value"] == "p1"


def test_describe_without_children(db: Session, sample_profile: Profile) -> None:
    result = service.describe_entity(
        session=db,
        entity_type="profile",
        name=sample_profile.name,
        include_children=False,
    )
    assert result["children"] == {}


def test_describe_unknown_name_raises(db: Session) -> None:
    with pytest.raises(LookupError, match="no-such-host"):
        service.describe_entity(session=db, entity_type="host", name="no-such-host")


# --- config generation ---


def test_generate_config_preview_redacts_by_default(
    db: Session, sample_host: Host
) -> None:
    result = service.generate_config_preview(session=db)
    assert result["redacted"] is True
    assert result["secrets_redacted"] >= 1
    assert sample_host.secret_key not in result["config"]
    assert result["line_count"] > 1
    assert result["byte_count"] == len(result["config"].encode("utf-8"))


def test_generate_config_preview_unredacted_contains_secret(
    db: Session, sample_host: Host
) -> None:
    result = service.generate_config_preview(session=db, redact_secrets=False)
    assert result["redacted"] is False
    assert result["secrets_redacted"] == 0
    assert sample_host.secret_key in result["config"]


def test_generate_every_declared_section(db: Session) -> None:
    for section in service.SECTIONS:
        result = service.generate_config_section(session=db, section=section)
        assert result["section"] == section
        assert isinstance(result["text"], str)


def test_generate_unknown_section_raises(db: Session) -> None:
    with pytest.raises(LookupError, match="nope"):
        service.generate_config_section(session=db, section="nope")


# --- saved configs ---


def test_list_saved_configs_shape(db: Session) -> None:
    result = service.list_saved_configs(session=db)
    assert result["count"] == len(result["items"])
    assert "active_filename" in result


def test_read_saved_config_rejects_traversal(db: Session) -> None:
    for bad in ("../etc/passwd", "sub/dir"):
        with pytest.raises(LookupError, match="Invalid filename"):
            service.read_saved_config(session=db, filename=bad)


def test_read_missing_saved_config_raises(db: Session) -> None:
    with pytest.raises(LookupError, match="no-such-config"):
        service.read_saved_config(session=db, filename="no-such-config")


def test_validate_saved_config_rejects_traversal() -> None:
    with pytest.raises(LookupError, match="Invalid filename"):
        service.validate_saved_config(filename="../x", timeout=5)


# --- diff ---


def test_diff_generated_vs_active_shape(db: Session) -> None:
    result = service.diff_generated_vs_active(session=db)
    assert set(result) >= {
        "diff",
        "changed",
        "added",
        "removed",
        "redacted",
        "active_config_exists",
    }
    assert isinstance(result["diff"], str)
    assert result["added"] >= 0
    assert result["removed"] >= 0


def test_read_active_config_text_when_absent(db: Session) -> None:
    text = service.read_active_config_text(session=db)
    assert isinstance(text, str)
    assert text


# --- settings ---


def test_get_tacacs_settings_or_raises(db: Session) -> None:
    try:
        settings_payload = service.get_tacacs_settings(session=db)
    except LookupError:
        pytest.skip("no TacacsNgSetting row seeded in this database")
    assert "ipv4_address" in settings_payload
    assert "ipv4_port" in settings_payload
