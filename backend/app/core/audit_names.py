"""The name of the object an audit entry is about, for the SIEM.

An audit row identifies its object by UUID only, and after a delete that id
resolves to nothing. The name is in the row's old/new values JSON, but those
values hold secrets (TacacsUser.password hash, Host.secret_key, Mavis values),
so they are never sent to a SIEM. Only this one derived value is.
"""

import json

_MAX_LEN = 200

# entity_type -> field holding its name. Singletons and unknown types have none.
_NAME_FIELD: dict[str, str] = {
    "User": "email",
    "TacacsUser": "username",
    "TacacsGroup": "group_name",
    "Host": "name",
    "TacacsService": "name",
    "Profile": "name",
    "Ruleset": "name",
    "ConfigurationOption": "name",
    "ApiKey": "name",
    "Mavis": "mavis_key",
    "StatsExcludedUser": "pattern",
    "TacacsConfig": "filename",
}
# Script rows have no name, only a key and a value (e.g. service=shell).
_KEY_VALUE_TYPES = frozenset(
    {"ProfileScript", "RulesetScript", "ProfileScriptSet", "RulesetScriptSet"}
)


def _name_from(entity_type: str, raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None
    if entity_type in _KEY_VALUE_TYPES:
        key, value = data.get("key"), data.get("value")
        if key in (None, ""):
            return None
        name = f"{key}={value}" if value not in (None, "") else str(key)
    else:
        field = _NAME_FIELD.get(entity_type)
        value = data.get(field) if field else None
        if value in (None, ""):
            return None
        name = str(value)
    return name[:_MAX_LEN]


def entity_name(
    entity_type: str, old_values: str | None, new_values: str | None
) -> tuple[str | None, str | None]:
    """``(name, renamed_from)`` for an audit entry.

    ``name`` is the current name, or the last one for a delete (only old
    values exist). ``renamed_from`` is the previous name when it changed.
    """
    old = _name_from(entity_type, old_values)
    new = _name_from(entity_type, new_values)
    name = new or old
    renamed_from = old if old and new and old != new else None
    return name, renamed_from
