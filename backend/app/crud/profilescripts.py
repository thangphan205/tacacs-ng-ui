from typing import Any

from sqlmodel import Session

from app.crud import ordering
from app.models import ProfileScript, ProfileScriptCreate, ProfileScriptUpdate


def _append_position(session: Session, parent_id: Any) -> int:
    return ordering.next_position(
        session=session,
        model=ProfileScript,
        parent_column=ProfileScript.profile_id,
        parent_id=parent_id,
    )


def create_profilescript(
    *, session: Session, profilescript_create: ProfileScriptCreate
) -> ProfileScript:
    data = profilescript_create.model_dump(exclude={"position"})
    data["position"] = _append_position(session, data["profile_id"])
    db_obj = ProfileScript.model_validate(data)
    session.add(db_obj)
    if profilescript_create.position is None:
        session.commit()
        session.refresh(db_obj)
        return db_obj
    # Insert and reorder in one transaction, so a refused position leaves no row.
    try:
        return move_profilescript(
            session=session,
            db_profilescript=db_obj,
            position=profilescript_create.position,
        )
    except ValueError:
        session.rollback()
        raise


def update_profilescript(
    *,
    session: Session,
    db_profilescript: ProfileScript,
    profilescript_in: ProfileScriptUpdate,
) -> Any:
    profilescript_data = profilescript_in.model_dump(exclude_unset=True)
    new_position = profilescript_data.pop("position", None)
    old_parent = db_profilescript.profile_id
    db_profilescript.sqlmodel_update(profilescript_data)
    if db_profilescript.profile_id != old_parent:
        # Moved to another profile: append there, close the gap it left behind.
        db_profilescript.position = _append_position(
            session, db_profilescript.profile_id
        )
        session.add(db_profilescript)
        session.flush()
        ordering.compact(
            session=session,
            model=ProfileScript,
            parent_column=ProfileScript.profile_id,
            parent_id=old_parent,
        )
    session.add(db_profilescript)
    if new_position is None or new_position == db_profilescript.position:
        session.commit()
        session.refresh(db_profilescript)
        return db_profilescript
    # Field changes and the move commit together, or not at all.
    try:
        return move_profilescript(
            session=session, db_profilescript=db_profilescript, position=new_position
        )
    except ValueError:
        session.rollback()
        raise


def move_profilescript(
    *, session: Session, db_profilescript: ProfileScript, position: int
) -> ProfileScript:
    """Reorder within the parent profile. Raises `ValueError` on a broken chain."""
    ordering.move(
        session=session,
        row=db_profilescript,
        model=ProfileScript,
        parent_column=ProfileScript.profile_id,
        parent_id=db_profilescript.profile_id,
        position=position,
        condition_attr="condition",
    )
    return db_profilescript


def delete_profilescript(*, session: Session, db_profilescript: ProfileScript) -> None:
    """Delete and renumber the siblings so positions stay 0..n-1."""
    parent_id = db_profilescript.profile_id
    session.delete(db_profilescript)
    session.flush()
    ordering.compact(
        session=session,
        model=ProfileScript,
        parent_column=ProfileScript.profile_id,
        parent_id=parent_id,
    )
    session.commit()
