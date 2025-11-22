from typing import Any

from sqlmodel import Session, select
from app.models import ProfileScriptSet, ProfileScriptSetCreate, ProfileScriptSetUpdate


def create_profilescriptset(
    *, session: Session, profilescriptset_create: ProfileScriptSetCreate
) -> ProfileScriptSet:
    db_obj = ProfileScriptSet.model_validate(profilescriptset_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_profilescriptset(
    *,
    session: Session,
    db_profilescriptset: ProfileScriptSet,
    profilescriptset_in: ProfileScriptSetUpdate
) -> Any:
    profilescriptset_data = profilescriptset_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_profilescriptset.sqlmodel_update(profilescriptset_data, update=extra_data)
    session.add(db_profilescriptset)
    session.commit()
    session.refresh(db_profilescriptset)
    return db_profilescriptset
