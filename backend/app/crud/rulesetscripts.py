from typing import Any

from sqlmodel import Session

from app.crud import ordering
from app.models import RulesetScript, RulesetScriptCreate, RulesetScriptUpdate

# Scripts are ordered within their ruleset, as an if/elif/else chain.
SIBLINGS = ordering.Siblings(
    model=RulesetScript, parent_attr="ruleset_id", condition_attr="condition"
)


def create_rulesetscript(
    *, session: Session, rulesetscript_create: RulesetScriptCreate
) -> RulesetScript:
    """Append, or insert at `position`. Raises `ValueError` on a broken chain."""
    row: RulesetScript = ordering.create(
        session=session,
        spec=SIBLINGS,
        data=rulesetscript_create.model_dump(exclude={"position"}),
        position=rulesetscript_create.position,
    )
    return row


def update_rulesetscript(
    *,
    session: Session,
    db_rulesetscript: RulesetScript,
    rulesetscript_in: RulesetScriptUpdate,
) -> Any:
    """Field changes keep the script's place unless `position` is given.

    Raises `ValueError` if the result breaks an if/elif/else chain.
    """
    return ordering.update(
        session=session,
        spec=SIBLINGS,
        row=db_rulesetscript,
        data=rulesetscript_in.model_dump(exclude_unset=True),
    )


def move_rulesetscript(
    *, session: Session, db_rulesetscript: RulesetScript, position: int
) -> RulesetScript:
    """Reorder within the parent ruleset. Raises `ValueError` on a broken chain."""
    row: RulesetScript = ordering.update(
        session=session,
        spec=SIBLINGS,
        row=db_rulesetscript,
        data={"position": position},
    )
    return row


def delete_rulesetscript(*, session: Session, db_rulesetscript: RulesetScript) -> None:
    """Delete and close the gap. Raises `ValueError` if that orphans an elif/else."""
    ordering.delete(session=session, spec=SIBLINGS, row=db_rulesetscript)
