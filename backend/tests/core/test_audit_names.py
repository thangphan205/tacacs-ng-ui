"""The entity name sent with a SIEM audit event, and nothing else from the values."""

import json

import pytest

from app.core.audit_names import entity_name


def j(**kw: object) -> str:
    return json.dumps(kw)


@pytest.mark.parametrize(
    ("entity_type", "values", "expected"),
    [
        ("User", {"email": "a@example.com"}, "a@example.com"),
        ("TacacsUser", {"username": "abc"}, "abc"),
        ("TacacsGroup", {"group_name": "noc"}, "noc"),
        ("Host", {"name": "core-sw"}, "core-sw"),
        ("TacacsService", {"name": "shell"}, "shell"),
        ("Profile", {"name": "p1"}, "p1"),
        ("Ruleset", {"name": "r1"}, "r1"),
        ("ConfigurationOption", {"name": "opt"}, "opt"),
        ("ApiKey", {"name": "ci"}, "ci"),
        ("Mavis", {"mavis_key": "LDAP_HOSTS"}, "LDAP_HOSTS"),
        ("StatsExcludedUser", {"pattern": "svc_*"}, "svc_*"),
        ("TacacsConfig", {"filename": "cfg-1.cfg"}, "cfg-1.cfg"),
        ("RulesetScript", {"key": "group", "value": "noc"}, "group=noc"),
        ("ProfileScriptSet", {"key": "priv-lvl", "value": "15"}, "priv-lvl=15"),
        ("ProfileScript", {"key": "service", "value": ""}, "service"),
    ],
)
def test_name_per_entity_type(
    entity_type: str, values: dict[str, object], expected: str
) -> None:
    assert entity_name(entity_type, None, json.dumps(values)) == (expected, None)


def test_delete_has_only_old_values() -> None:
    old = j(username="abc", password="$6$rounds=1$salt$hash")
    assert entity_name("TacacsUser", old, None) == ("abc", None)


def test_rename_reports_both_names() -> None:
    assert entity_name("Host", j(name="old"), j(name="new")) == ("new", "old")
    assert entity_name("Host", j(name="same"), j(name="same")) == ("same", None)


@pytest.mark.parametrize("entity_type", ["TacacsNgSetting", "SiemConfig", "Nope"])
def test_singletons_and_unknown_types_have_no_name(entity_type: str) -> None:
    assert entity_name(entity_type, None, j(name="x", enabled=True)) == (None, None)


@pytest.mark.parametrize("raw", [None, "", "not json", "[1, 2]", "null", '"s"'])
def test_bad_values_give_none(raw: str | None) -> None:
    assert entity_name("TacacsUser", raw, raw) == (None, None)


def test_missing_or_empty_field_gives_none() -> None:
    assert entity_name("TacacsUser", None, j(email="x@example.com")) == (None, None)
    assert entity_name("TacacsUser", None, j(username="")) == (None, None)


def test_long_name_is_cut() -> None:
    name, _ = entity_name("Host", None, j(name="h" * 500))
    assert name is not None and len(name) == 200
