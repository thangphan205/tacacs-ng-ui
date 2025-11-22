import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.crud import rulesetscriptsets
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    RulesetScriptSet,
    RulesetScriptSetCreate,
    RulesetScriptSetPublic,
    RulesetScriptSetsPublic,
    RulesetScriptSetUpdate,
    Ruleset,
    RulesetScript,
)

router = APIRouter(prefix="/rulesetscriptsets", tags=["rulesetscriptsets"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetScriptSetsPublic,
)
def read_rulesetscriptsets(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve rulesetscriptsets.
    """

    count_statement = select(func.count()).select_from(RulesetScriptSet)
    count = session.exec(count_statement).one()

    statement = (
        select(
            RulesetScriptSet,
            RulesetScript,
            Ruleset,
        )
        .join(
            RulesetScript,
            RulesetScriptSet.rulesetscript_id == RulesetScript.id,
        )
        .join(
            Ruleset,
            RulesetScript.ruleset_id == Ruleset.id,
        )
        .offset(skip)
        .limit(limit)
    )
    rulesetscriptsets = session.exec(statement).all()
    data_rulesetscriptsets = []
    for (
        rulesetscriptset,
        rulesetscript,
        ruleset,
    ) in rulesetscriptsets:
        data_rulesetscriptset = RulesetScriptSetPublic.from_orm(rulesetscriptset)
        data_rulesetscriptset.ruleset_id = rulesetscript.ruleset_id
        data_rulesetscriptset.ruleset_name = ruleset.name
        data_rulesetscriptset.rulesetscript_block = (
            rulesetscript.key + "==" + rulesetscript.value
        )
        data_rulesetscriptsets.append(data_rulesetscriptset)
    return RulesetScriptSetsPublic(data=data_rulesetscriptsets, count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=RulesetScriptSetPublic,
)
def create_rulesetscriptset(
    *,
    session: SessionDep,
    rulesetscriptset_in: RulesetScriptSetCreate,
) -> Any:
    """
    Create new rulesetscriptset.
    """

    rulesetscriptset = rulesetscriptsets.create_rulesetscriptset(
        session=session, rulesetscriptset_create=rulesetscriptset_in
    )
    return rulesetscriptset


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetScriptSetPublic,
)
def read_rulesetscriptset_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific rulesetscriptset by id.
    """

    rulesetscriptset = session.get(RulesetScriptSet, id)
    if not rulesetscriptset:
        raise HTTPException(status_code=404, detail="RulesetScriptSet not found")
    return rulesetscriptset


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=RulesetScriptSetPublic,
)
def update_rulesetscriptset(
    *,
    session: SessionDep,
    id: uuid.UUID,
    rulesetscriptset_in: RulesetScriptSetUpdate,
) -> Any:
    """
    Update a rulesetscriptset.
    """

    db_rulesetscriptset = session.get(RulesetScriptSet, id)
    if not db_rulesetscriptset:
        raise HTTPException(
            status_code=404,
            detail="The rulesetscriptset with this id does not exist in the system",
        )
    db_rulesetscriptset = rulesetscriptsets.update_rulesetscriptset(
        session=session,
        db_rulesetscriptset=db_rulesetscriptset,
        rulesetscriptset_in=rulesetscriptset_in,
    )
    return db_rulesetscriptset


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_rulesetscriptset(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    rulesetscriptset = session.get(RulesetScriptSet, id)
    if not rulesetscriptset:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(rulesetscriptset)
    session.commit()
    return Message(message="RulesetScriptSet deleted successfully")
