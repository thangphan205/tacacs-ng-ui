import logging

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.api.deps import CurrentUser, SessionDep
from app.core.config import settings
from app.crud.tacacs_configs import reload_active_config_from_db

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


@router.get("/ha-info")
def get_ha_info(_: CurrentUser) -> dict:
    """Return HA configuration for this node."""
    peer_available: bool | None = None
    if settings.PEER_BACKEND_URL and settings.INTERNAL_SYNC_TOKEN:
        try:
            url = f"{settings.PEER_BACKEND_URL.rstrip('/')}/api/v1/utils/health-check/"
            with httpx.Client(timeout=5) as client:
                r = client.get(url)
            peer_available = r.status_code == 200
        except Exception:
            peer_available = False

    return {
        "node_role": settings.NODE_ROLE,
        "sync_mode": settings.SYNC_MODE,
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
        "peer_backend_url": settings.PEER_BACKEND_URL or None,
        "peer_available": peer_available,
    }


@router.post("/push-config")
def push_config_to_standby(_: CurrentUser) -> dict:
    """Manually trigger config reload on the peer (standby) node.

    Only valid on the primary node with SYNC_MODE=manual.
    """
    if settings.NODE_ROLE != "primary":
        raise HTTPException(status_code=400, detail="Only the primary node can push config.")
    if not settings.PEER_BACKEND_URL:
        raise HTTPException(status_code=400, detail="PEER_BACKEND_URL is not configured.")
    if not settings.INTERNAL_SYNC_TOKEN:
        raise HTTPException(status_code=400, detail="INTERNAL_SYNC_TOKEN is not configured.")

    url = f"{settings.PEER_BACKEND_URL.rstrip('/')}/api/v1/sync/internal/reload-config"
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(url, headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN})
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach peer node: {e}")

    if r.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Peer node returned HTTP {r.status_code}: {r.text}",
        )

    log.info("Config pushed to peer node %s successfully.", settings.PEER_BACKEND_URL)
    return {"status": "ok", "peer": settings.PEER_BACKEND_URL}


@router.post("/internal/reload-config")
def internal_reload_config(request: Request, session: SessionDep) -> dict:
    """Internal endpoint: reload tac_plus-ng config from DB on this (standby) node.

    Called by the primary node (auto or manual sync). Authenticated via shared token.
    Not exposed in OpenAPI docs — internal HA traffic only.
    """
    token = request.headers.get("X-Internal-Token")
    if not settings.INTERNAL_SYNC_TOKEN or token != settings.INTERNAL_SYNC_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing internal sync token.")

    try:
        reload_active_config_from_db(session=session)
    except Exception as e:
        log.exception("HA config reload failed")
        raise HTTPException(status_code=500, detail=f"Config reload failed: {e}")

    return {"status": "reloaded"}
