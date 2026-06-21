from fastapi import APIRouter

from app.api.routes import (
    aaa_statistics,
    accounting_statistics,
    admin_auth,
    alert_events,
    alert_rules,
    anomaly_detection,
    audit_logs,
    authentication_statistics,
    authorization_statistics,
    configuration_options,
    hosts,
    items,
    login,
    mavises,
    notification_channels,
    oauth,
    passkeys,
    private,
    profiles,
    profilescripts,
    profilescriptsets,
    rulesets,
    rulesetscripts,
    rulesetscriptsets,
    sync,
    tacacs_configs,
    tacacs_groups,
    tacacs_logs,
    tacacs_ng_settings,
    tacacs_services,
    tacacs_users,
    users,
    utils,
)
from app.core.config import settings

api_router = APIRouter()
api_router.include_router(login.router)
api_router.include_router(oauth.router)
api_router.include_router(passkeys.router)
api_router.include_router(admin_auth.router)
api_router.include_router(admin_auth.status_router)
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
api_router.include_router(audit_logs.router)
api_router.include_router(tacacs_logs.router)
api_router.include_router(configuration_options.router)
api_router.include_router(authentication_statistics.router)
api_router.include_router(authorization_statistics.router)
api_router.include_router(accounting_statistics.router)
api_router.include_router(aaa_statistics.router)
api_router.include_router(alert_rules.router)
api_router.include_router(notification_channels.router)
api_router.include_router(alert_events.router)
api_router.include_router(anomaly_detection.router)
api_router.include_router(sync.router)


if settings.ENVIRONMENT == "local":
    api_router.include_router(private.router)
