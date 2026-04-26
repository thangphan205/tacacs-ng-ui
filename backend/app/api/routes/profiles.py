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
from app.crud import profiles
from app.models import (
    Message,
    Profile,
    ProfileCreate,
    ProfilePreviewPublic,
    ProfilePublic,
    ProfilesPublic,
    ProfileUpdate,
)

router = APIRouter(prefix="/profiles", tags=["profiles"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=ProfilesPublic,
)
def read_profiles(session: SessionDep, skip: int = 0, limit: int = 100, search: str | None = None) -> Any:
    """
    Retrieve profiles.
    """

    count_statement = select(func.count()).select_from(Profile)
    statement = select(Profile)
    if search:
        f = Profile.name.contains(search) | Profile.action.contains(search) | Profile.description.contains(search)
        count_statement = count_statement.where(f)
        statement = statement.where(f)
    count = session.exec(count_statement).one()

    profiles = session.exec(statement.offset(skip).limit(limit)).all()

    return ProfilesPublic(data=profiles, count=count)


@router.get(
    "/preview",
    dependencies=[Depends(get_current_user)],
    response_model=ProfilePreviewPublic,
)
def preview_profiles(session: SessionDep) -> Any:
    """
    Preview profiles.
    Generate candidate profile configuration preview.
    """
    statement = select(Profile)
    profiles_data = session.exec(statement).all()

    if not profiles_data:
        return ProfilePreviewPublic(data=None, created_at=None, updated_at=None)

    profile_template = profiles.profile_generator(session=session)
    created_at = min(p.created_at for p in profiles_data)
    updated_at = max(p.updated_at for p in profiles_data)

    return ProfilePreviewPublic(
        data=profile_template, created_at=created_at, updated_at=updated_at
    )


@router.post(
    "/",
    response_model=ProfilePublic,
)
def create_profile(
    *, session: SessionDep, current_user: SuperUser, request: Request, profile_in: ProfileCreate
) -> Any:
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
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="Profile",
        entity_id=str(profile.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=profile.model_dump_json(exclude=_SENSITIVE),
    )
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
    response_model=ProfilePublic,
)
def update_profile(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
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

    old_values = db_profile.model_dump_json(exclude=_SENSITIVE)
    db_profile = profiles.update_profile(
        session=session, db_profile=db_profile, profile_in=profile_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="Profile",
        entity_id=str(db_profile.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_profile.model_dump_json(exclude=_SENSITIVE),
    )
    return db_profile


@router.delete(
    "/{id}",
)
def delete_profile(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a profile.
    """

    profile = session.get(Profile, id)
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")

    old_values = profile.model_dump_json(exclude=_SENSITIVE)
    session.delete(profile)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="Profile",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="Profile deleted successfully")
