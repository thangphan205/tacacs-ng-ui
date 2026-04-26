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
from app.crud import profilescripts
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

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=ProfileScriptsPublic,
)
def read_profilescripts(session: SessionDep, skip: int = 0, limit: int = 100, search: str | None = None) -> Any:
    """
    Retrieve profilescripts.
    """

    count_statement = select(func.count()).select_from(ProfileScript)
    base_statement = select(ProfileScript, Profile).join(Profile)
    if search:
        f = ProfileScript.condition.contains(search) | ProfileScript.key.contains(search) | ProfileScript.value.contains(search) | ProfileScript.description.contains(search)
        count_statement = count_statement.where(f)
        base_statement = base_statement.where(f)
    count = session.exec(count_statement).one()

    statement = base_statement.offset(skip).limit(limit)
    profilescripts = session.exec(statement).all()
    data_profilescripts = []
    for profilescript, profile in profilescripts:
        data_profilescript = ProfileScriptPublic.from_orm(profilescript)
        data_profilescript.profile_name = profile.name
        data_profilescripts.append(data_profilescript)
    return ProfileScriptsPublic(count=count, data=data_profilescripts)


@router.post(
    "/",
    response_model=ProfileScriptPublic,
)
def create_profilescript(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    profilescript_in: ProfileScriptCreate,
) -> Any:
    """
    Create new profilescript.
    """

    profilescript = profilescripts.create_profilescript(
        session=session, profilescript_create=profilescript_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="ProfileScript",
        entity_id=str(profilescript.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=profilescript.model_dump_json(exclude=_SENSITIVE),
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
    response_model=ProfileScriptPublic,
)
def update_profilescript(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
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

    old_values = db_profilescript.model_dump_json(exclude=_SENSITIVE)
    db_profilescript = profilescripts.update_profilescript(
        session=session,
        db_profilescript=db_profilescript,
        profilescript_in=profilescript_in,
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="ProfileScript",
        entity_id=str(db_profilescript.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_profilescript.model_dump_json(exclude=_SENSITIVE),
    )
    return db_profilescript


@router.delete(
    "/{id}",
)
def delete_profilescript(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a profile script.
    """

    profilescript = session.get(ProfileScript, id)
    if not profilescript:
        raise HTTPException(status_code=404, detail="Profilescript not found")

    old_values = profilescript.model_dump_json(exclude=_SENSITIVE)
    session.delete(profilescript)
    session.commit()
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="ProfileScript",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="ProfileScript deleted successfully")
