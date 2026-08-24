"""Entity mutations behind the MCP write tools.

Same shape as `service.py`: plain synchronous functions taking a `Session`, no
MCP machinery, directly unit-testable with the `db` fixture. `tools.py` handles
authorization, thread offloading and audit logging.

Scope of what this module may touch: **entity rows only**. It deliberately does
not import `create_tacacs_config`, `update_tacacs_config` or
`delete_tacacs_config` — generating a config file, activating one and reloading
the daemon stay a human action in the UI. `tests/mcp/test_no_config_writes.py`
enforces that.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError
from sqlmodel import Session, SQLModel, select

from app.crud import configuration_options as configuration_options_crud
from app.crud import hosts as hosts_crud
from app.crud import mavises as mavises_crud
from app.crud import profiles as profiles_crud
from app.crud import rulesets as rulesets_crud
from app.crud import tacacs_groups as tacacs_groups_crud
from app.crud import tacacs_services as tacacs_services_crud
from app.crud import tacacs_users as tacacs_users_crud
from app.crud.audit_logs import _SENSITIVE
from app.mcp_server.service import ENTITY_TYPES, _dump
from app.models import (
    ConfigurationOptionCreate,
    ConfigurationOptionUpdate,
    HostCreate,
    HostUpdate,
    MavisCreate,
    MavisUpdate,
    ProfileCreate,
    ProfileUpdate,
    RulesetCreate,
    RulesetUpdate,
    TacacsGroupCreate,
    TacacsGroupUpdate,
    TacacsServiceCreate,
    TacacsServiceUpdate,
    TacacsUserCreate,
    TacacsUserUpdate,
)

# Fields kept out of audit payloads. A plain set, not the frozenset itself:
# pydantic's `exclude` is typed `IncEx`, which does not accept a frozenset.
_AUDIT_EXCLUDE = set(_SENSITIVE)


@dataclass(frozen=True)
class WriteSpec:
    """How one entity type is created and updated.

    The CRUD layer names its keyword arguments differently per entity
    (`user_create=` / `db_user=` vs `tacacs_service_create=` /
    `db_tacacs_service=`), so each spec adapts them to one signature.
    """

    create_dto: type[SQLModel]
    update_dto: type[SQLModel]
    create: Callable[[Session, Any], SQLModel]
    update: Callable[[Session, Any, Any], SQLModel]
    audit_type: str


WRITABLE: dict[str, WriteSpec] = {
    "host": WriteSpec(
        create_dto=HostCreate,
        update_dto=HostUpdate,
        create=lambda s, dto: hosts_crud.create_host(session=s, host_create=dto),
        update=lambda s, row, dto: hosts_crud.update_host(
            session=s, db_host=row, host_in=dto
        ),
        audit_type="Host",
    ),
    "user": WriteSpec(
        create_dto=TacacsUserCreate,
        update_dto=TacacsUserUpdate,
        create=lambda s, dto: tacacs_users_crud.create_tacacs_user(
            session=s, user_create=dto
        ),
        update=lambda s, row, dto: tacacs_users_crud.update_tacacs_user(
            session=s, db_user=row, user_in=dto
        ),
        audit_type="TacacsUser",
    ),
    "group": WriteSpec(
        create_dto=TacacsGroupCreate,
        update_dto=TacacsGroupUpdate,
        create=lambda s, dto: tacacs_groups_crud.create_tacacs_group(
            session=s, group_create=dto
        ),
        update=lambda s, row, dto: tacacs_groups_crud.update_tacacs_group(
            session=s, db_tacacs_group=row, group_in=dto
        ),
        audit_type="TacacsGroup",
    ),
    "profile": WriteSpec(
        create_dto=ProfileCreate,
        update_dto=ProfileUpdate,
        create=lambda s, dto: profiles_crud.create_profile(
            session=s, profile_create=dto
        ),
        update=lambda s, row, dto: profiles_crud.update_profile(
            session=s, db_profile=row, profile_in=dto
        ),
        audit_type="Profile",
    ),
    "ruleset": WriteSpec(
        create_dto=RulesetCreate,
        update_dto=RulesetUpdate,
        create=lambda s, dto: rulesets_crud.create_ruleset(
            session=s, ruleset_create=dto
        ),
        update=lambda s, row, dto: rulesets_crud.update_ruleset(
            session=s, db_ruleset=row, ruleset_in=dto
        ),
        audit_type="Ruleset",
    ),
    "mavis": WriteSpec(
        create_dto=MavisCreate,
        update_dto=MavisUpdate,
        create=lambda s, dto: mavises_crud.create_mavis(session=s, mavis_create=dto),
        update=lambda s, row, dto: mavises_crud.update_mavis(
            session=s, db_mavis=row, mavis_in=dto
        ),
        audit_type="Mavis",
    ),
    "configuration_option": WriteSpec(
        create_dto=ConfigurationOptionCreate,
        update_dto=ConfigurationOptionUpdate,
        create=lambda s, dto: configuration_options_crud.create_configuration_option(
            session=s, configuration_option_create=dto
        ),
        update=lambda s, row, dto: (
            configuration_options_crud.update_configuration_option(
                session=s, db_configuration_option=row, configuration_option_in=dto
            )
        ),
        audit_type="ConfigurationOption",
    ),
    "tacacs_service": WriteSpec(
        create_dto=TacacsServiceCreate,
        update_dto=TacacsServiceUpdate,
        create=lambda s, dto: tacacs_services_crud.create_tacacs_service(
            session=s, tacacs_service_create=dto
        ),
        update=lambda s, row, dto: tacacs_services_crud.update_tacacs_service(
            session=s, db_tacacs_service=row, tacacs_service_in=dto
        ),
        audit_type="TacacsService",
    ),
}


@dataclass(frozen=True)
class WriteResult:
    """Everything `tools.py` needs to answer the client and write an audit row."""

    entity_type: str
    audit_type: str
    entity_id: str | None
    item: dict[str, Any] | None
    old_values: str | None = None
    new_values: str | None = None


def _spec(entity_type: str) -> WriteSpec:
    spec = WRITABLE.get(entity_type)
    if spec is None:
        raise LookupError(
            f"Entity type '{entity_type}' is not writable over MCP. "
            f"Writable: {', '.join(sorted(WRITABLE))}."
        )
    return spec


def _find(session: Session, entity_type: str, name: str) -> SQLModel | None:
    model, name_field = ENTITY_TYPES[entity_type]
    return session.exec(select(model).where(getattr(model, name_field) == name)).first()


def _validate(dto: type[SQLModel], data: dict[str, Any]) -> Any:
    """Turn a client-supplied dict into a DTO, reporting errors readably.

    A raw pydantic traceback is noise to an LLM client; a flat "field: message"
    list is something it can act on.
    """
    try:
        return dto.model_validate(data)
    except ValidationError as e:
        problems = "; ".join(
            f"{'.'.join(str(p) for p in err['loc']) or '(body)'}: {err['msg']}"
            for err in e.errors()
        )
        raise ValueError(f"Invalid {dto.__name__} payload — {problems}") from e


def create_entity(
    *, session: Session, entity_type: str, data: dict[str, Any]
) -> WriteResult:
    spec = _spec(entity_type)
    _, name_field = ENTITY_TYPES[entity_type]

    dto = _validate(spec.create_dto, data)

    name = getattr(dto, name_field, None)
    if name is not None and _find(session, entity_type, name) is not None:
        raise ValueError(f"A {entity_type} named '{name}' already exists.")

    row = spec.create(session, dto)
    return WriteResult(
        entity_type=entity_type,
        audit_type=spec.audit_type,
        entity_id=str(row.id),  # type: ignore[attr-defined]
        item=_dump(entity_type, row),
        new_values=row.model_dump_json(exclude=_AUDIT_EXCLUDE),
    )


def update_entity(
    *, session: Session, entity_type: str, name: str, data: dict[str, Any]
) -> WriteResult:
    spec = _spec(entity_type)
    _, name_field = ENTITY_TYPES[entity_type]

    row = _find(session, entity_type, name)
    if row is None:
        raise LookupError(f"No {entity_type} named '{name}'.")

    new_name = data.get(name_field)
    if new_name is not None and new_name != name:
        clash = _find(session, entity_type, new_name)
        if clash is not None:
            raise ValueError(f"A {entity_type} named '{new_name}' already exists.")

    # Most *Update DTOs inherit *Base, so every field is required and a partial
    # payload would fail validation. Seed the payload from the current row so an
    # MCP client can send only the fields it means to change.
    current = row.model_dump()
    merged = {
        **{k: v for k, v in current.items() if k in spec.update_dto.model_fields},
        **data,
    }
    dto = _validate(spec.update_dto, merged)

    old_values = row.model_dump_json(exclude=_AUDIT_EXCLUDE)
    updated = spec.update(session, row, dto)
    return WriteResult(
        entity_type=entity_type,
        audit_type=spec.audit_type,
        entity_id=str(updated.id),  # type: ignore[attr-defined]
        item=_dump(entity_type, updated),
        old_values=old_values,
        new_values=updated.model_dump_json(exclude=_AUDIT_EXCLUDE),
    )


def delete_entity(*, session: Session, entity_type: str, name: str) -> WriteResult:
    spec = _spec(entity_type)

    row = _find(session, entity_type, name)
    if row is None:
        raise LookupError(f"No {entity_type} named '{name}'.")

    entity_id = str(row.id)  # type: ignore[attr-defined]
    old_values = row.model_dump_json(exclude=_AUDIT_EXCLUDE)
    session.delete(row)
    session.commit()
    return WriteResult(
        entity_type=entity_type,
        audit_type=spec.audit_type,
        entity_id=entity_id,
        item=None,
        old_values=old_values,
    )
