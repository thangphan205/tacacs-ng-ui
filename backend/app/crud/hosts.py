from typing import Any

from sqlmodel import Session, select
from app.models import Host, HostCreate, HostUpdate


def get_host_by_name(*, session: Session, name: str) -> Host | None:
    statement = select(Host).where(Host.name == name)
    session_host = session.exec(statement).first()
    return session_host


def create_host(*, session: Session, host_create: HostCreate) -> Host:
    db_obj = Host.model_validate(host_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_host(*, session: Session, db_host: Host, host_in: HostUpdate) -> Any:
    host_data = host_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_host.sqlmodel_update(host_data, update=extra_data)
    session.add(db_host)
    session.commit()
    session.refresh(db_host)
    return db_host
