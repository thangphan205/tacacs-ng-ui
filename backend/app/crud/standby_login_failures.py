"""Failed sign-ins counted on a standby, where no audit row can be written.

The sign-in throttle counts LOGIN_FAILED audit rows, but a standby's database
is a read-only replica: without this, a standby had no throttle at all, and
every LDAP guess sent to it still reached the directory and could trip its
account lockout policy.

A small SQLite file in the container's temp directory: shared by the uvicorn
workers on this node (an in-process counter would let each of the four allow
the full limit), gone with the container, and never replicated -- each
standby throttles what it sees itself. Failures here fail open: a broken temp
directory must not stop the emergency administrator signing in.
"""

import logging
import os
import sqlite3
import tempfile
import time
from datetime import timedelta

logger = logging.getLogger(__name__)

_FILENAME = "tacacs_ng_ui_standby_login_failures.sqlite3"
# Rows older than this are deleted on each write, whatever the window is.
_KEEP_SECONDS = 24 * 3600


def _path() -> str:
    return os.path.join(tempfile.gettempdir(), _FILENAME)


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_path(), timeout=5, isolation_level=None)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS failure "
        "(ts REAL NOT NULL, user_email TEXT, ip_address TEXT)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS ix_failure_ts ON failure (ts)")
    return conn


def record_failure(*, user_email: str | None, ip_address: str | None) -> None:
    now = time.time()
    try:
        conn = _connect()
        try:
            conn.execute("DELETE FROM failure WHERE ts < ?", (now - _KEEP_SECONDS,))
            conn.execute(
                "INSERT INTO failure (ts, user_email, ip_address) VALUES (?, ?, ?)",
                (now, user_email, ip_address),
            )
        finally:
            conn.close()
    except sqlite3.Error:
        logger.warning(
            "Could not record a failed sign-in on this standby", exc_info=True
        )


def count_recent_failures(
    *,
    within: timedelta,
    user_email: str | None = None,
    ip_address: str | None = None,
) -> int:
    clauses = ["ts >= ?"]
    params: list[float | str] = [time.time() - within.total_seconds()]
    if user_email is not None:
        clauses.append("user_email = ?")
        params.append(user_email)
    if ip_address is not None:
        clauses.append("ip_address = ?")
        params.append(ip_address)
    try:
        conn = _connect()
        try:
            row = conn.execute(
                f"SELECT count(*) FROM failure WHERE {' AND '.join(clauses)}",
                params,
            ).fetchone()
        finally:
            conn.close()
    except sqlite3.Error:
        logger.warning("Could not read failed sign-ins on this standby", exc_info=True)
        return 0
    return int(row[0])
