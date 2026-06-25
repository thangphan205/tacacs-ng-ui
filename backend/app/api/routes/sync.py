import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import Integer, cast, func
from sqlmodel import col, select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.crud.tacacs_configs import reload_active_config_from_db
from app.models import TacacsConfig

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])

_peer_cache: dict = {"available": None, "ts": 0.0}
_PEER_CACHE_TTL = 30  # seconds


def _check_peer_available() -> bool | None:
    if not (settings.PEER_BACKEND_URL and settings.INTERNAL_SYNC_TOKEN):
        return None
    now = time.monotonic()
    if now - _peer_cache["ts"] < _PEER_CACHE_TTL:
        return _peer_cache["available"]
    try:
        url = f"{settings.PEER_BACKEND_URL.rstrip('/')}/api/v1/utils/health-check/"
        with httpx.Client(timeout=5) as client:
            r = client.get(url)
        result: bool | None = r.status_code == 200
    except Exception:
        result = False
    _peer_cache["available"] = result
    _peer_cache["ts"] = now
    return result


@router.get("/ha-info")
def get_ha_info(_: CurrentUser, session: SessionDep) -> dict:
    """Return HA configuration for this node."""
    peer_available = _check_peer_available()

    active_cfg = session.exec(
        select(TacacsConfig)
        .where(TacacsConfig.active == True)  # noqa: E712
        .order_by(col(TacacsConfig.updated_at).desc())
    ).first()
    last_sync_at = active_cfg.updated_at.isoformat() if active_cfg else None

    return {
        "node_role": settings.NODE_ROLE,
        "sync_mode": settings.SYNC_MODE,
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
        "peer_backend_url": settings.PEER_BACKEND_URL or None,
        "peer_available": peer_available,
        "last_sync_at": last_sync_at,
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


@router.post("/promote")
def promote_to_primary(
    _: CurrentUser,
    session: SessionDep,
    __: bool = Depends(get_current_active_superuser),
) -> dict:
    """Promote this standby node to primary via pg_promote().

    Superuser only. Only valid on NODE_ROLE=standby.
    After success, update .env (NODE_ROLE=primary, SCHEDULER_ENABLED=true) and restart backend.
    """
    if settings.NODE_ROLE != "standby":
        raise HTTPException(status_code=400, detail="Only standby nodes can be promoted.")

    try:
        lag_col = cast(
            func.extract("epoch", func.now() - func.pg_last_xact_replay_timestamp()),
            Integer,
        )
        lag_val = session.exec(select(lag_col)).one_or_none()
        lag_seconds = int(lag_val) if lag_val is not None else None
    except Exception:
        lag_seconds = None

    try:
        session.exec(select(func.pg_promote()))
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pg_promote() failed: {e}")

    log.info("Node promoted to primary via API.")
    return {
        "status": "promoted",
        "replication_lag_seconds": lag_seconds,
        "next_steps": [
            "Update .env: NODE_ROLE=primary",
            "Update .env: SCHEDULER_ENABLED=true",
            "Run: docker compose up -d backend",
        ],
    }


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
