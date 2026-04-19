import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import func, select

from app.api.deps import (
    SessionDep,
    SuperUser,
    get_current_user,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import configuration_options
from app.models import (
    ConfigurationOption,
    ConfigurationOptionCreate,
    ConfigurationOptionPublic,
    ConfigurationOptionsPublic,
    ConfigurationOptionUpdate,
    Message,
)

router = APIRouter(prefix="/configuration_options", tags=["configuration_options"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=ConfigurationOptionsPublic,
)
def read_configuration_options(
    session: SessionDep, skip: int = 0, limit: int = 100
) -> Any:
    """
    Retrieve configuration_options.
    """

    count_statement = select(func.count()).select_from(ConfigurationOption)
    count = session.exec(count_statement).one()

    statement = select(ConfigurationOption).offset(skip).limit(limit)
    configuration_options = session.exec(statement).all()

    return ConfigurationOptionsPublic(data=configuration_options, count=count)


@router.post(
    "/",
    response_model=ConfigurationOptionPublic,
)
def create_configuration_option(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    configuration_option_in: ConfigurationOptionCreate,
) -> Any:
    """
    Create new configuration_option.
    """
    configuration_option = configuration_options.get_configuration_option_by_name(
        session=session, name=configuration_option_in.name
    )
    if configuration_option:
        raise HTTPException(
            status_code=400,
            detail="The configuration_option with this configuration_option name already exists in the system.",
        )

    configuration_option = configuration_options.create_configuration_option(
        session=session, configuration_option_create=configuration_option_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="ConfigurationOption",
        entity_id=str(configuration_option.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        new_values=configuration_option.model_dump_json(exclude=_SENSITIVE),
    )
    return configuration_option


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_user)],
    response_model=ConfigurationOptionPublic,
)
def read_configuration_option_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific configuration_option by id.
    """
    configuration_option = session.get(ConfigurationOption, id)
    if not configuration_option:
        raise HTTPException(status_code=404, detail="ConfigurationOption not found")
    return configuration_option


@router.put(
    "/{id}",
    response_model=ConfigurationOptionPublic,
)
def update_configuration_option(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    configuration_option_in: ConfigurationOptionUpdate,
) -> Any:
    """
    Update a configuration_option.
    """

    db_configuration_option = session.get(ConfigurationOption, id)
    if not db_configuration_option:
        raise HTTPException(
            status_code=404,
            detail="The configuration_option with this id does not exist in the system",
        )

    old_values = db_configuration_option.model_dump_json(exclude=_SENSITIVE)
    db_configuration_option = configuration_options.update_configuration_option(
        session=session,
        db_configuration_option=db_configuration_option,
        configuration_option_in=configuration_option_in,
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="ConfigurationOption",
        entity_id=str(db_configuration_option.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_configuration_option.model_dump_json(exclude=_SENSITIVE),
    )
    return db_configuration_option


@router.delete(
    "/{id}",
)
def delete_configuration_option(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a configuration option.
    """

    configuration_option = session.get(ConfigurationOption, id)
    if not configuration_option:
        raise HTTPException(status_code=404, detail="ConfigurationOption not found")

    old_values = configuration_option.model_dump_json(exclude=_SENSITIVE)
    session.delete(configuration_option)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="ConfigurationOption",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="ConfigurationOption deleted successfully")
