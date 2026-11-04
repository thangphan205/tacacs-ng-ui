from typing import Any

from sqlmodel import Session

from app.crud import ordering
from app.models import ProfileScript, ProfileScriptCreate, ProfileScriptUpdate

# Scripts are ordered within their profile, as an if/elif/else chain.
SIBLINGS = ordering.Siblings(
    model=ProfileScript, parent_attr="profile_id", condition_attr="condition"
)


def create_profilescript(
    *, session: Session, profilescript_create: ProfileScriptCreate
) -> ProfileScript:
    """Append, or insert at `position`. Raises `ValueError` on a broken chain."""
    row: ProfileScript = ordering.create(
        session=session,
        spec=SIBLINGS,
        data=profilescript_create.model_dump(exclude={"position"}),
        position=profilescript_create.position,
    )
    return row


def update_profilescript(
    *,
    session: Session,
    db_profilescript: ProfileScript,
    profilescript_in: ProfileScriptUpdate,
) -> Any:
    """Field changes keep the script's place unless `position` is given.

    Raises `ValueError` if the result breaks an if/elif/else chain.
    """
    return ordering.update(
        session=session,
        spec=SIBLINGS,
        row=db_profilescript,
        data=profilescript_in.model_dump(exclude_unset=True),
    )


def move_profilescript(
    *, session: Session, db_profilescript: ProfileScript, position: int
) -> ProfileScript:
    """Reorder within the parent profile. Raises `ValueError` on a broken chain."""
    row: ProfileScript = ordering.update(
        session=session,
        spec=SIBLINGS,
        row=db_profilescript,
        data={"position": position},
    )
    return row


def delete_profilescript(*, session: Session, db_profilescript: ProfileScript) -> None:
    """Delete and close the gap. Raises `ValueError` if that orphans an elif/else."""
    ordering.delete(session=session, spec=SIBLINGS, row=db_profilescript)
