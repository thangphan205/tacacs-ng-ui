import uuid
from typing import Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.crud import rulesets
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    Ruleset,
    RulesetCreate,
    RulesetPublic,
    RulesetsPublic,
    RulesetUpdate,
)

router = APIRouter(prefix="/rulesets", tags=["rulesets"])


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
)
def preview_rulesets(
    session: SessionDep,
) -> Any:
    """
    Preview rulesets.
    Generate candidate ruleset configuration preview.
    """

    preview_rulesets_section = rulesets.ruleset_generator(session=session)

    return {"data": preview_rulesets_section, "created_at": datetime.utcnow()}


@router.post(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=RulesetPublic,
)
def create_ruleset(*, session: SessionDep, ruleset_in: RulesetCreate) -> Any:
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
    dependencies=[Depends(get_current_active_superuser)],
    response_model=RulesetPublic,
)
def update_ruleset(
    *,
    session: SessionDep,
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
    db_ruleset = rulesets.update_ruleset(
        session=session, db_ruleset=db_ruleset, ruleset_in=ruleset_in
    )
    return db_ruleset


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_ruleset(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    ruleset = session.get(Ruleset, id)
    if not ruleset:
        raise HTTPException(status_code=404, detail="User not found")
    session.delete(ruleset)
    session.commit()
    return Message(message="Ruleset deleted successfully")
