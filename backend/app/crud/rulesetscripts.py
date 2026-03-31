from typing import Any

from sqlmodel import Session, select
from app.models import RulesetScript, RulesetScriptCreate, RulesetScriptUpdate


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
    db_rulesetscript.sqlmodel_update(rulesetscript_data)
    session.add(db_rulesetscript)
    session.commit()
    session.refresh(db_rulesetscript)
    return db_rulesetscript
