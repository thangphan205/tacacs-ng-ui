"""Elect one uvicorn worker to run the background write loops (issue #372).

supervisord starts ``uvicorn --workers 4``: four processes, each running the
FastAPI lifespan. Without coordination every worker starts its own alert, stats,
ML and purge loops, so each alert fires four times and each stats run (and the
SIEM forwarding inside it) happens four times.

The runs are sequential, not concurrent, so a per-iteration transaction lock
would not help: the next worker takes it as soon as the previous one commits.
Instead one worker holds a *session-level* advisory lock for as long as it
lives, and only that worker runs the loops. The others retry every
``retry_seconds``; when the leader dies, PostgreSQL ends its session, the lock
is freed and a follower takes over.

The lock connection is kept checked out of the pool for the leader's whole
term, in autocommit mode so it never sits "idle in transaction" holding a
snapshot. It is never returned to the pool while holding the lock: on a clean
release it is unlocked first, on any error it is invalidated, which closes the
server session and with it the lock.

Known gap: if the leader's server session is killed while the worker lives on,
the worker notices at its next heartbeat, so the old and new leader may overlap
for up to ``heartbeat_seconds``.
"""

import asyncio
import logging
import os
from collections.abc import Callable

from sqlalchemy import Connection, text

from app.core.db import engine

logger = logging.getLogger(__name__)

# Two-int4 advisory keys live in a separate key space from the single-bigint
# keys that crud/ordering.py derives with hashtext(), so they cannot collide.
LOCK_CLASS_ID = 7461636  # arbitrary, app-specific; also documented in CLAUDE.md
SCHEDULER_LOCK: tuple[int, int] = (LOCK_CLASS_ID, 1)

_RETRY_SECONDS = 30.0
_HEARTBEAT_SECONDS = 30.0


def _connect() -> Connection:
    return engine.connect().execution_options(isolation_level="AUTOCOMMIT")


def _try_acquire(conn: Connection, key: tuple[int, int]) -> bool:
    return bool(
        conn.execute(
            text("SELECT pg_try_advisory_lock(:a, :b)"), {"a": key[0], "b": key[1]}
        ).scalar()
    )


def _still_held(conn: Connection, key: tuple[int, int]) -> bool:
    """Prove this session still holds the lock, not only that the socket is up."""
    return bool(
        conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_locks"
                " WHERE locktype = 'advisory' AND pid = pg_backend_pid()"
                " AND classid = :a AND objid = :b AND objsubid = 2 AND granted)"
            ),
            {"a": key[0], "b": key[1]},
        ).scalar()
    )


def _release(conn: Connection, key: tuple[int, int]) -> None:
    """Unlock and return the connection; drop it instead if that fails."""
    try:
        conn.execute(
            text("SELECT pg_advisory_unlock(:a, :b)"), {"a": key[0], "b": key[1]}
        )
        conn.close()
    except Exception:
        logger.warning("Could not release scheduler lock cleanly", exc_info=True)
        _discard(conn)


def _discard(conn: Connection) -> None:
    try:
        conn.invalidate()
        conn.close()
    except Exception:
        logger.debug("Discarding lock connection failed", exc_info=True)


async def _stop(tasks: list[asyncio.Task[None]]) -> None:
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def run_as_leader(
    start: Callable[[], list[asyncio.Task[None]]],
    *,
    key: tuple[int, int] = SCHEDULER_LOCK,
    retry_seconds: float = _RETRY_SECONDS,
    heartbeat_seconds: float = _HEARTBEAT_SECONDS,
) -> None:
    """Run ``start()``'s tasks only while this process holds the advisory lock.

    Runs until cancelled. On cancellation the started tasks are cancelled and
    the lock is released so a follower can take over at its next retry.
    """
    while True:
        conn: Connection | None = None
        try:
            conn = await asyncio.to_thread(_connect)
            acquired = await asyncio.to_thread(_try_acquire, conn, key)
        except asyncio.CancelledError:
            if conn is not None:
                _discard(conn)
            raise
        except Exception:
            logger.warning("Scheduler lock attempt failed; retrying", exc_info=True)
            if conn is not None:
                _discard(conn)
            await asyncio.sleep(retry_seconds)
            continue

        if not acquired:
            conn.close()
            await asyncio.sleep(retry_seconds)
            continue

        logger.info(
            "Worker %d holds the scheduler lock; running background loops",
            os.getpid(),
        )
        tasks: list[asyncio.Task[None]] = []
        try:
            tasks = start()
            while True:
                await asyncio.sleep(heartbeat_seconds)
                try:
                    held = await asyncio.to_thread(_still_held, conn, key)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.warning("Scheduler lock heartbeat failed", exc_info=True)
                    held = False
                if not held:
                    logger.warning(
                        "Worker %d lost the scheduler lock; stopping background loops",
                        os.getpid(),
                    )
                    break
        except BaseException:
            # Shutdown (CancelledError) or start() failing: stop, unlock, propagate.
            await _stop(tasks)
            _release(conn, key)
            raise

        await _stop(tasks)
        _discard(conn)
