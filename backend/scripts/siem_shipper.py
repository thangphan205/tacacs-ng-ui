"""Real-time SIEM shipper — runs on every node (supervisord program).

Tails this node's tac_plus-ng log files and sends every line to the SIEM
configured under SIEM Integration in the UI. The settings are read from the
database (the replica on a standby) every few seconds, so changes apply
without a restart. See app/crud/siem_tailer.py.
"""

import logging
import os
import signal
import sys
import time
from types import FrameType

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s siem_shipper: %(message)s",
)
log = logging.getLogger(__name__)

TICK_SECONDS = float(os.environ.get("SIEM_SHIPPER_TICK_SECONDS", "1"))
CONFIG_RELOAD_SECONDS = 10.0

# Let FastAPI's prestart (migrations) finish before the first DB read.
time.sleep(10)

sys.path.insert(0, "/app")
from sqlmodel import Session  # noqa: E402

from app.core.db import engine  # noqa: E402
from app.crud.siem_tailer import LogTailer  # noqa: E402
from app.crud.tacacs_siem import SiemTarget, load_target  # noqa: E402

_stop = False


def _on_signal(_signum: int, _frame: FrameType | None) -> None:
    global _stop
    _stop = True


def main() -> None:
    signal.signal(signal.SIGTERM, _on_signal)
    signal.signal(signal.SIGINT, _on_signal)
    tailer = LogTailer()
    target: SiemTarget | None = None
    known = False  # a failed first read must not count as "disabled"
    loaded_at = float("-inf")
    log.info("SIEM shipper started")
    while not _stop:
        if time.monotonic() - loaded_at >= CONFIG_RELOAD_SECONDS:
            try:
                with Session(engine) as session:
                    new_target = load_target(session)
                if new_target != target:
                    log.info(
                        "SIEM config: %s",
                        "disabled"
                        if new_target is None
                        else f"shipping {sorted(new_target.ship)}",
                    )
                target = new_target
                known = True
            except Exception:
                # Keep the last known config while the database is unreachable.
                log.warning(
                    "Cannot read SIEM config; keeping the last one", exc_info=True
                )
            loaded_at = time.monotonic()
        if known:
            tailer.tick(target)
        time.sleep(TICK_SECONDS)
    tailer.status.running = False
    if known:
        tailer.tick(target)
    log.info("SIEM shipper stopped")


if __name__ == "__main__":
    main()
