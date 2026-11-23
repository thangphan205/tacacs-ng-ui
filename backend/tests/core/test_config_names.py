"""The rules for names and actions written unquoted into the config (#442)."""

import pytest

from app.core.config_names import (
    check_action,
    check_changed,
    check_config_name,
    name_check,
    normalize_member,
    render_action,
    render_member,
    render_rule_name,
    renderable_name,
)

# Each refused for a new value. The binary rejects the first group anywhere in
# a name; the second parses inside a name but not at its start.
STRUCTURE = [" ", "\t", "\n", "{", "}", "=", ",", "(", ")", "!"]
QUOTING = ['"', "'", "#", "\\"]


@pytest.mark.parametrize("ch", STRUCTURE + QUOTING)
def test_entry_refuses_characters_that_end_or_open_a_token(ch: str) -> None:
    for name in (f"a{ch}b", f"{ch}ab", f"ab{ch}"):
        with pytest.raises(ValueError, match="Host name"):
            check_config_name(name, "Host name")


@pytest.mark.parametrize(
    "name", ["core-sw01", "user_admin", "alice@example.com", "10.0.0.1", "a:b/c$d"]
)
def test_entry_accepts_ordinary_names(name: str) -> None:
    assert check_config_name(name, "Username") == name


def test_entry_refuses_an_empty_name() -> None:
    with pytest.raises(ValueError):
        check_config_name("", "Group name")


def test_member_is_a_comma_list_of_safe_names() -> None:
    assert normalize_member("g1, g2 ,g3") == "g1,g2,g3"
    for bad in ("g1,", "g1,,g2", "g1, g 2", "g1}", 'g1,"g2'):
        with pytest.raises(ValueError, match="Group Membership"):
            normalize_member(bad)


@pytest.mark.parametrize("action", ["permit", "deny"])
def test_actions_are_one_word(action: str) -> None:
    assert check_action(action, "Script action") == action
    for bad in ("", "permit }", "deny\n}", "permit;deny", "#"):
        with pytest.raises(ValueError, match="Script action"):
            check_action(bad, "Script action")


def test_render_keeps_names_that_parse_today() -> None:
    """Quotes, `#` and `\\` inside a name parse as part of it
    (`tac_plus-ng -P`), so stored rows like these keep working."""
    for name in ("o'brien", "DOMAIN\\user", 'a"b', "a#b", "ab\\"):
        assert renderable_name(name)


@pytest.mark.parametrize("name", ["a b", "a\nb", "a{b", "a}b", '"a', "'a", "#a", ""])
def test_render_drops_names_that_change_the_structure(name: str) -> None:
    assert not renderable_name(name)


def test_render_member_strips_spaces_and_drops_unsafe_lists() -> None:
    assert render_member("g1, g2") == "g1,g2"
    assert render_member("g1,o'brien") == "g1,o'brien"
    assert render_member("g1 } user evil { member = g1") is None
    assert render_member("g1,#g2") is None


def test_render_fails_closed() -> None:
    """An unsafe action becomes deny, and a rule keeps its place."""
    assert render_action("permit", "x") == "permit"
    assert render_action("permit }\n} user evil {", "x") == "deny"
    assert render_rule_name("rule-1", "abc") == "rule-1"
    assert render_rule_name("r } x {", "abc") == "ruleset_abc"


class _Row:
    name = "o'brien"
    parent = None


def test_check_changed_only_checks_values_that_change() -> None:
    checks = {"name": name_check("Host name"), "parent": name_check("Parent host")}
    data = {"name": "o'brien", "parent": None}
    check_changed(data, _Row(), checks)  # unchanged legacy name: accepted
    with pytest.raises(ValueError, match="Host name"):
        check_changed({"name": "x y"}, _Row(), checks)
    with pytest.raises(ValueError, match="Parent host"):
        check_changed({"parent": "p q"}, _Row(), checks)
    normalized = {"member": "g1, g2"}

    class _User:
        member = "g1"

    check_changed(normalized, _User(), {"member": normalize_member})
    assert normalized["member"] == "g1,g2"
