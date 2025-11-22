import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.crud import rulesetscripts
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    RulesetScript,
    RulesetScriptCreate,
    RulesetScriptPublic,
    RulesetScriptsPublic,
    RulesetScriptUpdate,
    Ruleset,
)

router = APIRouter(prefix="/rulesetscripts", tags=["rulesetscripts"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetScriptsPublic,
)
def read_rulesetscripts(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve rulesetscripts.
    """

    count_statement = select(func.count()).select_from(RulesetScript)
    count = session.exec(count_statement).one()

    statement = select(RulesetScript, Ruleset).join(Ruleset).offset(skip).limit(limit)
    rulesetscripts = session.exec(statement).all()
    data_rulesetscripts = []
    for rulesetscript, ruleset in rulesetscripts:
        data_rulesetscript = RulesetScriptPublic.from_orm(rulesetscript)
        data_rulesetscript.ruleset_name = ruleset.name
        data_rulesetscripts.append(data_rulesetscript)
    return RulesetScriptsPublic(data=data_rulesetscripts, count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=RulesetScriptPublic,
)
def create_rulesetscript(
    *,
    session: SessionDep,
    rulesetscript_in: RulesetScriptCreate,
) -> Any:
    """
    Create new rulesetscript.
    """

    rulesetscript = rulesetscripts.create_rulesetscript(
        session=session, rulesetscript_create=rulesetscript_in
    )
    return rulesetscript


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetScriptPublic,
)
def read_rulesetscript_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific rulesetscript by id.
    """
    rulesetscript = session.get(RulesetScript, id)

    return rulesetscript


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=RulesetScriptPublic,
)
def update_rulesetscript(
    *,
    session: SessionDep,
    id: uuid.UUID,
    rulesetscript_in: RulesetScriptUpdate,
) -> Any:
    """
    Update a rulesetscript.
    """

    db_rulesetscript = session.get(RulesetScript, id)
    if not db_rulesetscript:
        raise HTTPException(
            status_code=404,
            detail="The rulesetscript with this id does not exist in the system",
        )
    db_rulesetscript = rulesetscripts.update_rulesetscript(
        session=session,
        db_rulesetscript=db_rulesetscript,
        rulesetscript_in=rulesetscript_in,
    )
    return db_rulesetscript


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_rulesetscript(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    rulesetscript = session.get(RulesetScript, id)
    if not rulesetscript:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(rulesetscript)
    session.commit()
    return Message(message="RulesetScript deleted successfully")
