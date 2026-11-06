import uuid
from typing import Any

from sqlmodel import Session, select

from app.crud import ordering
from app.models import (
    Profile,
    ProfileScript,
    ProfileScriptCreate,
    ProfileScriptUpdate,
)

# Scripts are ordered within their profile, as an if/elif/else chain.
SIBLINGS = ordering.Siblings(
    model=ProfileScript, parent_attr="profile_id", condition_attr="condition"
)


def _refuse_raw_parent(session: Session, profile_id: uuid.UUID | None) -> None:
    # One mode per profile (#359): a raw script replaces the structured
    # scripts, so a script added to it would sit unused. The caller already
    # holds the profile's lock (`ordering.lock_parents`, the one update_profile
    # takes), so the check and the insert can't interleave with a concurrent
    # switch to raw. A fresh SELECT reads raw_script as of the lock.
    if not profile_id:
        return
    row = session.exec(
        select(Profile.name, Profile.raw_script).where(Profile.id == profile_id)
    ).first()
    if row is not None and row.raw_script:
        raise ValueError(
            f"Profile '{row.name}' uses a raw script; structured scripts "
            "can't be added to it."
        )


def create_profilescript(
    *, session: Session, profilescript_create: ProfileScriptCreate
) -> ProfileScript:
    """Append, or insert at `position`. Raises `ValueError` on a broken chain
    or a raw-script profile."""
    if profilescript_create.profile_id:
        ordering.lock_parents(session, SIBLINGS, [profilescript_create.profile_id])
    _refuse_raw_parent(session, profilescript_create.profile_id)
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

    Raises `ValueError` if the result breaks an if/elif/else chain, or moves
    the script to a raw-script profile.
    """
    data = profilescript_in.model_dump(exclude_unset=True)
    new_parent = data.get("profile_id")
    if new_parent and new_parent != db_profilescript.profile_id:
        # Both groups, in sorted order, before any check: ordering.update
        # locks the same pair, so two opposite moves cannot deadlock.
        ordering.lock_parents(
            session, SIBLINGS, [db_profilescript.profile_id, new_parent]
        )
        _refuse_raw_parent(session, new_parent)
    return ordering.update(
        session=session,
        spec=SIBLINGS,
        row=db_profilescript,
        data=data,
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
