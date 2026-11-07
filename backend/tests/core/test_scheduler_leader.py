"""Only one uvicorn worker may run the background write loops (issue #372).

Every test uses its own advisory key: the session-scoped ``client`` fixture runs
the real lifespan, whose leader may already hold ``SCHEDULER_LOCK``.
"""

import asyncio
from collections.abc import Callable
from unittest.mock import patch

from sqlalchemy import Connection, text

from app.core import leader
from app.core.leader import (
    LOCK_CLASS_ID,
    _connect,
    _still_held,
    _try_acquire,
    run_as_leader,
)

FAST = {"retry_seconds": 0.05, "heartbeat_seconds": 0.05}


def _key(n: int) -> tuple[int, int]:
    return (LOCK_CLASS_ID, 900 + n)


def _unlock(conn: Connection, key: tuple[int, int]) -> None:
    conn.execute(text("SELECT pg_advisory_unlock(:a, :b)"), {"a": key[0], "b": key[1]})


def test_lock_is_exclusive_across_sessions() -> None:
    key = _key(1)
    a, b = _connect(), _connect()
    try:
        assert _try_acquire(a, key) is True
        assert _try_acquire(b, key) is False
        _unlock(a, key)
        a.close()
        assert _try_acquire(b, key) is True
    finally:
        _unlock(b, key)
        b.close()
        if not a.closed:
            a.close()


def test_lock_dies_with_its_session() -> None:
    key = _key(2)
    a, b = _connect(), _connect()
    try:
        assert _try_acquire(a, key) is True
        a.invalidate()  # what a crashed worker looks like to PostgreSQL
        assert _try_acquire(b, key) is True
    finally:
        _unlock(b, key)
        b.close()


def test_still_held_reflects_the_lock() -> None:
    key = _key(3)
    conn = _connect()
    try:
        assert _still_held(conn, key) is False
        assert _try_acquire(conn, key) is True
        assert _still_held(conn, key) is True
        _unlock(conn, key)
        assert _still_held(conn, key) is False
    finally:
        conn.close()


def _forever() -> asyncio.Task[None]:
    return asyncio.create_task(asyncio.sleep(3600))


async def _wait_for(cond: Callable[[], bool], timeout: float = 5.0) -> None:
    async with asyncio.timeout(timeout):
        while not cond():
            await asyncio.sleep(0.01)


def test_one_leader_and_failover() -> None:
    key = _key(4)
    started = {"a": 0, "b": 0}
    children: dict[str, list[asyncio.Task[None]]] = {"a": [], "b": []}

    def starter(name: str) -> Callable[[], list[asyncio.Task[None]]]:
        def start() -> list[asyncio.Task[None]]:
            started[name] += 1
            children[name] = [_forever()]
            return children[name]

        return start

    async def scenario() -> None:
        a = asyncio.create_task(run_as_leader(starter("a"), key=key, **FAST))
        await _wait_for(lambda: started["a"] == 1)
        b = asyncio.create_task(run_as_leader(starter("b"), key=key, **FAST))
        await asyncio.sleep(0.3)  # several retries and heartbeats
        assert started == {"a": 1, "b": 0}

        a.cancel()
        await asyncio.gather(a, return_exceptions=True)
        assert all(t.cancelled() for t in children["a"])

        await _wait_for(lambda: started["b"] == 1)
        b.cancel()
        await asyncio.gather(b, return_exceptions=True)
        assert all(t.cancelled() for t in children["b"])

    asyncio.run(scenario())

    # The lock was released on cancellation, not left on a pooled connection.
    conn = _connect()
    try:
        assert _try_acquire(conn, key) is True
    finally:
        _unlock(conn, key)
        conn.close()


def test_lost_lock_stops_loops_and_reelects() -> None:
    key = _key(5)
    starts: list[list[asyncio.Task[None]]] = []
    beats = {"n": 0}

    def start() -> list[asyncio.Task[None]]:
        starts.append([_forever()])
        return starts[-1]

    def flaky_still_held(_conn: Connection, _key: tuple[int, int]) -> bool:
        beats["n"] += 1
        return beats["n"] != 1  # first heartbeat reports the lock lost

    async def scenario() -> None:
        task = asyncio.create_task(run_as_leader(start, key=key, **FAST))
        await _wait_for(lambda: len(starts) == 2)
        assert all(t.cancelled() for t in starts[0])
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    with patch.object(leader, "_still_held", flaky_still_held):
        asyncio.run(scenario())
