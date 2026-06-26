import logging
import time
import uuid
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Integer, cast, func
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.crud.tacacs_configs import reload_active_config_from_db
from app.models import (
    HaConfig,
    HaConfigPublic,
    HaConfigUpdate,
    HaNodeState,
    HaPeerNode,
    HaPeerNodeCreate,
    HaPeerNodePublic,
    HaPeerNodesPublic,
    HaPeerNodeUpdate,
    HaState,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])

_PEER_CACHE_TTL = 30  # seconds
_peers_cache: dict[str, dict] = {}  # url -> {"available": bool|None, "ts": float}


# --- helpers ---

def _get_or_create_ha_state(session: SessionDep) -> HaState:
    state = session.get(HaState, 1)
    if state is None:
        state = HaState(id=1)
        session.add(state)
        session.commit()
        session.refresh(state)
    return state


def _get_ha_config(session: SessionDep) -> HaConfig:
    cfg = session.get(HaConfig, 1)
    return cfg or HaConfig()


def _check_peers_available(peer_urls: list[str]) -> dict[str, bool | None]:
    """Return {url: available} for each URL. Results cached 30 s per URL."""
    if not settings.INTERNAL_SYNC_TOKEN:
        return {url: None for url in peer_urls}
    now = time.monotonic()
    result: dict[str, bool | None] = {}
    for url in peer_urls:
        cache = _peers_cache.setdefault(url, {"available": None, "ts": 0.0})
        if now - cache["ts"] < _PEER_CACHE_TTL:
            result[url] = cache["available"]
            continue
        try:
            with httpx.Client(timeout=5) as client:
                r = client.get(f"{url.rstrip('/')}/api/v1/utils/health-check/")
            cache["available"] = r.status_code == 200
        except Exception:
            cache["available"] = False
        cache["ts"] = now
        result[url] = cache["available"]
    return result


def _get_enabled_peers(session: SessionDep) -> list[HaPeerNode]:
    return list(session.exec(select(HaPeerNode).where(HaPeerNode.enabled == True)).all())


# --- HA info ---

@router.get("/ha-info")
def get_ha_info(_: CurrentUser, session: SessionDep) -> dict:
    """Return HA configuration and peer status for this node."""
    cfg = _get_ha_config(session)
    peers = list(session.exec(select(HaPeerNode)).all())
    peer_urls = [p.url for p in peers if p.enabled]
    availability = _check_peers_available(peer_urls)

    # Load per-peer sync state
    node_states: dict[uuid.UUID, HaNodeState] = {
        ns.peer_id: ns
        for ns in session.exec(select(HaNodeState)).all()
    }

    peers_out = []
    for p in peers:
        ns = node_states.get(p.id)
        peers_out.append({
            "id": str(p.id),
            "name": p.name,
            "url": p.url,
            "enabled": p.enabled,
            "available": availability.get(p.url) if p.enabled else None,
            "last_push_at": ns.last_push_at.isoformat() if ns and ns.last_push_at else None,
        })

    # last_sync_at: most recent push (primary) or received (standby)
    if settings.NODE_ROLE == "primary":
        push_times = [ns.last_push_at for ns in node_states.values() if ns.last_push_at]
        last_sync_ts = max(push_times) if push_times else None
    else:
        ha_state = _get_or_create_ha_state(session)
        last_sync_ts = ha_state.last_received_at

    # compat fields for old frontend / SyncToStandby component
    first_peer = peers[0] if peers else None
    peer_available_any = any(v for v in availability.values() if v is not None) if availability else None

    return {
        "node_role": settings.NODE_ROLE,
        "node_name": cfg.node_name,
        "sync_mode": cfg.sync_mode,
        "scheduler_enabled": cfg.scheduler_enabled,
        "stats_interval_minutes": cfg.stats_interval_minutes,
        "peers": peers_out,
        # backward-compat single-peer fields
        "peer_backend_url": first_peer.url if first_peer else None,
        "peer_available": peer_available_any,
        "last_sync_at": last_sync_ts.isoformat() if last_sync_ts else None,
    }


# --- HA config CRUD ---

@router.get("/config")
def get_ha_config_endpoint(
    _: CurrentUser,
    session: SessionDep,
    __: bool = Depends(get_current_active_superuser),
) -> HaConfigPublic:
    cfg = session.get(HaConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="HA config not found.")
    return HaConfigPublic.model_validate(cfg)


@router.patch("/config")
def update_ha_config(
    body: HaConfigUpdate,
    _: CurrentUser,
    session: SessionDep,
    __: bool = Depends(get_current_active_superuser),
) -> HaConfigPublic:
    if settings.NODE_ROLE == "standby":
        raise HTTPException(status_code=403, detail="Standby node is read-only.")
    cfg = session.get(HaConfig, 1)
    if cfg is None:
        raise HTTPException(status_code=404, detail="HA config not found.")
    patch = body.model_dump(exclude_unset=True)
    for k, v in patch.items():
        setattr(cfg, k, v)
    cfg.updated_at = datetime.now(timezone.utc)
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return HaConfigPublic.model_validate(cfg)


# --- Peer node CRUD ---

@router.get("/peers")
def list_peers(
    _: CurrentUser,
    session: SessionDep,
    __: bool = Depends(get_current_active_superuser),
) -> HaPeerNodesPublic:
    peers = list(session.exec(select(HaPeerNode)).all())
    return HaPeerNodesPublic(
        data=[HaPeerNodePublic.model_validate(p) for p in peers],
        count=len(peers),
    )


@router.post("/peers", status_code=201)
def create_peer(
    body: HaPeerNodeCreate,
    _: CurrentUser,
    session: SessionDep,
    __: bool = Depends(get_current_active_superuser),
) -> HaPeerNodePublic:
    if settings.NODE_ROLE == "standby":
        raise HTTPException(status_code=403, detail="Standby node is read-only.")
    peer = HaPeerNode.model_validate(body)
    session.add(peer)
    session.commit()
    session.refresh(peer)
    return HaPeerNodePublic.model_validate(peer)


@router.patch("/peers/{peer_id}")
def update_peer(
    peer_id: uuid.UUID,
    body: HaPeerNodeUpdate,
    _: CurrentUser,
    session: SessionDep,
    __: bool = Depends(get_current_active_superuser),
) -> HaPeerNodePublic:
    if settings.NODE_ROLE == "standby":
        raise HTTPException(status_code=403, detail="Standby node is read-only.")
    peer = session.get(HaPeerNode, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found.")
    patch = body.model_dump(exclude_unset=True)
    for k, v in patch.items():
        setattr(peer, k, v)
    peer.updated_at = datetime.now(timezone.utc)
    session.add(peer)
    session.commit()
    session.refresh(peer)
    # invalidate availability cache for changed URL
    _peers_cache.pop(peer.url, None)
    return HaPeerNodePublic.model_validate(peer)


@router.delete("/peers/{peer_id}", status_code=204)
def delete_peer(
    peer_id: uuid.UUID,
    _: CurrentUser,
    session: SessionDep,
    __: bool = Depends(get_current_active_superuser),
) -> None:
    if settings.NODE_ROLE == "standby":
        raise HTTPException(status_code=403, detail="Standby node is read-only.")
    peer = session.get(HaPeerNode, peer_id)
    if peer is None:
        raise HTTPException(status_code=404, detail="Peer not found.")
    _peers_cache.pop(peer.url, None)
    session.delete(peer)
    session.commit()


# --- Config push ---

@router.post("/push-config")
def push_config_to_standby(_: CurrentUser, session: SessionDep) -> dict:
    """Manually push config to all enabled standby peers (primary + manual sync only)."""
    if settings.NODE_ROLE != "primary":
        raise HTTPException(status_code=400, detail="Only the primary node can push config.")
    if not settings.INTERNAL_SYNC_TOKEN:
        raise HTTPException(status_code=400, detail="INTERNAL_SYNC_TOKEN is not configured.")

    cfg = _get_ha_config(session)
    if cfg.sync_mode != "manual":
        raise HTTPException(status_code=400, detail="Manual push only available in SYNC_MODE=manual.")

    peers = _get_enabled_peers(session)
    if not peers:
        raise HTTPException(status_code=400, detail="No enabled peer nodes configured.")

    results = []
    for peer in peers:
        url = f"{peer.url.rstrip('/')}/api/v1/sync/internal/reload-config"
        ok = False
        try:
            with httpx.Client(timeout=15) as client:
                r = client.post(url, headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN})
            ok = r.status_code == 200
            if not ok:
                log.warning("Peer %s reload returned HTTP %s: %s", peer.name, r.status_code, r.text)
            else:
                log.info("Config pushed to peer %s (%s) successfully.", peer.name, peer.url)
        except httpx.RequestError as e:
            log.warning("Could not reach peer %s: %s", peer.name, e)

        state = session.get(HaNodeState, peer.id) or HaNodeState(peer_id=peer.id)
        state.last_push_at = datetime.now(timezone.utc)
        state.last_available = ok
        session.add(state)
        results.append({"peer": peer.name, "url": peer.url, "status": "ok" if ok else "error"})

    session.commit()
    return {"results": results}


# --- Promote ---

@router.post("/promote")
def promote_to_primary(
    _: CurrentUser,
    session: SessionDep,
    __: bool = Depends(get_current_active_superuser),
) -> dict:
    """Promote this standby node to primary via pg_promote(). Superuser only."""
    if settings.NODE_ROLE != "standby":
        raise HTTPException(status_code=400, detail="Only standby nodes can be promoted.")

    try:
        lag_col = cast(
            func.extract("epoch", func.now() - func.pg_last_xact_replay_timestamp()),
            Integer,
        )
        lag_val = session.exec(select(lag_col)).one_or_none()
        lag_seconds = lag_val if lag_val is not None else None
    except Exception:
        lag_seconds = None

    try:
        session.exec(select(func.pg_promote()))
        session.commit()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"pg_promote() failed: {e}")

    # DB is now writable — update HaConfig immediately so scheduler starts correctly
    try:
        cfg = session.get(HaConfig, 1) or HaConfig(id=1)
        cfg.scheduler_enabled = True
        session.add(cfg)
        session.commit()
    except Exception:
        log.warning("Could not update HaConfig.scheduler_enabled after promotion")

    log.info("Node promoted to primary via API.")
    return {
        "status": "promoted",
        "replication_lag_seconds": lag_seconds,
        "next_steps": [
            "Update .env: NODE_ROLE=primary",
            "Restart backend: docker compose up -d backend",
            "Remove old primary from peer list in the HA UI",
            "Repoint remaining standbys' PostgreSQL replication to this node",
        ],
    }


# --- Internal endpoints (inter-node, not in OpenAPI docs) ---

@router.post("/internal/collect-stats")
def internal_collect_stats(
    request: Request,
    target_date: date = Query(default=None, alias="date"),
) -> dict:
    """Internal: parse local TACACS logs and return raw stats. Called by primary."""
    token = request.headers.get("X-Internal-Token")
    if not settings.INTERNAL_SYNC_TOKEN or token != settings.INTERNAL_SYNC_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing internal sync token.")

    import sys

    from scripts._log_stats_base import (
        get_target_date,
        parse_accounting_logs,
        parse_authentication_logs,
        parse_authorization_logs,
        to_log_datetime,
    )

    if target_date is None:
        orig_argv = sys.argv[:]
        sys.argv = sys.argv[:1]
        target_date = get_target_date()
        sys.argv = orig_argv

    log_dir = settings.TACACS_LOG_DIRECTORY
    auth_success, auth_fail = parse_authentication_logs(target_date, log_dir)
    authz_permit, authz_deny = parse_authorization_logs(target_date, log_dir)
    acct_start, acct_stop = parse_accounting_logs(target_date, log_dir)
    log_dt = to_log_datetime(target_date)

    def _counters_to_list(c1: dict, c2: dict, k1: str, k2: str) -> list[dict]:
        all_keys = set(c1.keys()) | set(c2.keys())
        return [
            {
                "username": u,
                "nas_ip": n,
                "user_source_ip": c,
                k1: c1.get((u, n, c), 0),
                k2: c2.get((u, n, c), 0),
                "log_date": log_dt.isoformat(),
            }
            for u, n, c in sorted(all_keys)
        ]

    return {
        "node_name": settings.NODE_NAME,
        "date": target_date.isoformat(),
        "authentication": _counters_to_list(auth_success, auth_fail, "success_count", "fail_count"),
        "authorization": _counters_to_list(authz_permit, authz_deny, "permit_count", "deny_count"),
        "accounting": _counters_to_list(acct_start, acct_stop, "start_count", "stop_count"),
    }


@router.post("/internal/reload-config")
def internal_reload_config(request: Request, session: SessionDep) -> dict:
    """Internal: reload tac_plus-ng config from DB on this (standby) node."""
    token = request.headers.get("X-Internal-Token")
    if not settings.INTERNAL_SYNC_TOKEN or token != settings.INTERNAL_SYNC_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid or missing internal sync token.")

    try:
        reload_active_config_from_db(session=session)
    except Exception as e:
        log.exception("HA config reload failed")
        raise HTTPException(status_code=500, detail=f"Config reload failed: {e}")

    # Only write last_received_at if DB is writable (non-replica standby)
    try:
        state = _get_or_create_ha_state(session)
        state.last_received_at = datetime.now(timezone.utc)
        session.add(state)
        session.commit()
    except Exception:
        log.debug("Could not update last_received_at (read-only replica)")

    return {"status": "reloaded"}
