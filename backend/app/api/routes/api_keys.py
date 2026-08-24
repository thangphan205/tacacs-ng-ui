import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import func, select

from app.api.deps import (
    CurrentUser,
    SessionDep,
    SuperUser,
    get_client_ip,
    get_current_active_superuser,
    require_primary_node,
)
from app.crud import api_keys
from app.crud import audit_logs as audit_logs_crud
from app.models import (
    ApiKey,
    ApiKeyAllowedIpsUpdate,
    ApiKeyCreate,
    ApiKeyCreated,
    ApiKeyPublic,
    ApiKeysPublic,
    Message,
    User,
)

router = APIRouter(prefix="/api_keys", tags=["api_keys"])

_SENSITIVE = audit_logs_crud._SENSITIVE


@router.post(
    "/",
    dependencies=[Depends(require_primary_node)],
    response_model=ApiKeyCreated,
)
def create_api_key(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    api_key_in: ApiKeyCreate,
) -> Any:
    """
    Create a new API key.

    The plaintext key is returned exactly once, here. It is not recoverable
    afterwards — a lost key must be revoked and replaced.
    """
    owner_id = api_key_in.user_id or current_user.id
    if session.get(User, owner_id) is None:
        raise HTTPException(
            status_code=404,
            detail="The user this API key would belong to does not exist.",
        )

    db_api_key, plaintext = api_keys.create_api_key(
        session=session,
        api_key_create=api_key_in,
        owner_id=owner_id,
        created_by_id=current_user.id,
    )
    # Snapshot before auditing: log_entity_action commits, which expires this
    # instance's attributes, and model_dump() reads __dict__ directly without
    # triggering SQLAlchemy's lazy refresh — it would come back empty.
    payload = db_api_key.model_dump(exclude=_SENSITIVE)
    audit_logs_crud.log_entity_action(
        session=session,
        action="CREATE",
        entity_type="ApiKey",
        entity_id=str(payload["id"]),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        new_values=db_api_key.model_dump_json(exclude=_SENSITIVE),
        description=f"Created API key '{payload['name']}' ({payload['key_prefix']})",
    )
    return ApiKeyCreated(**payload, plaintext_key=plaintext)


@router.get(
    "/",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ApiKeysPublic,
)
def read_api_keys(
    session: SessionDep,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> Any:
    """
    Retrieve API keys.
    """
    count_statement = select(func.count()).select_from(ApiKey)
    statement = select(ApiKey)
    if search:
        f = ApiKey.name.ilike(f"%{search}%") | ApiKey.key_prefix.ilike(f"%{search}%")
        count_statement = count_statement.where(f)
        statement = statement.where(f)
    count = session.exec(count_statement).one()
    rows = session.exec(statement.offset(skip).limit(limit)).all()

    return ApiKeysPublic(data=rows, count=count)


@router.get("/me", response_model=ApiKeysPublic)
def read_own_api_keys(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """
    Retrieve the calling user's own API keys.
    """
    f = ApiKey.user_id == current_user.id
    count = session.exec(select(func.count()).select_from(ApiKey).where(f)).one()
    rows = session.exec(select(ApiKey).where(f).offset(skip).limit(limit)).all()

    return ApiKeysPublic(data=rows, count=count)


@router.get(
    "/{id}",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=ApiKeyPublic,
)
def read_api_key_by_id(
    id: uuid.UUID,
    session: SessionDep,
) -> Any:
    """
    Get a specific API key by id.
    """
    api_key = api_keys.get_api_key_by_id(session=session, id=id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")
    return api_key


@router.patch(
    "/{id}",
    dependencies=[Depends(require_primary_node)],
    response_model=ApiKeyPublic,
)
def update_api_key_allowed_ips(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    id: uuid.UUID,
    update_in: ApiKeyAllowedIpsUpdate,
) -> Any:
    """
    Update an API key's allowed source-IP restriction.

    This is the only field editable after creation — name/scopes/description/
    expiry are set once at creation, same as before this route existed.
    """
    api_key = api_keys.get_api_key_by_id(session=session, id=id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    old_values = api_key.model_dump_json(exclude=_SENSITIVE)
    api_key = api_keys.update_allowed_ips(
        session=session, db_api_key=api_key, allowed_ips=update_in.allowed_ips
    )
    audit_logs_crud.log_entity_action(
        session=session,
        action="UPDATE",
        entity_type="ApiKey",
        entity_id=str(api_key.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=api_key.model_dump_json(exclude=_SENSITIVE),
        description=f"Updated allowed IPs for API key '{api_key.name}' ({api_key.key_prefix})",
    )
    return api_key


@router.delete("/{id}", dependencies=[Depends(require_primary_node)])
def revoke_api_key(
    session: SessionDep, current_user: SuperUser, request: Request, id: uuid.UUID
) -> Message:
    """
    Revoke an API key.

    This is a soft revoke: the row is kept so audit entries referencing it stay
    resolvable, but the key stops authenticating immediately.
    """
    api_key = api_keys.get_api_key_by_id(session=session, id=id)
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    old_values = api_key.model_dump_json(exclude=_SENSITIVE)
    api_key = api_keys.revoke_api_key(session=session, db_api_key=api_key)
    audit_logs_crud.log_entity_action(
        session=session,
        action="REVOKE",
        entity_type="ApiKey",
        entity_id=str(api_key.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=old_values,
        new_values=api_key.model_dump_json(exclude=_SENSITIVE),
        description=f"Revoked API key '{api_key.name}' ({api_key.key_prefix})",
    )
    return Message(message="API key revoked successfully")
