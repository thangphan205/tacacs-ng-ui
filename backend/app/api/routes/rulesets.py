import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import func, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    SuperUser,
    get_current_user,
)
from app.crud import audit_logs as audit_logs_crud
from app.crud import rulesets
from app.models import (
    Message,
    Ruleset,
    RulesetCreate,
    RulesetPreviewPublic,
    RulesetPublic,
    RulesetsPublic,
    RulesetUpdate,
)

router = APIRouter(prefix="/rulesets", tags=["rulesets"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetsPublic,
)
def read_rulesets(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve rulesets.
    """

    count_statement = select(func.count()).select_from(Ruleset)
    count = session.exec(count_statement).one()

    statement = select(Ruleset).offset(skip).limit(limit)
    rulesets = session.exec(statement).all()

    return RulesetsPublic(data=rulesets, count=count)


@router.get(
    "/preview",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetPreviewPublic,
)
def preview_rulesets(
    session: SessionDep,
) -> Any:
    """
    Preview rulesets.
    Generate candidate ruleset configuration preview.
    """
    statement = select(Ruleset)
    rulesets_data = session.exec(statement).all()

    if not rulesets_data:
        return RulesetPreviewPublic(data=None, created_at=None, updated_at=None)

    preview_rulesets_section = rulesets.ruleset_generator(session=session)
    created_at = min(r.created_at for r in rulesets_data)
    updated_at = max(r.updated_at for r in rulesets_data)

    return RulesetPreviewPublic(
        data=preview_rulesets_section, created_at=created_at, updated_at=updated_at
    )


@router.post(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetPublic,
)
def create_ruleset(
    *, session: SessionDep, current_user: CurrentUser, request: Request, ruleset_in: RulesetCreate
) -> Any:
    """
    Create new ruleset.
    """

    ruleset = rulesets.get_ruleset_by_name(session=session, name=ruleset_in.name)
    if ruleset:
        raise HTTPException(
            status_code=400,
            detail="The ruleset with this ruleset name already exists in the system.",
        )

    ruleset = rulesets.create_ruleset(session=session, ruleset_create=ruleset_in)
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="Ruleset",
        entity_id=str(ruleset.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        new_values=ruleset.model_dump_json(exclude=_SENSITIVE),
    )
    return ruleset


@router.get(
    "/{id}", dependencies=[Depends(get_current_user)], response_model=RulesetPublic
)
def read_ruleset_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific ruleset by id.
    """
    ruleset = session.get(Ruleset, id)

    return ruleset


@router.put(
    "/{id}",
    response_model=RulesetPublic,
)
def update_ruleset(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    ruleset_in: RulesetUpdate,
) -> Any:
    """
    Update a ruleset.
    """

    db_ruleset = session.get(Ruleset, id)
    if not db_ruleset:
        raise HTTPException(
            status_code=404,
            detail="The ruleset with this id does not exist in the system",
        )
    old_values = db_ruleset.model_dump_json(exclude=_SENSITIVE)
    db_ruleset = rulesets.update_ruleset(
        session=session, db_ruleset=db_ruleset, ruleset_in=ruleset_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="Ruleset",
        entity_id=str(db_ruleset.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_ruleset.model_dump_json(exclude=_SENSITIVE),
    )
    return db_ruleset


@router.delete(
    "/{id}",
)
def delete_ruleset(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a ruleset.
    """

    ruleset = session.get(Ruleset, id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="Ruleset not found")
    old_values = ruleset.model_dump_json(exclude=_SENSITIVE)
    session.delete(ruleset)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="Ruleset",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="Ruleset deleted successfully")
