import uuid
from typing import Any
from sqlalchemy.orm import joinedload
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.crud import profilescriptsets
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    ProfileScriptSet,
    ProfileScriptSetCreate,
    ProfileScriptSetPublic,
    ProfileScriptSetsPublic,
    ProfileScriptSetUpdate,
    ProfileScript,
    Profile,
)

router = APIRouter(prefix="/profilescriptsets", tags=["profilescriptsets"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=ProfileScriptSetsPublic,
)
def read_profilescriptsets(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve profilescriptsets.
    """

    count_statement = select(func.count()).select_from(ProfileScriptSet)
    count = session.exec(count_statement).one()

    # statement = select(ProfileScriptSet).offset(skip).limit(limit)
    statement = (
        select(ProfileScriptSet, ProfileScript)
        .join(ProfileScript)
        .offset(skip)
        .limit(limit)
    )
    profilescriptsets = session.exec(statement).all()
    data_profilescriptsets = []
    for profilescriptset, profilescript in profilescriptsets:
        data_profilescriptset = ProfileScriptSetPublic.from_orm(profilescriptset)
        profile = session.get(Profile, profilescript.profile_id)
        data_profilescriptset.profile_id = profilescript.profile_id
        data_profilescriptset.profile_name = profile.name
        data_profilescriptset.profilescript_block = (
            profilescript.key + "==" + profilescript.value
        )
        data_profilescriptsets.append(data_profilescriptset)

    return ProfileScriptSetsPublic(data=data_profilescriptsets, count=count)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProfileScriptSetPublic,
)
def create_profilescriptset(
    *,
    session: SessionDep,
    profilescriptset_in: ProfileScriptSetCreate,
) -> Any:
    """
    Create new profilescriptset.
    """

    profilescriptset = profilescriptsets.create_profilescriptset(
        session=session, profilescriptset_create=profilescriptset_in
    )

    return profilescriptset


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_user)],
    response_model=ProfileScriptSetPublic,
)
def read_profilescriptset_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific profilescriptset by id.
    """
    statement = (
        select(ProfileScriptSet)
        .where(ProfileScriptSet.id == id)
        .options(
            joinedload(ProfileScriptSet.profile),
            joinedload(ProfileScriptSet.profilescript),
        )
    )
    profilescriptset = session.exec(statement).first()

    if not profilescriptset:
        raise HTTPException(status_code=404, detail="ProfileScriptSet not found")
    return profilescriptset


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProfileScriptSetPublic,
)
def update_profilescriptset(
    *,
    session: SessionDep,
    id: uuid.UUID,
    profilescriptset_in: ProfileScriptSetUpdate,
) -> Any:
    """
    Update a profilescriptset.
    """

    statement = (
        select(ProfileScriptSet)
        .where(ProfileScriptSet.id == id)
        .options(
            joinedload(ProfileScriptSet.profile),
            joinedload(ProfileScriptSet.profilescript),
        )
    )
    db_profilescriptset = session.exec(statement).first()
    if not db_profilescriptset:
        raise HTTPException(
            status_code=404,
            detail="The profilescriptset with this id does not exist in the system",
        )
    db_profilescriptset = profilescriptsets.update_profilescriptset(
        session=session,
        db_profilescriptset=db_profilescriptset,
        profilescriptset_in=profilescriptset_in,
    )
    return db_profilescriptset


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_profilescriptset(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    profilescriptset = session.get(ProfileScriptSet, id)
    if not profilescriptset:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(profilescriptset)
    session.commit()
    return Message(message="ProfileScriptSet deleted successfully")
