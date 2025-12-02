from typing import Any

from sqlmodel import Session, select
from app.models import (
    ConfigurationOption,
    ConfigurationOptionCreate,
    ConfigurationOptionUpdate,
)


def get_configuration_option_by_name(
    *, session: Session, name: str
) -> ConfigurationOption | None:
    statement = select(ConfigurationOption).where(ConfigurationOption.name == name)
    session_configuration_option = session.exec(statement).first()
    return session_configuration_option


def create_configuration_option(
    *, session: Session, configuration_option_create: ConfigurationOptionCreate
) -> ConfigurationOption:
    db_obj = ConfigurationOption.model_validate(configuration_option_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_configuration_option(
    *,
    session: Session,
    db_configuration_option: ConfigurationOption,
    configuration_option_in: ConfigurationOptionUpdate
) -> Any:
    configuration_option_data = configuration_option_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_configuration_option.sqlmodel_update(
        configuration_option_data, update=extra_data
    )
    session.add(db_configuration_option)
    session.commit()
    session.refresh(db_configuration_option)
    return db_configuration_option
