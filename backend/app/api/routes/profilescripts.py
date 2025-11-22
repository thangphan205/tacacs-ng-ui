import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import func, select

from app.crud import profilescripts
from app.api.deps import (
    SessionDep,
    get_current_active_superuser,
    get_current_user,
)
from app.models import (
    Message,
    Profile,
    ProfileScript,
    ProfileScriptCreate,
    ProfileScriptPublic,
    ProfileScriptsPublic,
    ProfileScriptUpdate,
)

router = APIRouter(prefix="/profilescripts", tags=["profilescripts"])


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=ProfileScriptsPublic,
)
def read_profilescripts(session: SessionDep, skip: int = 0, limit: int = 100) -> Any:
    """
    Retrieve profilescripts.
    """

    count_statement = select(func.count()).select_from(ProfileScript)
    count = session.exec(count_statement).one()

    statement = select(ProfileScript, Profile).join(Profile).offset(skip).limit(limit)
    profilescripts = session.exec(statement).all()
    data_profilescripts = []
    for profilescript, profile in profilescripts:
        data_profilescript = ProfileScriptPublic.from_orm(profilescript)
        data_profilescript.profile_name = profile.name
        data_profilescripts.append(data_profilescript)
    return ProfileScriptsPublic(count=count, data=data_profilescripts)


@router.post(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProfileScriptPublic,
)
def create_profilescript(
    *,
    session: SessionDep,
    profilescript_in: ProfileScriptCreate,
) -> Any:
    """
    Create new profilescript.
    """

    profilescript = profilescripts.create_profilescript(
        session=session, profilescript_create=profilescript_in
    )
    return profilescript


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_user)],
    response_model=ProfileScriptPublic,
)
def read_profilescript_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific profilescript by id.
    """
    profilescript = session.get(ProfileScript, id)
    if not profilescript:
        raise HTTPException(status_code=404, detail="ProfileScript not found")
    data_profilescript = ProfileScriptPublic.from_orm(profilescript)
    profile = session.get(Profile, profilescript.profile_id)
    data_profilescript.profile_name = profile.name
    return data_profilescript


@router.put(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ProfileScriptPublic,
)
def update_profilescript(
    *,
    session: SessionDep,
    id: uuid.UUID,
    profilescript_in: ProfileScriptUpdate,
) -> Any:
    """
    Update a profilescript.
    """

    db_profilescript = session.get(ProfileScript, id)
    if not db_profilescript:
        raise HTTPException(
            status_code=404,
            detail="The profilescript with this id does not exist in the system",
        )

    db_profilescript = profilescripts.update_profilescript(
        session=session,
        db_profilescript=db_profilescript,
        profilescript_in=profilescript_in,
    )
    return db_profilescript


@router.delete(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
)
def delete_profilescript(session: SessionDep, id: uuid.UUID) -> Message:
    """
    Delete an item.
    """

    profilescript = session.get(ProfileScript, id)
    if not profilescript:
        raise HTTPException(status_code=404, detail="Profilescript not found")

    session.delete(profilescript)
    session.commit()
    return Message(message="ProfileScript deleted successfully")
