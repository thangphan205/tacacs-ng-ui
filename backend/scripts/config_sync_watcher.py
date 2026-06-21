"""HA config sync watcher — runs on standby node in auto-sync mode.

Polls the local (replicated) DB for active TacacsConfig changes and
regenerates tac_plus-ng.cfg + reloads the daemon when a change is detected.

Exits immediately if NODE_ROLE != standby or SYNC_MODE != auto.
"""
import logging
import os
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s config_sync_watcher: %(message)s",
)
log = logging.getLogger(__name__)

NODE_ROLE = os.environ.get("NODE_ROLE", "primary")
SYNC_MODE = os.environ.get("SYNC_MODE", "auto")
POLL_INTERVAL = int(os.environ.get("SYNC_WATCHER_INTERVAL", "10"))

if NODE_ROLE != "standby" or SYNC_MODE != "auto":
    log.info("Not in standby+auto mode (NODE_ROLE=%s, SYNC_MODE=%s). Exiting.", NODE_ROLE, SYNC_MODE)
    sys.exit(0)

# Delay startup to let FastAPI and DB connection initialize
time.sleep(15)

# Import app modules after env check so non-HA deployments pay no startup cost
sys.path.insert(0, "/app")
from sqlmodel import Session, select  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.crud.tacacs_configs import reload_active_config_from_db  # noqa: E402
from app.models import TacacsConfig  # noqa: E402

log.info("Config sync watcher started. Polling every %ds.", POLL_INTERVAL)

last_seen: str | None = None

while True:
    try:
        with Session(engine) as session:
            active = session.exec(
                select(TacacsConfig).where(TacacsConfig.active == True)  # noqa: E712
            ).first()

            if active is not None:
                version = f"{active.id}:{active.updated_at}"
                if last_seen is not None and version != last_seen:
                    log.info("Active config changed — regenerating and reloading tac_plus-ng.")
                    reload_active_config_from_db(session=session)
                last_seen = version

    except Exception:
        log.exception("Error in config sync watcher loop")

    time.sleep(POLL_INTERVAL)
