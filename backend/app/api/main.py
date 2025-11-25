from fastapi import APIRouter

from app.api.routes import (
    items,
    login,
    private,
    users,
    utils,
    tacacs_ng_settings,
    tacacs_configs,
    tacacs_users,
    tacacs_groups,
    tacacs_services,
    profiles,
    mavises,
    profilescripts,
    profilescriptsets,
    hosts,
    rulesets,
    rulesetscripts,
    rulesetscriptsets,
    tacacs_logs,
    tacacs_statistics,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(users.router)
api_router.include_router(utils.router)
api_router.include_router(items.router)
api_router.include_router(tacacs_ng_settings.router)
api_router.include_router(tacacs_configs.router)
api_router.include_router(tacacs_users.router)
api_router.include_router(tacacs_groups.router)
api_router.include_router(tacacs_services.router)
api_router.include_router(mavises.router)
api_router.include_router(profiles.router)
api_router.include_router(profilescripts.router)
api_router.include_router(profilescriptsets.router)
api_router.include_router(hosts.router)
api_router.include_router(rulesets.router)
api_router.include_router(rulesetscripts.router)
api_router.include_router(rulesetscriptsets.router)
api_router.include_router(tacacs_logs.router)
api_router.include_router(tacacs_statistics.router)

if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
