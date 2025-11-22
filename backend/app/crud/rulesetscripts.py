from typing import Any

from sqlmodel import Session, select
from app.models import RulesetScript, RulesetScriptCreate, RulesetScriptUpdate


def get_rulesetscript_by_name(*, session: Session, name: str) -> RulesetScript | None:
    statement = select(RulesetScript).where(RulesetScript.name == name)
    session_rulesetscript = session.exec(statement).first()
    return session_rulesetscript


def create_rulesetscript(
    *, session: Session, rulesetscript_create: RulesetScriptCreate
) -> RulesetScript:
    db_obj = RulesetScript.model_validate(rulesetscript_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_rulesetscript(
    *,
    session: Session,
    db_rulesetscript: RulesetScript,
    rulesetscript_in: RulesetScriptUpdate
) -> Any:
    rulesetscript_data = rulesetscript_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_rulesetscript.sqlmodel_update(rulesetscript_data, update=extra_data)
    session.add(db_rulesetscript)
    session.commit()
    session.refresh(db_rulesetscript)
    return db_rulesetscript
