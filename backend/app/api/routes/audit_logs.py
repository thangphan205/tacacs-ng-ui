import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.crud import audit_logs as crud_audit_logs
from app.models import AuditLog, AuditLogPublic, AuditLogsPublic

router = APIRouter(prefix="/audit_logs", tags=["audit_logs"])


@router.get("/", response_model=AuditLogsPublic)
def read_audit_logs(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> Any:
    user_id = None if current_user.is_superuser else current_user.id
    logs, count = crud_audit_logs.get_audit_logs(
        session=session, skip=skip, limit=limit, search=search, user_id=user_id
    )
    return AuditLogsPublic(data=logs, count=count)


@router.get("/{id}", response_model=AuditLogPublic)
def read_audit_log_by_id(
    id: uuid.UUID, session: SessionDep, current_user: CurrentUser
) -> Any:
    log = session.get(AuditLog, id)
    if not log:
        raise HTTPException(status_code=404, detail="Audit log not found")
    if not current_user.is_superuser and log.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return log


@router.delete("/purge", dependencies=[Depends(get_current_active_superuser)])
def purge_audit_logs(session: SessionDep) -> dict[str, int]:
    deleted = crud_audit_logs.purge_old_audit_logs(session=session)
    return {"deleted": deleted}
