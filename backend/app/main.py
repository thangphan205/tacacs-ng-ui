import asyncio
import logging
import subprocess
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import date

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlmodel import Session, select
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.core.db import engine
from app.crud.alert_evaluator import evaluate_all_rules
from app.crud.audit_logs import purge_old_audit_logs
from app.crud.ml_anomaly_scorer import run_daily_anomaly_scoring
from app.models import HaConfig, HaPeerNode

logger = logging.getLogger(__name__)

_PURGE_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours
_ALERT_EVAL_INTERVAL_SECONDS = 5 * 60  # 5 minutes
_ML_SCORING_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


def _seed_ha_config(session: Session) -> None:
    """Seed HaConfig and HaPeerNode from env vars on first primary startup."""
    if settings.NODE_ROLE == "standby":
        return  # replica DB is read-only; replication delivers the config
    if not session.get(HaConfig, 1):
        session.add(
            HaConfig(
                id=1,
                node_name=settings.NODE_NAME,
                sync_mode=settings.SYNC_MODE,
                scheduler_enabled=settings.SCHEDULER_ENABLED,
                stats_interval_minutes=settings.STATS_INTERVAL_MINUTES,
            )
        )
        session.commit()
    if not session.exec(select(HaPeerNode)).first():
        for url in settings.peer_urls:
            session.add(HaPeerNode(name=url, url=url))
        if settings.peer_urls:
            session.commit()


async def _audit_purge_loop() -> None:
    while True:
        await asyncio.sleep(_PURGE_INTERVAL_SECONDS)
        try:
            with Session(engine) as session:
                deleted = purge_old_audit_logs(session=session)
            if deleted:
                logger.info("Audit log purge: removed %d rows", deleted)
        except Exception:
            logger.exception("Audit log purge failed")


async def _alert_evaluation_loop() -> None:
    while True:
        await asyncio.sleep(_ALERT_EVAL_INTERVAL_SECONDS)
        try:
            with Session(engine) as session:
                evaluate_all_rules(session=session)
        except Exception:
            logger.exception("Alert evaluation failed")


async def _ml_scoring_loop() -> None:
    await asyncio.sleep(60)  # brief startup delay
    while True:
        try:
            with Session(engine) as session:
                run_daily_anomaly_scoring(session=session)
        except Exception:
            logger.exception("ML anomaly scoring failed")
        await asyncio.sleep(_ML_SCORING_INTERVAL_SECONDS)


async def _stats_collection_loop() -> None:
    await asyncio.sleep(30)  # brief startup delay
    while True:
        with Session(engine) as s:
            cfg = s.get(HaConfig, 1)
        interval = (cfg.stats_interval_minutes if cfg else settings.STATS_INTERVAL_MINUTES) * 60
        if interval <= 0:
            await asyncio.sleep(60)
            continue
        today_str = date.today().isoformat()
        scripts = [
            "/app/scripts/tacacs_logs_authentication.py",
            "/app/scripts/tacacs_logs_authorization.py",
            "/app/scripts/tacacs_logs_accounting.py",
        ]
        for script in scripts:
            try:
                proc = subprocess.run(
                    [sys.executable, script, today_str],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                if proc.returncode != 0:
                    logger.warning(
                        "Stats script %s exited %s: %s",
                        script,
                        proc.returncode,
                        proc.stderr[-500:],
                    )
            except subprocess.TimeoutExpired:
                logger.warning("Stats script %s timed out", script)
            except Exception:
                logger.exception("Stats script %s failed", script)

        # collect from peer nodes
        try:
            from app.api.routes.aaa_statistics import _collect_from_peers

            _collect_from_peers(today_str)
        except Exception:
            logger.exception("Peer stats collection failed")

        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    with Session(engine) as session:
        _seed_ha_config(session)

    cfg: HaConfig | None
    with Session(engine) as session:
        cfg = session.get(HaConfig, 1)
    scheduler_on = cfg.scheduler_enabled if cfg else settings.SCHEDULER_ENABLED
    stats_interval = (cfg.stats_interval_minutes if cfg else settings.STATS_INTERVAL_MINUTES)

    tasks = []
    if scheduler_on:
        tasks = [
            asyncio.create_task(_audit_purge_loop()),
            asyncio.create_task(_alert_evaluation_loop()),
            asyncio.create_task(_ml_scoring_loop()),
        ]
        if stats_interval > 0:
            tasks.append(asyncio.create_task(_stats_collection_loop()))
    yield
    for t in tasks:
        t.cancel()


def custom_generate_unique_id(route: APIRoute) -> str:
    return f"{route.tags[0]}-{route.name}"


if settings.SENTRY_DSN and settings.ENVIRONMENT != "local":
    sentry_sdk.init(dsn=str(settings.SENTRY_DSN), enable_tracing=True)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    generate_unique_id_function=custom_generate_unique_id,
    lifespan=lifespan,
)

# Set all CORS enabled origins
if settings.all_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.all_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)
