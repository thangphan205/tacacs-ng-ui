from typing import Any

from sqlmodel import Session, select
from app.models import (
    Mavis,
    MavisCreate,
    MavisUpdate,
)


def get_mavis_by_key(*, session: Session, mavis_key: str) -> Mavis | None:
    statement = select(Mavis).where(Mavis.mavis_key == mavis_key)
    session_mavis = session.exec(statement).first()
    return session_mavis


def create_mavis(*, session: Session, mavis_create: MavisCreate) -> Mavis:
    db_obj = Mavis.model_validate(mavis_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_mavis(*, session: Session, db_mavis: Mavis, mavis_in: MavisUpdate) -> Any:
    mavis_data = mavis_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_mavis.sqlmodel_update(mavis_data, update=extra_data)
    session.add(db_mavis)
    session.commit()
    session.refresh(db_mavis)
    return db_mavis
