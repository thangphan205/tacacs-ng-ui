import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import func, select

from app.api.deps import (
    SessionDep,
    SuperUser,
    get_client_ip,
    get_current_user,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud.ordering import order_columns
from app.crud import rulesetscripts
from app.models import (
    Message,
    Ruleset,
    RulesetScript,
    RulesetScriptCreate,
    PositionMove,
    RulesetScriptPublic,
    RulesetScriptsPublic,
    RulesetScriptUpdate,
)

router = APIRouter(prefix="/rulesetscripts", tags=["rulesetscripts"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetScriptsPublic,
)
def read_rulesetscripts(
    session: SessionDep, skip: int = 0, limit: int = 100, search: str | None = None
) -> Any:
    """
    Retrieve rulesetscripts.
    """

    count_statement = select(func.count()).select_from(RulesetScript)
    base_statement = select(RulesetScript, Ruleset).join(Ruleset)
    if search:
        f = (
            RulesetScript.condition.ilike(f"%{search}%")
            | RulesetScript.key.ilike(f"%{search}%")
            | RulesetScript.value.ilike(f"%{search}%")
            | RulesetScript.description.ilike(f"%{search}%")
        )
        count_statement = count_statement.where(f)
        base_statement = base_statement.where(f)
    count = session.exec(count_statement).one()

    # Same order the generator writes: grouped by ruleset, then by position.
    statement = (
        base_statement.order_by(Ruleset.name, *order_columns(RulesetScript))
        .offset(skip)
        .limit(limit)
    )
    rulesetscripts = session.exec(statement).all()
    data_rulesetscripts = []
    for rulesetscript, ruleset in rulesetscripts:
        data_rulesetscript = RulesetScriptPublic.from_orm(rulesetscript)
        data_rulesetscript.ruleset_name = ruleset.name
        data_rulesetscripts.append(data_rulesetscript)
    return RulesetScriptsPublic(data=data_rulesetscripts, count=count)


@router.post(
    "/",
    response_model=RulesetScriptPublic,
)
def create_rulesetscript(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    rulesetscript_in: RulesetScriptCreate,
) -> Any:
    """
    Create new rulesetscript.
    """

    try:
        rulesetscript = rulesetscripts.create_rulesetscript(
            session=session, rulesetscript_create=rulesetscript_in
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_logs_crud.log_entity_action(
        session=session,
        action="CREATE",
        entity_type="RulesetScript",
        entity_id=str(rulesetscript.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=rulesetscript.model_dump_json(exclude=_SENSITIVE),
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
    if not rulesetscript:
        raise HTTPException(status_code=404, detail="RulesetScript not found")
    data_rulesetscript = RulesetScriptPublic.from_orm(rulesetscript)
    ruleset = session.get(Ruleset, rulesetscript.ruleset_id)
    data_rulesetscript.ruleset_name = ruleset.name if ruleset else None
    return data_rulesetscript


@router.put(
    "/{id}",
    response_model=RulesetScriptPublic,
)
def update_rulesetscript(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
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
    old_values = db_rulesetscript.model_dump_json(exclude=_SENSITIVE)
    try:
        db_rulesetscript = rulesetscripts.update_rulesetscript(
            session=session,
            db_rulesetscript=db_rulesetscript,
            rulesetscript_in=rulesetscript_in,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_logs_crud.log_entity_action(
        session=session,
        action="UPDATE",
        entity_type="RulesetScript",
        entity_id=str(db_rulesetscript.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_rulesetscript.model_dump_json(exclude=_SENSITIVE),
    )
    return db_rulesetscript


@router.delete(
    "/{id}",
)
def delete_rulesetscript(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a ruleset script.
    """

    rulesetscript = session.get(RulesetScript, id)
    if not rulesetscript:
        raise HTTPException(status_code=404, detail="RulesetScript not found")

    old_values = rulesetscript.model_dump_json(exclude=_SENSITIVE)
    rulesetscripts.delete_rulesetscript(session=session, db_rulesetscript=rulesetscript)
    audit_logs_crud.log_entity_action(
        session=session,
        action="DELETE",
        entity_type="RulesetScript",
        entity_id=str(id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="RulesetScript deleted successfully")


@router.post(
    "/{id}/move",
    response_model=RulesetScriptPublic,
)
def move_rulesetscript(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    move_in: PositionMove,
) -> Any:
    """
    Move a ruleset script to a 0-based position within its ruleset.

    Siblings are renumbered in the same transaction. A move that would leave an
    `elif` or `else` without the `if` it continues is refused with 400.
    """
    db_rulesetscript = session.get(RulesetScript, id)
    if not db_rulesetscript:
        raise HTTPException(status_code=404, detail="RulesetScript not found")

    old_values = db_rulesetscript.model_dump_json(exclude=_SENSITIVE)
    try:
        db_rulesetscript = rulesetscripts.move_rulesetscript(
            session=session,
            db_rulesetscript=db_rulesetscript,
            position=move_in.position,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    audit_logs_crud.log_entity_action(
        session=session,
        action="UPDATE",
        entity_type="RulesetScript",
        entity_id=str(db_rulesetscript.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_rulesetscript.model_dump_json(exclude=_SENSITIVE),
    )
    return db_rulesetscript
