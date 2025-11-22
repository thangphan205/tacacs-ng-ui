import uuid
from typing import Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.crud import profiles
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    Profile,
    ProfileCreate,
    ProfilePublic,
    ProfilesPublic,
    ProfileUpdate,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=ProfilesPublic,
)
def read_profiles(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve profiles.
    """

    count_statement = select(func.count()).select_from(Profile)
    count = session.exec(count_statement).one()

    statement = select(Profile).offset(skip).limit(limit)
    profiles = session.exec(statement).all()

    return ProfilesPublic(data=profiles, count=count)


@router.get(
    "/preview",
    dependencies=[Depends(get_current_user)],
)
def preview_profiles(session: SessionDep) -> Any:
    """
    Preview profiles.
    Generate candidate profile configuration preview.
    """

    profile_template = profiles.profile_generator(session=session)

    return {"data": profile_template, "created_at": datetime.utcnow()}


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProfilePublic,
)
def create_profile(*, session: SessionDep, profile_in: ProfileCreate) -> Any:
    """
    Create new profile.
    """
    profile = profiles.get_profile_by_name(session=session, name=profile_in.name)
    if profile:
        raise HTTPException(
            status_code=400,
            detail="The profile with this profile name already exists in the system.",
        )

    profile = profiles.create_profile(session=session, profile_create=profile_in)
    return profile


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_user)],
    response_model=ProfilePublic,
)
def read_profile_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific profile by id.
    """
    profile = session.get(Profile, id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProfilePublic,
)
def update_profile(
    *,
    session: SessionDep,
    id: uuid.UUID,
    profile_in: ProfileUpdate,
) -> Any:
    """
    Update a profile.
    """

    db_profile = session.get(Profile, id)
    if not db_profile:
        raise HTTPException(
            status_code=404,
            detail="The profile with this id does not exist in the system",
        )

    db_profile = profiles.update_profile(
        session=session, db_profile=db_profile, profile_in=profile_in
    )
    return db_profile


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_profile(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    profile = session.get(Profile, id)
    if not profile:
        raise HTTPException(status_code=404, detail="User not found")

    session.delete(profile)
    session.commit()
    return Message(message="Profile deleted successfully")
