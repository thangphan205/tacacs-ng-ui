from typing import Any

from sqlmodel import Session, select
from app.models import TacacsService, TacacsServiceCreate, TacacsServiceUpdate


def get_tacacs_service_by_name(*, session: Session, name: str) -> TacacsService | None:
    statement = select(TacacsService).where(TacacsService.name == name)
    session_tacacs_service = session.exec(statement).first()
    return session_tacacs_service


def create_tacacs_service(
    *, session: Session, tacacs_service_create: TacacsServiceCreate
) -> TacacsService:
    db_obj = TacacsService.model_validate(tacacs_service_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_tacacs_service(
    *,
    session: Session,
    db_tacacs_service: TacacsService,
    tacacs_service_in: TacacsServiceUpdate
) -> Any:
    tacacs_service_data = tacacs_service_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_tacacs_service.sqlmodel_update(tacacs_service_data, update=extra_data)
    session.add(db_tacacs_service)
    session.commit()
    session.refresh(db_tacacs_service)
    return db_tacacs_service
