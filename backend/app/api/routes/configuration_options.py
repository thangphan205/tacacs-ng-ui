import uuid
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.crud import configuration_options
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    ConfigurationOption,
    ConfigurationOptionCreate,
    ConfigurationOptionPublic,
    ConfigurationOptionsPublic,
    ConfigurationOptionUpdate,
)

router = APIRouter(prefix="/configuration_options", tags=["configuration_options"])


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
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ConfigurationOptionPublic,
)
def create_configuration_option(
    *, session: SessionDep, configuration_option_in: ConfigurationOptionCreate
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
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ConfigurationOptionPublic,
)
def update_configuration_option(
    *,
    session: SessionDep,
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

    db_configuration_option = configuration_options.update_configuration_option(
        session=session,
        db_configuration_option=db_configuration_option,
        configuration_option_in=configuration_option_in,
    )
    return db_configuration_option


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_configuration_option(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    configuration_option = session.get(ConfigurationOption, id)
    if not configuration_option:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(configuration_option)
    session.commit()
    return Message(message="ConfigurationOption deleted successfully")
