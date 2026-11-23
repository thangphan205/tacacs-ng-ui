"""Names and actions written unquoted into the tac_plus-ng config (#442).

The generator writes these as bare tokens:

    user <username> {            member = <group>[,<group>...]
    group = <group_name>         host = <name> {    parent = <name>
    rule <ruleset name> {        <action>   (profile / ruleset / script)

Two rules, verified against the binary (`tac_plus-ng -P`), not guessed:

* **Entry** (`check_config_name`, `normalize_member`, `check_action`): what the
  API and MCP accept for a new value. Refuses whitespace, braces, quotes, `#`,
  `\\` and `= , ( ) !`. Whitespace and braces end the token and let the rest
  add config; a leading quote opens a string that swallows the config lines
  after it; a leading `#` comments the rest of the line out; `= , ( ) !` make
  the config fail the syntax check. Quotes, `#` and `\\` *inside* a name parse
  as part of it (`o'brien`, `DOMAIN\\user` work today), but they are refused
  for new values like profile names are (`core/raw_script.check_profile_name`).
  An update applies the rule only when the value changes, so a row that works
  today stays editable.

* **Render** (`renderable_name`, `render_*`): what the generator still writes
  from a stored row. Only what can change the config's structure is dropped:
  whitespace,
  braces, or a leading quote or `#`. Such a value already made the config fail
  the syntax check, so no working install has one. Hosts, groups and users
  with one are left out (fail closed: nobody gains access); a rule keeps its
  place under a substitute label, and an unsafe action becomes `deny`.

Pure functions with no app imports, so `models.py` can use them in validators.
"""

import logging
import re
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

_UNSAFE_NAME = re.compile(r"""[\s{}"'#\\=,()!]""")
_UNRENDERABLE = re.compile(r"""[\s{}]|^["'#]""")
_ACTION = re.compile(r"[A-Za-z0-9_-]+\Z")


def check_config_name(value: str, what: str) -> str:
    """Return `value`, or raise `ValueError` naming `what`."""
    if not value or _UNSAFE_NAME.search(value):
        raise ValueError(
            f"{what} can't be empty or contain whitespace, braces, quotes, "
            "'#', '\\', '=', ',', '(', ')' or '!'."
        )
    return value


def normalize_member(value: str) -> str:
    """A comma-separated group list, spaces around commas removed. Each group
    name must pass `check_config_name`. Raises `ValueError`."""
    groups = [g.strip() for g in value.split(",")]
    for group in groups:
        check_config_name(group, "Each group in Group Membership")
    return ",".join(groups)


def check_action(value: str, what: str) -> str:
    """An action is one bare word (`permit`, `deny`). Raises `ValueError`."""
    if not _ACTION.match(value or ""):
        raise ValueError(f"{what} must be a single word such as permit or deny.")
    return value


def renderable_name(value: str | None) -> bool:
    return bool(value) and not _UNRENDERABLE.search(value or "")


def render_member(value: str | None) -> str | None:
    """The stored group list as the generator writes it (spaces around commas
    removed, which tac_plus-ng ignores anyway), or None when a group in it
    could change the config's structure."""
    groups = [g.strip() for g in (value or "").split(",")]
    if not all(renderable_name(g) for g in groups):
        return None
    return ",".join(groups)


def render_action(value: str | None, where: str) -> str:
    """The stored action as the generator writes it. An action that is not one
    bare word becomes `deny`: dropping it, or the rule around it, could let a
    request through that the admin meant to stop."""
    if _ACTION.match(value or ""):
        return value  # type: ignore[return-value]
    log.error("Writing deny for the unsafe action %r of %s", value, where)
    return "deny"


def render_rule_name(name: str, row_id: object) -> str:
    """A ruleset's label as the generator writes it. Nothing refers to a rule
    by name, so an unsafe stored name is replaced rather than the rule
    dropped, which could let requests through."""
    if renderable_name(name):
        return name
    log.error("Writing rule %r as ruleset_%s: unsafe name", name, row_id)
    return f"ruleset_{row_id}"


def check_changed(
    data: dict[str, Any], stored: object, checks: dict[str, Callable[[str], str]]
) -> None:
    """Apply each entry check to the fields of a partial update that change.

    A row stored before these checks (a working `o'brien` user) stays
    editable: an update that resends its unchanged name is not refused. The
    checked (normalized) value replaces the sent one. Raises `ValueError`.
    """
    for field, check in checks.items():
        value = data.get(field)
        if value is not None and value != getattr(stored, field):
            data[field] = check(value)


def name_check(what: str) -> Callable[[str], str]:
    return lambda value: check_config_name(value, what)


def action_check(what: str) -> Callable[[str], str]:
    return lambda value: check_action(value, what)
