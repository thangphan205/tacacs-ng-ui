import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import sentry_sdk
from fastapi import FastAPI
from fastapi.routing import APIRoute
from sqlmodel import Session
from starlette.middleware.cors import CORSMiddleware

from app.api.main import api_router
from app.core.config import settings
from app.core.db import engine
from app.crud.audit_logs import purge_old_audit_logs

logger = logging.getLogger(__name__)

_PURGE_INTERVAL_SECONDS = 24 * 60 * 60  # 24 hours


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


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    task = asyncio.create_task(_audit_purge_loop())
    yield
    task.cancel()


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
