from typing import Any

from sqlmodel import Session

from app.crud import ordering
from app.models import RulesetScript, RulesetScriptCreate, RulesetScriptUpdate


def _append_position(session: Session, parent_id: Any) -> int:
    return ordering.next_position(
        session=session,
        model=RulesetScript,
        parent_column=RulesetScript.ruleset_id,
        parent_id=parent_id,
    )


def create_rulesetscript(
    *, session: Session, rulesetscript_create: RulesetScriptCreate
) -> RulesetScript:
    data = rulesetscript_create.model_dump(exclude={"position"})
    data["position"] = _append_position(session, data["ruleset_id"])
    db_obj = RulesetScript.model_validate(data)
    session.add(db_obj)
    if rulesetscript_create.position is None:
        session.commit()
        session.refresh(db_obj)
        return db_obj
    # Insert and reorder in one transaction, so a refused position leaves no row.
    try:
        return move_rulesetscript(
            session=session,
            db_rulesetscript=db_obj,
            position=rulesetscript_create.position,
        )
    except ValueError:
        session.rollback()
        raise


def update_rulesetscript(
    *,
    session: Session,
    db_rulesetscript: RulesetScript,
    rulesetscript_in: RulesetScriptUpdate,
) -> Any:
    rulesetscript_data = rulesetscript_in.model_dump(exclude_unset=True)
    new_position = rulesetscript_data.pop("position", None)
    old_parent = db_rulesetscript.ruleset_id
    db_rulesetscript.sqlmodel_update(rulesetscript_data)
    if db_rulesetscript.ruleset_id != old_parent:
        # Moved to another ruleset: append there, close the gap it left behind.
        db_rulesetscript.position = _append_position(
            session, db_rulesetscript.ruleset_id
        )
        session.add(db_rulesetscript)
        session.flush()
        ordering.compact(
            session=session,
            model=RulesetScript,
            parent_column=RulesetScript.ruleset_id,
            parent_id=old_parent,
        )
    session.add(db_rulesetscript)
    if new_position is None or new_position == db_rulesetscript.position:
        session.commit()
        session.refresh(db_rulesetscript)
        return db_rulesetscript
    # Field changes and the move commit together, or not at all.
    try:
        return move_rulesetscript(
            session=session, db_rulesetscript=db_rulesetscript, position=new_position
        )
    except ValueError:
        session.rollback()
        raise


def move_rulesetscript(
    *, session: Session, db_rulesetscript: RulesetScript, position: int
) -> RulesetScript:
    """Reorder within the parent ruleset. Raises `ValueError` on a broken chain."""
    ordering.move(
        session=session,
        row=db_rulesetscript,
        model=RulesetScript,
        parent_column=RulesetScript.ruleset_id,
        parent_id=db_rulesetscript.ruleset_id,
        position=position,
        condition_attr="condition",
    )
    return db_rulesetscript


def delete_rulesetscript(*, session: Session, db_rulesetscript: RulesetScript) -> None:
    """Delete and renumber the siblings so positions stay 0..n-1."""
    parent_id = db_rulesetscript.ruleset_id
    session.delete(db_rulesetscript)
    session.flush()
    ordering.compact(
        session=session,
        model=RulesetScript,
        parent_column=RulesetScript.ruleset_id,
        parent_id=parent_id,
    )
    session.commit()
