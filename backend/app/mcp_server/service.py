"""Database work behind the MCP tools.

Plain synchronous functions taking a Session, so they are directly unit-testable
with the existing `db` fixture and carry no MCP machinery. `tools.py` handles
authorization and thread offloading.

Nothing here mutates the database, the config directory, or the daemon.
"""

import difflib
import os
from typing import Any

from sqlmodel import Session, SQLModel, func, select

from app.crud import profiles as profiles_crud
from app.crud import rulesets as rulesets_crud
from app.crud import tacacs_configs as tacacs_configs_crud
from app.mcp_server.redact import collect_secrets, redact_config_text
from app.models import (
    ConfigurationOption,
    Host,
    Mavis,
    Profile,
    ProfileScript,
    ProfileScriptSet,
    Ruleset,
    RulesetScript,
    RulesetScriptSet,
    TacacsConfig,
    TacacsGroup,
    TacacsNgSetting,
    TacacsService,
    TacacsUser,
)

# entity_type -> (model, name field)
ENTITY_TYPES: dict[str, tuple[type[SQLModel], str]] = {
    "host": (Host, "name"),
    "user": (TacacsUser, "username"),
    "group": (TacacsGroup, "group_name"),
    "profile": (Profile, "name"),
    "ruleset": (Ruleset, "name"),
    "mavis": (Mavis, "mavis_key"),
    "configuration_option": (ConfigurationOption, "name"),
    "tacacs_service": (TacacsService, "name"),
}

# Fields never returned to an MCP client, per entity type.
_ENTITY_SECRET_FIELDS: dict[str, frozenset[str]] = {
    "host": frozenset({"secret_key"}),
    "user": frozenset({"password"}),
    "mavis": frozenset({"mavis_value"}),
}

SECTIONS = ("mavis", "profiles", "rulesets")


def _dump(entity_type: str, row: SQLModel) -> dict[str, Any]:
    data = row.model_dump(mode="json")
    for field in _ENTITY_SECRET_FIELDS.get(entity_type, frozenset()):
        if data.get(field):
            data[field] = "***REDACTED***"
    return data


def list_entities(
    *,
    session: Session,
    entity_type: str,
    search: str | None = None,
    limit: int = 100,
    offset: int = 0,
    only_generated: bool | None = None,
) -> dict[str, Any]:
    model, name_field = ENTITY_TYPES[entity_type]

    statement = select(model)
    count_statement = select(func.count()).select_from(model)

    if search:
        f = getattr(model, name_field).ilike(f"%{search}%")
        statement = statement.where(f)
        count_statement = count_statement.where(f)

    if only_generated is not None and "generate_config" in model.model_fields:
        f = model.generate_config == only_generated  # type: ignore[attr-defined]
        statement = statement.where(f)
        count_statement = count_statement.where(f)

    total = session.exec(count_statement).one()
    rows = session.exec(statement.offset(offset).limit(limit)).all()

    items = [_dump(entity_type, row) for row in rows]
    return {
        "entity_type": entity_type,
        "count": len(items),
        "total": total,
        "items": items,
    }


def describe_entity(
    *,
    session: Session,
    entity_type: str,
    name: str,
    include_children: bool = True,
) -> dict[str, Any]:
    model, name_field = ENTITY_TYPES[entity_type]
    row = session.exec(select(model).where(getattr(model, name_field) == name)).first()
    if row is None:
        raise LookupError(f"No {entity_type} named '{name}'.")

    result: dict[str, Any] = {
        "entity_type": entity_type,
        "item": _dump(entity_type, row),
        "children": {},
    }

    if not include_children:
        return result

    row_id = row.id  # type: ignore[attr-defined]

    if entity_type == "profile":
        result["children"]["scripts"] = [
            {
                **script.model_dump(mode="json"),
                "sets": [
                    s.model_dump(mode="json")
                    for s in session.exec(
                        select(ProfileScriptSet).where(
                            ProfileScriptSet.profilescript_id == script.id
                        )
                    ).all()
                ],
            }
            for script in session.exec(
                select(ProfileScript).where(ProfileScript.profile_id == row_id)
            ).all()
        ]
    elif entity_type == "ruleset":
        result["children"]["scripts"] = [
            {
                **script.model_dump(mode="json"),
                "sets": [
                    s.model_dump(mode="json")
                    for s in session.exec(
                        select(RulesetScriptSet).where(
                            RulesetScriptSet.rulesetscript_id == script.id
                        )
                    ).all()
                ],
            }
            for script in session.exec(
                select(RulesetScript).where(RulesetScript.ruleset_id == row_id)
            ).all()
        ]

    return result


def get_tacacs_settings(*, session: Session) -> dict[str, Any]:
    row = session.exec(select(TacacsNgSetting).limit(1)).first()
    if row is None:
        raise LookupError("No TACACS NG settings row exists yet.")
    return row.model_dump(mode="json")


def _redact(session: Session, text: str) -> tuple[str, int]:
    return redact_config_text(text, secrets=collect_secrets(session=session))


def _wrap_config(session: Session, text: str, redact: bool) -> dict[str, Any]:
    secrets_redacted = 0
    if redact:
        text, secrets_redacted = _redact(session, text)
    return {
        "config": text,
        "redacted": redact,
        "secrets_redacted": secrets_redacted,
        "line_count": text.count("\n") + 1,
        "byte_count": len(text.encode("utf-8")),
    }


def generate_config_preview(
    *, session: Session, redact_secrets: bool = True
) -> dict[str, Any]:
    text = tacacs_configs_crud.generate_tacacs_ng_config(session=session)
    return _wrap_config(session, text, redact_secrets)


def generate_config_section(
    *, session: Session, section: str, redact_secrets: bool = True
) -> dict[str, Any]:
    if section == "mavis":
        text = tacacs_configs_crud.generate_tacacs_mavis_setting(session=session)
    elif section == "profiles":
        text = profiles_crud.profile_generator(session=session)
    elif section == "rulesets":
        text = rulesets_crud.ruleset_generator(session=session)
    else:
        raise LookupError(
            f"Unknown section '{section}'. Available: {', '.join(SECTIONS)}."
        )

    secrets_redacted = 0
    if redact_secrets:
        text, secrets_redacted = _redact(session, text)
    return {
        "section": section,
        "text": text,
        "redacted": redact_secrets,
        "secrets_redacted": secrets_redacted,
    }


def validate_config_text(*, text: str, timeout: int) -> dict[str, Any]:
    return tacacs_configs_crud.validate_config_text(text=text, timeout=timeout)


def validate_generated_config(*, session: Session, timeout: int) -> dict[str, Any]:
    """Validate the real, unredacted config without any secret leaving the server."""
    text = tacacs_configs_crud.generate_tacacs_ng_config(session=session)
    result = tacacs_configs_crud.validate_config_text(text=text, timeout=timeout)
    result["validated"] = "generated-from-database"
    return result


def list_saved_configs(*, session: Session) -> dict[str, Any]:
    rows = session.exec(select(TacacsConfig)).all()
    active = next((r.filename for r in rows if r.active), None)
    return {
        "count": len(rows),
        "active_filename": active,
        "items": [
            {
                "id": str(r.id),
                "filename": r.filename,
                "description": r.description,
                "active": r.active,
                "created_at": r.created_at.isoformat(),
                "updated_at": r.updated_at.isoformat(),
            }
            for r in rows
        ],
    }


def _saved_config_path(filename: str) -> str:
    """Resolve a saved config filename to a path inside CONFIG_PATH.

    Rejects anything that could escape the directory, then confirms the file
    exists so callers get one consistent error instead of an OSError.
    """
    if ".." in filename or "/" in filename:
        raise LookupError("Invalid filename.")
    path = os.path.join(tacacs_configs_crud.CONFIG_PATH, f"{filename}.cfg")
    if not os.path.exists(path):
        raise LookupError(f"No saved config named '{filename}'.")
    return path


def read_saved_config(
    *, session: Session, filename: str, redact_secrets: bool = True
) -> dict[str, Any]:
    with open(_saved_config_path(filename), encoding="utf-8") as f:
        text = f.read()

    secrets_redacted = 0
    if redact_secrets:
        text, secrets_redacted = _redact(session, text)
    return {
        "filename": filename,
        "data": text,
        "redacted": redact_secrets,
        "secrets_redacted": secrets_redacted,
    }


def validate_saved_config(*, filename: str, timeout: int) -> dict[str, Any]:
    path = _saved_config_path(filename)
    return tacacs_configs_crud._run_syntax_check(
        config_file_path=path, filename=f"{filename}.cfg", timeout=timeout
    )


def read_active_config_text(*, session: Session, redact_secrets: bool = True) -> str:
    """The live tac_plus-ng.cfg as text, redacted by default."""
    path = tacacs_configs_crud.CONFIG_FILE_PATH
    if not os.path.exists(path):
        return "No active config file is present on this node."
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if redact_secrets:
        text, _ = _redact(session, text)
    return text


def diff_generated_vs_active(
    *, session: Session, redact_secrets: bool = True
) -> dict[str, Any]:
    generated = tacacs_configs_crud.generate_tacacs_ng_config(session=session)

    active_path = tacacs_configs_crud.CONFIG_FILE_PATH
    if os.path.exists(active_path):
        with open(active_path, encoding="utf-8") as f:
            active = f.read()
    else:
        active = ""

    if redact_secrets:
        generated, _ = _redact(session, generated)
        active, _ = _redact(session, active)

    diff_lines = list(
        difflib.unified_diff(
            active.splitlines(keepends=True),
            generated.splitlines(keepends=True),
            fromfile="active/tac_plus-ng.cfg",
            tofile="generated-from-database",
        )
    )
    added = sum(1 for line in diff_lines if line.startswith("+") and line[:3] != "+++")
    removed = sum(
        1 for line in diff_lines if line.startswith("-") and line[:3] != "---"
    )

    return {
        "diff": "".join(diff_lines),
        "changed": bool(diff_lines),
        "added": added,
        "removed": removed,
        "redacted": redact_secrets,
        "active_config_exists": os.path.exists(active_path),
    }
