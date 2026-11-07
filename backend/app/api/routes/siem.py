import json
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool

from app.api.deps import (
    SessionDep,
    SuperUser,
    get_client_ip,
    get_current_active_superuser,
    require_primary_node,
)
from app.core.config import settings
from app.crud import audit_logs as audit_logs_crud
from app.crud import siem_config as siem_config_crud
from app.crud import siem_tailer, tacacs_siem
from app.models import (
    SiemConfigPublic,
    SiemConfigUpdate,
    SiemStatus,
    SiemTestResult,
)

router = APIRouter(prefix="/siem", tags=["siem"])

# The shipper rewrites its status file every tick (~1 s); older than this
# means it is not running.
_STATUS_STALE = timedelta(seconds=30)


@router.get(
    "/config",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SiemConfigPublic,
)
def read_siem_config(session: SessionDep) -> Any:
    """SIEM forwarding settings. The webhook token is never returned."""
    return siem_config_crud.to_public(siem_config_crud.get_config(session=session))


@router.put(
    "/config",
    dependencies=[Depends(require_primary_node)],
    response_model=SiemConfigPublic,
)
def update_siem_config(
    *,
    session: SessionDep,
    current_user: SuperUser,
    request: Request,
    config_in: SiemConfigUpdate,
) -> Any:
    """Update SIEM forwarding. Every node's shipper picks it up within ~10 s."""
    old = siem_config_crud.audit_snapshot(siem_config_crud.get_config(session=session))
    cfg = siem_config_crud.update_config(session=session, config_in=config_in)
    audit_logs_crud.log_entity_action(
        session=session,
        action="UPDATE",
        entity_type="SiemConfig",
        entity_id=str(cfg.id),
        user_id=current_user.id,
        user_email=current_user.email,
        ip_address=get_client_ip(request),
        user_agent=request.headers.get("user-agent"),
        old_values=json.dumps(old),
        new_values=json.dumps(siem_config_crud.audit_snapshot(cfg)),
    )
    return siem_config_crud.to_public(cfg)


@router.post(
    "/test",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SiemTestResult,
)
async def test_siem(session: SessionDep) -> Any:
    """Send one test event to each saved sink, from the node serving the request."""
    target = tacacs_siem.load_target(session, require_enabled=False)
    if target is None:
        raise HTTPException(
            status_code=400,
            detail="No SIEM destination is configured. Set a webhook URL or a syslog host and save first.",
        )
    results = await run_in_threadpool(tacacs_siem.send_test_event, target)
    return SiemTestResult(results=results)


@router.get(
    "/status",
    dependencies=[Depends(get_current_active_superuser)],
    response_model=SiemStatus,
)
def read_siem_status() -> Any:
    """Real-time shipper status on the node that answers this request."""
    raw = siem_tailer.read_status()
    node = tacacs_siem.node_name()
    if raw is None:
        return SiemStatus(node_name=node, node_role=settings.NODE_ROLE, running=False)
    status = SiemStatus.model_validate(
        {
            **raw,
            "node_name": raw.get("node_name") or node,
            "node_role": settings.NODE_ROLE,
        }
    )
    fresh = status.updated_at is not None and (
        datetime.now(timezone.utc) - status.updated_at < _STATUS_STALE
    )
    status.running = bool(raw.get("running")) and fresh
    return status
