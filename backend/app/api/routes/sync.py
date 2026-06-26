import logging
import time
from datetime import date, datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Integer, cast, func
from sqlmodel import select

from app.api.deps import CurrentUser, SessionDep, get_current_active_superuser
from app.core.config import settings
from app.crud.tacacs_configs import reload_active_config_from_db
from app.models import HaState

log = logging.getLogger(__name__)

router = APIRouter(prefix="/sync", tags=["sync"])


def _get_or_create_ha_state(session: SessionDep) -> HaState:
    state = session.get(HaState, 1)
    if state is None:
        state = HaState(id=1)
        session.add(state)
        session.commit()
        session.refresh(state)
    return state

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
    ha_state = _get_or_create_ha_state(session)

    if settings.NODE_ROLE == "primary":
        last_sync_ts = ha_state.last_push_at
    else:
        last_sync_ts = ha_state.last_received_at

    return {
        "node_role": settings.NODE_ROLE,
        "sync_mode": settings.SYNC_MODE,
        "scheduler_enabled": settings.SCHEDULER_ENABLED,
        "peer_backend_url": settings.PEER_BACKEND_URL or None,
        "peer_available": peer_available,
        "last_sync_at": last_sync_ts.isoformat() if last_sync_ts else None,
    }


@router.post("/push-config")
def push_config_to_standby(_: CurrentUser, session: SessionDep) -> dict:
    """Manually trigger config reload on the peer (standby) node.

    Only valid on the primary node with SYNC_MODE=manual.
    """
    if settings.NODE_ROLE != "primary":
        raise HTTPException(
            status_code=400, detail="Only the primary node can push config."
        )
    if not settings.PEER_BACKEND_URL:
        raise HTTPException(
            status_code=400, detail="PEER_BACKEND_URL is not configured."
        )
    if not settings.INTERNAL_SYNC_TOKEN:
        raise HTTPException(
            status_code=400, detail="INTERNAL_SYNC_TOKEN is not configured."
        )

    url = f"{settings.PEER_BACKEND_URL.rstrip('/')}/api/v1/sync/internal/reload-config"
    try:
        with httpx.Client(timeout=15) as client:
            r = client.post(
                url, headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN}
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Could not reach peer node: {e}")

    if r.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Peer node returned HTTP {r.status_code}: {r.text}",
        )

    state = _get_or_create_ha_state(session)
    state.last_push_at = datetime.now(timezone.utc)
    session.add(state)
    session.commit()

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
        raise HTTPException(
            status_code=400, detail="Only standby nodes can be promoted."
        )

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


@router.post("/internal/collect-stats")
def internal_collect_stats(
    request: Request,
    target_date: date = Query(default=None, alias="date"),
) -> dict:
    """Internal endpoint: parse local TACACS logs and return raw aggregated stats.

    Called by the primary node to collect stats from each peer (standby) node.
    Does NOT write to DB — primary is the sole writer.
    Authenticated via X-Internal-Token.
    """
    token = request.headers.get("X-Internal-Token")
    if not settings.INTERNAL_SYNC_TOKEN or token != settings.INTERNAL_SYNC_TOKEN:
        raise HTTPException(
            status_code=403, detail="Invalid or missing internal sync token."
        )

    import sys

    from scripts._log_stats_base import (
        get_target_date,
        parse_accounting_logs,
        parse_authentication_logs,
        parse_authorization_logs,
        to_log_datetime,
    )

    if target_date is None:
        # Temporarily inject no-arg so get_target_date() uses yesterday
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
        "authentication": _counters_to_list(
            auth_success, auth_fail, "success_count", "fail_count"
        ),
        "authorization": _counters_to_list(
            authz_permit, authz_deny, "permit_count", "deny_count"
        ),
        "accounting": _counters_to_list(
            acct_start, acct_stop, "start_count", "stop_count"
        ),
    }


@router.post("/internal/reload-config")
def internal_reload_config(request: Request, session: SessionDep) -> dict:
    """Internal endpoint: reload tac_plus-ng config from DB on this (standby) node.

    Called by the primary node (auto or manual sync). Authenticated via shared token.
    Not exposed in OpenAPI docs — internal HA traffic only.
    """
    token = request.headers.get("X-Internal-Token")
    if not settings.INTERNAL_SYNC_TOKEN or token != settings.INTERNAL_SYNC_TOKEN:
        raise HTTPException(
            status_code=403, detail="Invalid or missing internal sync token."
        )

    try:
        reload_active_config_from_db(session=session)
    except Exception as e:
        log.exception("HA config reload failed")
        raise HTTPException(status_code=500, detail=f"Config reload failed: {e}")

    state = _get_or_create_ha_state(session)
    state.last_received_at = datetime.now(timezone.utc)
    session.add(state)
    session.commit()

    return {"status": "reloaded"}
