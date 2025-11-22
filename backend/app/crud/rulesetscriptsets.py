from typing import Any

from sqlmodel import Session, select
from app.models import RulesetScriptSet, RulesetScriptSetCreate, RulesetScriptSetUpdate


def create_rulesetscriptset(
    *, session: Session, rulesetscriptset_create: RulesetScriptSetCreate
) -> RulesetScriptSet:
    db_obj = RulesetScriptSet.model_validate(rulesetscriptset_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_rulesetscriptset(
    *,
    session: Session,
    db_rulesetscriptset: RulesetScriptSet,
    rulesetscriptset_in: RulesetScriptSetUpdate
) -> Any:
    rulesetscriptset_data = rulesetscriptset_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_rulesetscriptset.sqlmodel_update(rulesetscriptset_data, update=extra_data)
    session.add(db_rulesetscriptset)
    session.commit()
    session.refresh(db_rulesetscriptset)
    return db_rulesetscriptset
