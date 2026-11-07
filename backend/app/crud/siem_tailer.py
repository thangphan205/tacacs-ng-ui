"""Real-time SIEM shipping of tac_plus-ng log files.

``scripts/siem_shipper.py`` runs one ``LogTailer`` per node (a supervisord
program, so once per container rather than once per uvicorn worker). Every
tick it reads the lines appended to today's log file of each enabled type and
sends one event per line to the configured sinks.

Offsets are kept per file in ``OFFSETS_FILE`` on the log volume, so a restart
resumes where it stopped. A file the tailer has no offset for when it starts
(or when its type is switched on) is read from its end: enabling forwarding
never replays history. A file that appears while running (a new day's file)
is read from the start. After local midnight the previous day's file is
drained to its end before it is dropped.

Delivery is at-least-once for the deciding sink: the webhook when one is set,
otherwise syslog. The offset only moves once that sink took the batch, and a
failed batch is retried with backoff before anything newer is read. With both
sinks, syslog is sent once per batch, before the webhook, and is not re-sent
while only the webhook retry is pending, so a syslog outage then drops messages.

A tick reads at most MAX_BATCHES_PER_TICK batches per type, so catching up a
large backlog never blocks config reloads, shutdown or the status file.
"""

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.config import settings
from app.core.tacacs_log_parse import parse_log_line
from app.crud import tacacs_siem
from app.crud.tacacs_siem import SiemTarget
from app.models import SIEM_TACACS_LOG_TYPES
from scripts._log_stats_base import build_log_file_path, local_today

logger = logging.getLogger(__name__)

# On the log volume so it survives container rebuilds, in a dot-directory that
# the TACACS Logs file listing skips.
OFFSETS_FILE = os.path.join(settings.TACACS_LOG_DIRECTORY, ".siem", "offsets.json")
STATUS_FILE = "/tmp/siem_shipper_status.json"

BATCH_LINES = 500
# Batches per log type per tick: bounds a tick while catching up a backlog, so
# config reloads, SIGTERM and the status file are never held up for long.
MAX_BATCHES_PER_TICK = 20
# ~500 lines of tac_plus-ng output; a longer single line is skipped.
_READ_CHUNK = 256 * 1024
_RETRY_MIN = 2.0
_RETRY_MAX = 60.0


# _ship_file results
_DONE = "done"  # read to the end
_PARTIAL = "partial"  # only an unfinished last line left
_MORE = "more"  # stopped at MAX_BATCHES_PER_TICK; continue next tick
_FAILED = "failed"  # a sink failed; retry after backoff


@dataclass
class _Pending:
    """A batch the webhook has not accepted yet; syslog already has it."""

    log_type: str
    new_offset: int
    inode: int
    events: list[dict[str, Any]]
    syslog_ok: bool


@dataclass
class _Status:
    running: bool = True
    enabled: bool = False
    last_event_at: datetime | None = None
    events_sent: dict[str, int] = field(default_factory=dict)
    last_error: str | None = None
    last_error_at: datetime | None = None

    def error(self, message: str) -> None:
        self.last_error = message
        self.last_error_at = datetime.now(timezone.utc)

    def clear_error(self) -> None:
        self.last_error = None
        self.last_error_at = None

    def to_json(self) -> dict[str, Any]:
        def iso(d: datetime | None) -> str | None:
            return d.isoformat() if d else None

        return {
            "node_name": tacacs_siem.node_name(),
            "running": self.running,
            "enabled": self.enabled,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "last_event_at": iso(self.last_event_at),
            "events_sent": self.events_sent,
            "last_error": self.last_error,
            "last_error_at": iso(self.last_error_at),
        }


class LogTailer:
    def __init__(
        self,
        *,
        log_dir: str = settings.TACACS_LOG_DIRECTORY,
        offsets_path: str = OFFSETS_FILE,
        status_path: str | None = STATUS_FILE,
        today: Callable[[], date] = local_today,
        clock: Callable[[], float] = time.monotonic,
        client: httpx.Client | None = None,
    ) -> None:
        self._log_dir = log_dir if log_dir.endswith("/") else log_dir + "/"
        self._offsets_path = offsets_path
        self._status_path = status_path
        self._today = today
        self._clock = clock
        self._client = client
        self._client_verify: bool | None = None
        # path -> {"type", "offset", "inode"}
        self._state: dict[str, dict[str, Any]] = self._load_offsets()
        self._dirty = False
        # Types read at least once since start / since switched on. Until then
        # a file without an offset starts at its end.
        self._primed: set[str] = set()
        self._pending: dict[str, _Pending] = {}
        self._retry_at = 0.0
        self._retry_delay = _RETRY_MIN
        self.status = _Status()

    # --- persistence ----------------------------------------------------------

    def _load_offsets(self) -> dict[str, dict[str, Any]]:
        try:
            with open(self._offsets_path) as f:
                data = json.load(f)
            return {
                p: v
                for p, v in data.items()
                if isinstance(v, dict) and {"type", "offset", "inode"} <= v.keys()
            }
        except (OSError, ValueError):
            return {}

    def _save_offsets(self) -> None:
        if not self._dirty:
            return
        tmp = f"{self._offsets_path}.tmp"
        try:
            os.makedirs(os.path.dirname(self._offsets_path) or ".", exist_ok=True)
            with open(tmp, "w") as f:
                json.dump(self._state, f)
            os.replace(tmp, self._offsets_path)
            self._dirty = False
        except OSError as e:
            self.status.error(f"cannot save offsets: {e}")
            logger.warning("Cannot save SIEM offsets to %s", self._offsets_path)

    def _write_status(self) -> None:
        if not self._status_path:
            return
        tmp = f"{self._status_path}.tmp"
        try:
            with open(tmp, "w") as f:
                json.dump(self.status.to_json(), f)
            os.replace(tmp, self._status_path)
        except OSError:
            logger.debug("Cannot write SIEM status file", exc_info=True)

    def _set(self, path: str, log_type: str, offset: int, inode: int) -> None:
        new = {"type": log_type, "offset": offset, "inode": inode}
        if self._state.get(path) != new:
            self._state[path] = new
            self._dirty = True

    def _drop(self, path: str) -> None:
        if self._state.pop(path, None) is not None:
            self._dirty = True
        self._pending.pop(path, None)

    # --- main entry -------------------------------------------------------------

    def tick(self, target: SiemTarget | None) -> None:
        """Ship what was appended since the last tick. Never raises."""
        try:
            self._tick(target)
        except Exception as e:
            logger.exception("SIEM shipper tick failed")
            self.status.error(f"internal error: {e}")
        self._save_offsets()
        self._write_status()

    def _tick(self, target: SiemTarget | None) -> None:
        self.status.enabled = target is not None
        enabled = (
            {t for t in SIEM_TACACS_LOG_TYPES if target.ships(t)} if target else set()
        )
        # Forget everything about switched-off types, so switching one back on
        # starts at the end of its file instead of replaying the gap.
        for path, st in list(self._state.items()):
            if st["type"] not in enabled:
                self._drop(path)
        self._primed &= enabled
        if target is None or not enabled:
            return
        if self._clock() < self._retry_at:
            return  # a sink just failed: read nothing newer until the retry

        today = self._today()
        for log_type in sorted(enabled):
            if self._clock() < self._retry_at:
                break  # failed for an earlier type; don't pay its timeout again
            self._ship_type(target, log_type, today)
            self._primed.add(log_type)

    def _ship_type(self, target: SiemTarget, log_type: str, today: date) -> None:
        today_path = build_log_file_path(today, log_type, self._log_dir)
        yesterday_path = build_log_file_path(
            today - timedelta(days=1), log_type, self._log_dir
        )
        # Offsets of older files are useless now.
        for path, st in list(self._state.items()):
            if st["type"] == log_type and path not in (today_path, yesterday_path):
                self._drop(path)

        # Drain yesterday's file first, but only if it was being tailed. Then
        # today's file was missed only while this process was down, so read it
        # from the start even before the type is primed.
        tailing = yesterday_path in self._state
        if tailing:
            result = self._ship_file(target, log_type, yesterday_path, from_start=True)
            if result in (_FAILED, _MORE):
                return  # keep order: nothing from today before yesterday is done
            # Done, or only a line tac_plus-ng never finished: once today's file
            # exists nothing more will be appended to yesterday's.
            if os.path.exists(today_path):
                self._drop(yesterday_path)
        self._ship_file(target, log_type, today_path, from_start=tailing)

    def _ship_file(
        self, target: SiemTarget, log_type: str, path: str, *, from_start: bool
    ) -> str:
        """Ship new lines of one file: _DONE, _PARTIAL, _MORE or _FAILED."""
        try:
            st = os.stat(path)
        except OSError:
            return _DONE
        inode = st.st_ino

        pending = self._pending.get(path)
        if pending is not None:
            if not self._deliver_pending(target, path, pending):
                return _FAILED

        prev = self._state.get(path)
        if prev is None:
            # Unknown file: at start (or when the type was just enabled) skip
            # what is already there; afterwards it is a new file, read it all.
            start = 0 if from_start or log_type in self._primed else st.st_size
            self._set(path, log_type, start, inode)
            prev = self._state[path]
        offset = int(prev["offset"])
        if prev["inode"] != inode or st.st_size < offset:
            offset = 0  # replaced or truncated
            self._set(path, log_type, 0, inode)

        for _ in range(MAX_BATCHES_PER_TICK):
            if offset >= st.st_size:
                return _DONE
            lines, new_offset = _read_lines(path, offset, BATCH_LINES)
            if new_offset == offset:
                return _PARTIAL  # only an unfinished line left
            if not self._send_batch(target, log_type, path, lines, new_offset, inode):
                return _FAILED
            offset = new_offset
        return _DONE if offset >= st.st_size else _MORE

    # --- sending ----------------------------------------------------------------

    def _send_batch(
        self,
        target: SiemTarget,
        log_type: str,
        path: str,
        lines: list[str],
        new_offset: int,
        inode: int,
    ) -> bool:
        parsed = [(line, parse_log_line(log_type, line)) for line in lines]
        syslog_ok = True
        if target.syslog_host:
            msgs = [
                tacacs_siem.format_tacacs_syslog(log_type, e, ln) for ln, e in parsed
            ]
            error = tacacs_siem.send_syslog(target, msgs)
            if error:
                syslog_ok = False
                self.status.error(error)
                if not target.webhook_url:
                    # Syslog is the only destination: hold the position and
                    # retry, as for the webhook. (With a webhook as well, the
                    # webhook decides; re-sending to it would duplicate.)
                    self._backoff(f"syslog: {error}", path)
                    return False
        if target.webhook_url:
            events = [tacacs_siem.tacacs_hec(log_type, e, ln) for ln, e in parsed]
            pending = _Pending(log_type, new_offset, inode, events, syslog_ok)
            self._pending[path] = pending
            return self._deliver_pending(target, path, pending)
        self._delivered(path, log_type, new_offset, inode, len(lines), clean=True)
        return True

    def _deliver_pending(self, target: SiemTarget, path: str, p: _Pending) -> bool:
        if target.webhook_url:
            error = tacacs_siem.send_webhook(target, p.events, self._http(target))
            if error:
                self.status.error(f"webhook: {error}")
                self._backoff(f"webhook: {error}", path)
                return False
        del self._pending[path]
        self._delivered(
            path, p.log_type, p.new_offset, p.inode, len(p.events), clean=p.syslog_ok
        )
        return True

    def _backoff(self, error: str, path: str) -> None:
        self._retry_at = self._clock() + self._retry_delay
        logger.warning(
            "SIEM forwarding failed (%s); retrying %s in %.0fs",
            error,
            path,
            self._retry_delay,
        )
        self._retry_delay = min(self._retry_delay * 2, _RETRY_MAX)

    def _delivered(
        self,
        path: str,
        log_type: str,
        offset: int,
        inode: int,
        count: int,
        *,
        clean: bool,
    ) -> None:
        self._retry_delay = _RETRY_MIN
        if clean:
            self.status.clear_error()  # every sink took this batch
        self._committed(path, log_type, offset, inode, count)

    def _committed(
        self, path: str, log_type: str, offset: int, inode: int, count: int
    ) -> None:
        self._set(path, log_type, offset, inode)
        if count:
            sent = self.status.events_sent
            sent[log_type] = sent.get(log_type, 0) + count
            self.status.last_event_at = datetime.now(timezone.utc)

    def _http(self, target: SiemTarget) -> httpx.Client:
        if self._client is None or self._client_verify != target.webhook_verify_tls:
            if self._client is not None:
                self._client.close()
            self._client = httpx.Client(
                verify=target.webhook_verify_tls, timeout=tacacs_siem.HTTP_TIMEOUT
            )
            self._client_verify = target.webhook_verify_tls
        return self._client


def _read_lines(path: str, offset: int, max_lines: int) -> tuple[list[str], int]:
    """Complete lines from ``offset``; the offset after the last one read."""
    try:
        with open(path, "rb") as f:
            f.seek(offset)
            chunk = f.read(_READ_CHUNK)
    except OSError:
        return [], offset
    lines: list[str] = []
    pos = 0
    while len(lines) < max_lines:
        nl = chunk.find(b"\n", pos)
        if nl < 0:
            break
        raw = chunk[pos:nl].decode("utf-8", errors="replace").rstrip("\r")
        if raw.strip():
            lines.append(raw)
        pos = nl + 1
    if pos == 0 and len(chunk) >= _READ_CHUNK:
        # A single line longer than the chunk: skip it rather than stall.
        return [], offset + len(chunk)
    return lines, offset + pos


def read_status(path: str = STATUS_FILE) -> dict[str, Any] | None:
    try:
        with open(path) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except (OSError, ValueError):
        return None
