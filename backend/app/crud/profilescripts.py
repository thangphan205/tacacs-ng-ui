from typing import Any

from sqlmodel import Session, select
from app.models import ProfileScript, ProfileScriptCreate, ProfileScriptUpdate


def create_profilescript(
    *, session: Session, profilescript_create: ProfileScriptCreate
) -> ProfileScript:
    db_obj = ProfileScript.model_validate(profilescript_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_profilescript(
    *,
    session: Session,
    db_profilescript: ProfileScript,
    profilescript_in: ProfileScriptUpdate
) -> Any:
    profilescript_data = profilescript_in.model_dump(exclude_unset=True)
    db_profilescript.sqlmodel_update(profilescript_data)
    session.add(db_profilescript)
    session.commit()
    session.refresh(db_profilescript)
    return db_profilescript
