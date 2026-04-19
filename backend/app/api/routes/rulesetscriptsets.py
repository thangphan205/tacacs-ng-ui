import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import func, select

from app.api.deps import (
    SessionDep,
    SuperUser,
    get_current_user,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import rulesetscriptsets
from app.models import (
    Message,
    Ruleset,
    RulesetScript,
    RulesetScriptSet,
    RulesetScriptSetCreate,
    RulesetScriptSetPublic,
    RulesetScriptSetsPublic,
    RulesetScriptSetUpdate,
)

router = APIRouter(prefix="/rulesetscriptsets", tags=["rulesetscriptsets"])

_SENSITIVE = audit_logs_crud._SENSITIVE


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
    response_model=RulesetScriptSetPublic,
)
def create_rulesetscriptset(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    rulesetscriptset_in: RulesetScriptSetCreate,
) -> Any:
    """
    Create new rulesetscriptset.
    """

    rulesetscriptset = rulesetscriptsets.create_rulesetscriptset(
        session=session, rulesetscriptset_create=rulesetscriptset_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="RulesetScriptSet",
        entity_id=str(rulesetscriptset.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        new_values=rulesetscriptset.model_dump_json(exclude=_SENSITIVE),
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
    response_model=RulesetScriptSetPublic,
)
def update_rulesetscriptset(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
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
    old_values = db_rulesetscriptset.model_dump_json(exclude=_SENSITIVE)
    db_rulesetscriptset = rulesetscriptsets.update_rulesetscriptset(
        session=session,
        db_rulesetscriptset=db_rulesetscriptset,
        rulesetscriptset_in=rulesetscriptset_in,
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="RulesetScriptSet",
        entity_id=str(db_rulesetscriptset.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_rulesetscriptset.model_dump_json(exclude=_SENSITIVE),
    )
    return db_rulesetscriptset


@router.delete(
    "/{id}",
)
def delete_rulesetscriptset(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a ruleset script set.
    """

    rulesetscriptset = session.get(RulesetScriptSet, id)
    if not rulesetscriptset:
        raise HTTPException(status_code=404, detail="RulesetScriptSet not found")

    old_values = rulesetscriptset.model_dump_json(exclude=_SENSITIVE)
    session.delete(rulesetscriptset)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="RulesetScriptSet",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="RulesetScriptSet deleted successfully")
