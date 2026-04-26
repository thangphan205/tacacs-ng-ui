import re
import uuid
from datetime import datetime, timezone
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
from app.crud import tacacs_configs
from app.models import (
    Message,
    TacacsConfig,
    TacacsConfigCreate,
    TacacsConfigPreviewPublic,
    TacacsConfigPublic,
    TacacsConfigsPublic,
    TacacsConfigUpdate,
)

router = APIRouter(prefix="/tacacs_configs", tags=["tacacs_configs"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.get(
    "/",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsConfigsPublic,
)
def read_tacacs_configs(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    search: str | None = None,
) -> Any:
    """
    Retrieve tacacs_configs.
    """

    count_statement = select(func.count()).select_from(TacacsConfig)
    statement = select(TacacsConfig)
    if search:
        f = TacacsConfig.filename.contains(search) | TacacsConfig.description.contains(search)
        count_statement = count_statement.where(f)
        statement = statement.where(f)
    count = session.exec(count_statement).one()
    sort_column = getattr(TacacsConfig, sort_by, None)
    if sort_column is None:
        raise HTTPException(status_code=400, detail=f"Invalid sort column: {sort_by}")
    order = sort_column.desc() if sort_order == "desc" else sort_column.asc()
    tacacs_configs = session.exec(statement.order_by(order).offset(skip).limit(limit)).all()

    return TacacsConfigsPublic(data=tacacs_configs, count=count)


@router.get(
    "/preview",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsConfigPreviewPublic,
)
def generate_preview_tacacs_config(*, session: SessionDep) -> Any:
    """
    Preview candidate tacacs_config.
    """

    tacacs_config = tacacs_configs.generate_preview_tacacs_config(session=session)
    return {
        "data": tacacs_config,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }


@router.get(
    "/active",
    dependencies=[Depends(get_current_user)],
    response_model=TacacsConfigPublic,
)
def get_active_tacacs_config(*, session: SessionDep) -> Any:
    """
    Preview candidate tacacs_config.
    """

    tacacs_config = tacacs_configs.get_active_tacacs_config(session=session)
    tacacs_config_return = TacacsConfigPublic.model_validate(tacacs_config)
    tacacs_config_return.data = tacacs_configs.get_tacacs_config_by_filename(
        filename="tac_plus-ng"
    )
    return tacacs_config_return


@router.post(
    "/",
    response_model=TacacsConfigPublic,
)
def create_tacacs_config(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    tacacs_config_in: TacacsConfigCreate,
) -> Any:
    """
    Create new tacacs_config.
    """

    # Validate filename for safe characters
    if not re.match(r"^[a-zA-Z0-9._-]+$", tacacs_config_in.filename):
        raise HTTPException(
            status_code=400,
            detail="Invalid filename. Only alphanumerics, dots, underscores, and hyphens are allowed.",
        )
    if tacacs_config_in.filename in [".", ".."]:
        raise HTTPException(
            status_code=400,
            detail="Filename cannot be '.' or '..'.",
        )

    tacacs_config = tacacs_configs.get_tacacs_config_by_name(
        session=session, name=tacacs_config_in.filename
    )
    if tacacs_config or tacacs_config_in.filename == "tac_plus-ng":
        raise HTTPException(
            status_code=400,
            detail="The tacacs_config with this tacacs_config name already exists in the system.",
        )

    tacacs_config = tacacs_configs.create_tacacs_config(
        session=session, tacacs_config_create=tacacs_config_in
    )
    audit_logs_crud.log_entity_action(
        session=session, action="CREATE", entity_type="TacacsConfig",
        entity_id=str(tacacs_config.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=tacacs_config.model_dump_json(exclude=_SENSITIVE),
    )
    return tacacs_config


@router.get(
    "/{id}", dependencies=[Depends(get_current_user)], response_model=TacacsConfigPublic
)
def read_tacacs_config_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific tacacs_config by id.
    """
    tacacs_config = session.get(TacacsConfig, id)

    if not tacacs_config:
        raise HTTPException(
            status_code=404,
            detail="The tacacs_config with this id does not exist in the system",
        )
    file_content = tacacs_configs.get_tacacs_config_by_filename(tacacs_config.filename)
    tacacs_config_return = TacacsConfigPublic.model_validate(tacacs_config)
    tacacs_config_return.data = file_content
    return tacacs_config_return


@router.get(
    "/{id}/check",
    dependencies=[Depends(get_current_user)],
)
def check_tacacs_config_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Check a specific tacacs_config by id.
    """
    tacacs_config = session.get(TacacsConfig, id)

    if not tacacs_config:
        raise HTTPException(
            status_code=404,
            detail="The tacacs_config with this id does not exist in the system",
        )
    result = tacacs_configs.check_tacacs_config_by_id(session=session, id=id)
    return result


@router.put(
    "/{id}",
    response_model=TacacsConfigPublic,
)
def update_tacacs_config(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    tacacs_config_in: TacacsConfigUpdate,
) -> Any:
    """
    Update a tacacs_config.
    """

    db_tacacs_config = session.get(TacacsConfig, id)
    if not db_tacacs_config:
        raise HTTPException(
            status_code=404,
            detail="The tacacs_config with this id does not exist in the system",
        )

    result = tacacs_configs.check_tacacs_config_by_id(session=session, id=id)
    if result["line"] > 0:
        raise HTTPException(
            status_code=400,
            detail=result["message"],
        )

    old_values = db_tacacs_config.model_dump_json(exclude=_SENSITIVE)
    db_tacacs_config = tacacs_configs.update_tacacs_config(
        session=session,
        db_tacacs_config=db_tacacs_config,
        tacacs_config_in=tacacs_config_in,
    )
    audit_logs_crud.log_entity_action(
        session=session, action="UPDATE", entity_type="TacacsConfig",
        entity_id=str(db_tacacs_config.id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=db_tacacs_config.model_dump_json(exclude=_SENSITIVE),
    )
    return db_tacacs_config


@router.delete(
    "/{id}",
    response_model=Message,
)
def delete_tacacs_config(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Delete a TACACS config.
    """

    db_tacacs_config = session.get(TacacsConfig, id)
    if not db_tacacs_config:
        raise HTTPException(status_code=404, detail="TacacsConfig not found")
    old_values = db_tacacs_config.model_dump_json(exclude=_SENSITIVE)
    tacacs_configs.delete_tacacs_config(
        session=session, db_tacacs_config=db_tacacs_config
    )
    audit_logs_crud.log_entity_action(
        session=session, action="DELETE", entity_type="TacacsConfig",
        entity_id=str(id),
        user_id=current_user.id, user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
    )
    return Message(message="TacacsConfig deleted successfully")
