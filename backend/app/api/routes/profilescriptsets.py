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
from app.crud import profilescriptsets
from app.models import (
    Message,
    Profile,
    ProfileScript,
    ProfileScriptSet,
    ProfileScriptSetCreate,
    ProfileScriptSetPublic,
    ProfileScriptSetsPublic,
    ProfileScriptSetUpdate,
)

router = APIRouter(prefix="/profilescriptsets", tags=["profilescriptsets"])

_SENSITIVE = audit_logs_crud._SENSITIVE


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
    response_model=ProfileScriptSetPublic,
)
def create_profilescriptset(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    profilescriptset_in: ProfileScriptSetCreate,
) -> Any:
    """
    Create new profilescriptset.
    """

    profilescriptset = profilescriptsets.create_profilescriptset(
        session=session, profilescriptset_create=profilescriptset_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="ProfileScriptSet",
        entity_id=str(profilescriptset.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=profilescriptset.model_dump_json(exclude=_SENSITIVE),
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
    profilescriptset = session.get(ProfileScriptSet, id)

    if not profilescriptset:
        raise HTTPException(status_code=404, detail="ProfileScriptSet not found")
    return profilescriptset


@router.put(
    "/{id}",
    response_model=ProfileScriptSetPublic,
)
def update_profilescriptset(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    profilescriptset_in: ProfileScriptSetUpdate,
) -> Any:
    """
    Update a profilescriptset.
    """

    db_profilescriptset = session.get(ProfileScriptSet, id)
    if not db_profilescriptset:
        raise HTTPException(
            status_code=404,
            detail="The profilescriptset with this id does not exist in the system",
        )
    old_values = db_profilescriptset.model_dump_json(exclude=_SENSITIVE)
    db_profilescriptset = profilescriptsets.update_profilescriptset(
        session=session,
        db_profilescriptset=db_profilescriptset,
        profilescriptset_in=profilescriptset_in,
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="ProfileScriptSet",
        entity_id=str(db_profilescriptset.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_profilescriptset.model_dump_json(exclude=_SENSITIVE),
    )
    return db_profilescriptset


@router.delete(
    "/{id}",
)
def delete_profilescriptset(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a profile script set.
    """

    profilescriptset = session.get(ProfileScriptSet, id)
    if not profilescriptset:
        raise HTTPException(status_code=404, detail="ProfileScriptSet not found")

    old_values = profilescriptset.model_dump_json(exclude=_SENSITIVE)
    session.delete(profilescriptset)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="ProfileScriptSet",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="ProfileScriptSet deleted successfully")
