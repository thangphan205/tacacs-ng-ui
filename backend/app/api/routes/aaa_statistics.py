import logging
import subprocess
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api.deps import SessionDep, get_current_active_superuser, get_current_user
from app.core.config import settings
from app.core.db import engine
from app.crud import aaa_statistics
from app.models import (
    AaaStatisticsDateRangePublic,
    AaaStatisticsTodayPublic,
    AuthenticationStatistics,
    AuthorizationStatistics,
    AccountingStatistics,
)

log = logging.getLogger(__name__)

router = APIRouter(prefix="/aaa_statistics", tags=["aaa_statistics"])


@router.get(
    "/nodes/",
    dependencies=[Depends(get_current_user)],
)
def list_aaa_nodes(session: SessionDep) -> list[str]:
    """Return distinct node_name values present in AAA statistics tables."""
    return aaa_statistics.get_distinct_node_names(session)


@router.get(
    "/today/",
    dependencies=[Depends(get_current_user)],
    response_model=AaaStatisticsTodayPublic,
)
def read_aaa_statistics(
    session: SessionDep,
    node_name: str | None = None,
) -> Any:
    """
    Retrieve aaa_statistics.
    """

    return_statistics = {}
    return_statistics.update(
        aaa_statistics.get_last_7_days_statistics(
            session=session,
            node_name=node_name,
        )
    )

    return_statistics.update(
        aaa_statistics.process_today_authentication_statistics(
            session=session,
        )
    )

    return return_statistics


@router.get(
    "/range/",
    dependencies=[Depends(get_current_user)],
    response_model=AaaStatisticsDateRangePublic,
)
def read_aaa_statistics_range(
    session: SessionDep,
    skip: int = 0,
    limit: int = 5,
    range_date: str | None = None,
    node_name: str | None = None,
) -> Any:
    """
    Retrieve aaa_statistics.
    """

    if range_date:
        try:
            start_date_str, end_date_str = range_date.split(",")
            start_date = datetime.fromisoformat(start_date_str)
            # Combine end date with max time to include the whole day
            end_date = datetime.combine(
                datetime.fromisoformat(end_date_str).date(), time.max
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid range_date format. Expected 'YYYY-MM-DD,YYYY-MM-DD'.",
            )
    else:
        # Default to last 7 days ending today
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=7)

    return_statistics = {}
    return_statistics.update(
        aaa_statistics.get_date_range_statistics(
            session=session,
            start_date=start_date,
            end_date=end_date,
            node_name=node_name,
        )
    )
    return_statistics.update(
        aaa_statistics.process_authentication_statistics(
            session=session,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
            node_name=node_name,
        )
    )
    return_statistics.update(
        aaa_statistics.process_authorization_statistics(
            session=session,
            start_date=start_date,
            end_date=end_date,
            skip=skip,
            limit=limit,
            node_name=node_name,
        )
    )

    return return_statistics


def _upsert_peer_stats(session: Session, data: dict) -> None:
    """Write stats returned by a peer's collect-stats endpoint into the local DB."""
    from datetime import datetime as dt
    from sqlmodel import select as sel

    peer_node = data.get("node_name", "unknown")

    for row in data.get("authentication", []):
        log_dt = dt.fromisoformat(row["log_date"])
        stmt = sel(AuthenticationStatistics).where(
            AuthenticationStatistics.username == row["username"],
            AuthenticationStatistics.nas_ip == row["nas_ip"],
            AuthenticationStatistics.user_source_ip == row["user_source_ip"],
            AuthenticationStatistics.log_date == log_dt,
            AuthenticationStatistics.node_name == peer_node,
        )
        obj = session.exec(stmt).first()
        if obj:
            obj.success_count = row["success_count"]
            obj.fail_count = row["fail_count"]
        else:
            obj = AuthenticationStatistics(
                username=row["username"],
                nas_ip=row["nas_ip"],
                user_source_ip=row["user_source_ip"],
                success_count=row["success_count"],
                fail_count=row["fail_count"],
                log_date=log_dt,
                node_name=peer_node,
            )
        session.add(obj)

    for row in data.get("authorization", []):
        log_dt = dt.fromisoformat(row["log_date"])
        stmt = sel(AuthorizationStatistics).where(
            AuthorizationStatistics.username == row["username"],
            AuthorizationStatistics.nas_ip == row["nas_ip"],
            AuthorizationStatistics.user_source_ip == row["user_source_ip"],
            AuthorizationStatistics.log_date == log_dt,
            AuthorizationStatistics.node_name == peer_node,
        )
        obj = session.exec(stmt).first()
        if obj:
            obj.permit_count = row["permit_count"]
            obj.deny_count = row["deny_count"]
        else:
            obj = AuthorizationStatistics(
                username=row["username"],
                nas_ip=row["nas_ip"],
                user_source_ip=row["user_source_ip"],
                permit_count=row["permit_count"],
                deny_count=row["deny_count"],
                log_date=log_dt,
                node_name=peer_node,
            )
        session.add(obj)

    for row in data.get("accounting", []):
        log_dt = dt.fromisoformat(row["log_date"])
        stmt = sel(AccountingStatistics).where(
            AccountingStatistics.username == row["username"],
            AccountingStatistics.nas_ip == row["nas_ip"],
            AccountingStatistics.user_source_ip == row["user_source_ip"],
            AccountingStatistics.log_date == log_dt,
            AccountingStatistics.node_name == peer_node,
        )
        obj = session.exec(stmt).first()
        if obj:
            obj.start_count = row["start_count"]
            obj.stop_count = row["stop_count"]
        else:
            obj = AccountingStatistics(
                username=row["username"],
                nas_ip=row["nas_ip"],
                user_source_ip=row["user_source_ip"],
                start_count=row["start_count"],
                stop_count=row["stop_count"],
                log_date=log_dt,
                node_name=peer_node,
            )
        session.add(obj)

    session.commit()


def _collect_from_peers(date_str: str | None) -> dict[str, Any]:
    """Call each peer's internal collect-stats endpoint and upsert results."""
    peer_urls = [u.strip() for u in settings.PEER_NODES.split(",") if u.strip()]
    if not peer_urls and settings.PEER_BACKEND_URL:
        peer_urls = [settings.PEER_BACKEND_URL]

    if not peer_urls:
        return {}

    if not settings.INTERNAL_SYNC_TOKEN:
        log.warning("INTERNAL_SYNC_TOKEN not set — skipping peer stats collection.")
        return {}

    peer_results: dict[str, Any] = {}
    params = {"date": date_str} if date_str else {}

    for url in peer_urls:
        endpoint = f"{url.rstrip('/')}/api/v1/sync/internal/collect-stats"
        try:
            with httpx.Client(timeout=60) as client:
                resp = client.post(
                    endpoint,
                    params=params,
                    headers={"X-Internal-Token": settings.INTERNAL_SYNC_TOKEN},
                )
        except httpx.RequestError as e:
            log.warning("Peer %s collect-stats request failed: %s", url, e)
            peer_results[url] = {"error": str(e)}
            continue

        if resp.status_code != 200:
            log.warning("Peer %s collect-stats returned HTTP %s", url, resp.status_code)
            peer_results[url] = {"error": f"HTTP {resp.status_code}"}
            continue

        data = resp.json()
        peer_node = data.get("node_name", url)
        log.info("Received stats from peer node '%s' (%s)", peer_node, url)

        with Session(engine) as session:
            _upsert_peer_stats(session, data)

        peer_results[url] = {"node_name": peer_node, "status": "ok"}

    return peer_results


@router.post(
    "/run/",
    dependencies=[Depends(get_current_active_superuser)],
)
def run_aaa_statistics(date: str | None = None) -> Any:
    """Manually trigger AAA statistics scripts for a given date (YYYY-MM-DD) or yesterday.

    On the primary node (SCHEDULER_ENABLED=true), also collects stats from all peer nodes
    configured in PEER_NODES.
    """
    scripts = [
        "/app/scripts/tacacs_logs_authentication.py",
        "/app/scripts/tacacs_logs_authorization.py",
        "/app/scripts/tacacs_logs_accounting.py",
    ]
    results: dict[str, Any] = {}
    args = [date] if date else []
    for script in scripts:
        name = Path(script).stem
        try:
            proc = subprocess.run(
                [sys.executable, script, *args],
                capture_output=True,
                text=True,
                timeout=120,
            )
            results[name] = {
                "returncode": proc.returncode,
                "stdout": proc.stdout[-2000:] if proc.stdout else "",
                "stderr": proc.stderr[-1000:] if proc.stderr else "",
            }
        except subprocess.TimeoutExpired:
            results[name] = {"returncode": -1, "error": "timeout"}
        except Exception as e:
            results[name] = {"returncode": -1, "error": str(e)}

    # Collect stats from peer nodes (primary only)
    if settings.SCHEDULER_ENABLED:
        peer_results = _collect_from_peers(date)
        if peer_results:
            results["peers"] = peer_results

    return results
