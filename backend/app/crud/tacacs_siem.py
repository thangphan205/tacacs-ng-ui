"""Forward TACACS+ statistics records to a SIEM (HTTP webhook and/or syslog).

What is sent is one record per (user, device, source, result) for a day, from
each statistics run (scripts/tacacs_logs_*.py), not individual events.

Syslog messages follow RFC 5424 so receivers get a timestamp and the node as
hostname (#373). Over TCP each message ends with LF (RFC 6587 non-transparent
framing), which is what Graylog's and most collectors' default TCP inputs
split on; the stdlib SysLogHandler ends them with NUL instead, which those
inputs silently drop.
"""

import logging
import re
import socket
import threading
import time
from datetime import datetime, timezone

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

APP_NAME = "tacacs-ng"
# facility user (1) * 8 + severity informational (6)
_PRI = 14
_CONNECT_TIMEOUT = 3.0
# After a failed connect or send, skip syslog for this long instead of paying
# the connect timeout once per record.
_BACKOFF_SECONDS = 60.0

_UNSAFE = re.compile(r"[\s\x00-\x1f\x7f]+")
_HOSTNAME_UNSAFE = re.compile(r"[^\x21-\x7e]")


def forward_tacacs_event_to_siem(
    log_type: str,
    username: str,
    nas_ip: str,
    client_ip: str,
    result: str,
    timestamp: float,
    *,
    node_name: str | None = None,
    background: bool = True,
) -> None:
    """Forward one statistics record to SIEM via HTTP webhook and/or syslog.

    ``timestamp`` is the start of the day the record covers. ``node_name`` is
    the syslog HOSTNAME (defaults to ``NODE_NAME``). background=False for
    batch scripts where daemon threads would be killed on exit.
    """
    if not settings.SIEM_FORWARD_TACACS_EVENTS:
        return

    def _send() -> None:
        _send_http(log_type, username, nas_ip, client_ip, result, timestamp)
        _send_syslog(
            log_type, username, nas_ip, client_ip, result, timestamp, node_name
        )

    if background:
        threading.Thread(target=_send, daemon=True).start()
    else:
        _send()


def _send_http(
    log_type: str,
    username: str,
    nas_ip: str,
    client_ip: str,
    result: str,
    timestamp: float,
) -> None:
    if not settings.SIEM_WEBHOOK_URL:
        return
    payload = {
        "time": timestamp,
        "event": {
            "type": log_type,
            "username": username,
            "nas_ip": nas_ip,
            "client_ip": client_ip,
            "result": result,
        },
        "sourcetype": f"tacacs-ng:{log_type}",
    }
    headers: dict[str, str] = {}
    if settings.SIEM_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Splunk {settings.SIEM_WEBHOOK_TOKEN}"
    try:
        httpx.post(settings.SIEM_WEBHOOK_URL, json=payload, headers=headers, timeout=3)  # type: ignore[arg-type]
    except Exception:
        logger.warning("Failed to forward TACACS event to SIEM webhook", exc_info=True)


def _value(v: str) -> str:
    """A key=value value: no whitespace or control characters, never empty."""
    return _UNSAFE.sub("_", v) or "-"


def _hostname(name: str | None) -> str:
    """RFC 5424 HOSTNAME: 1-255 printable US-ASCII, no spaces; NILVALUE if none."""
    cleaned = _HOSTNAME_UNSAFE.sub("-", (name or "").strip())[:255]
    return cleaned or "-"


def format_syslog_message(
    log_type: str,
    username: str,
    nas_ip: str,
    client_ip: str,
    result: str,
    timestamp: float,
    node_name: str | None,
    *,
    now: datetime | None = None,
) -> str:
    """One RFC 5424 message, without framing.

    The header TIMESTAMP is when the record was sent; ``ts=`` in the body is the
    start of the day the record summarises.
    """
    sent = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    header_ts = sent.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    day_ts = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    msgid = _value(log_type)[:32]
    body = (
        f"type={_value(log_type)} ts={day_ts} username={_value(username)} "
        f"nas_ip={_value(nas_ip)} client_ip={_value(client_ip)} "
        f"result={_value(result)}"
    )
    return f"<{_PRI}>1 {header_ts} {_hostname(node_name or settings.NODE_NAME)} {APP_NAME} - {msgid} - {body}"


class _SyslogSender:
    """One connection per process, reused across records.

    The statistics scripts send hundreds of records per run; a TCP connection
    each was what the old SysLogHandler-per-record code did.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._target: tuple[str, int, str] | None = None
        self._paused_until = 0.0

    def _close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    def _connect(self, host: str, port: int, proto: str) -> socket.socket:
        if proto == "tcp":
            return socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT)
        family, type_, protocol, _, addr = socket.getaddrinfo(
            host, port, type=socket.SOCK_DGRAM
        )[0]
        sock = socket.socket(family, type_, protocol)
        sock.connect(addr)
        return sock

    def send(self, message: str, host: str, port: int, proto: str) -> None:
        data = message.encode("utf-8")
        if proto == "tcp":
            data += b"\n"
        target = (host, port, proto)
        with self._lock:
            if time.monotonic() < self._paused_until:
                return
            if self._target != target:
                self._close()
                self._target = target
            # One retry: a peer that closed an idle TCP connection only shows
            # up on the next send.
            for attempt in (1, 2):
                try:
                    if self._sock is None:
                        self._sock = self._connect(host, port, proto)
                    self._sock.sendall(data)
                    return
                except OSError:
                    self._close()
                    if attempt == 2:
                        self._paused_until = time.monotonic() + _BACKOFF_SECONDS
                        logger.warning(
                            "Failed to forward TACACS event to syslog %s:%s/%s; "
                            "pausing syslog forwarding for %ds",
                            host,
                            port,
                            proto,
                            int(_BACKOFF_SECONDS),
                            exc_info=True,
                        )

    def reset(self) -> None:
        with self._lock:
            self._close()
            self._target = None
            self._paused_until = 0.0


_sender = _SyslogSender()


def _send_syslog(
    log_type: str,
    username: str,
    nas_ip: str,
    client_ip: str,
    result: str,
    timestamp: float,
    node_name: str | None = None,
) -> None:
    if not settings.SIEM_SYSLOG_HOST:
        return
    proto = "udp" if settings.SIEM_SYSLOG_PROTOCOL == "udp" else "tcp"
    message = format_syslog_message(
        log_type, username, nas_ip, client_ip, result, timestamp, node_name
    )
    _sender.send(message, settings.SIEM_SYSLOG_HOST, settings.SIEM_SYSLOG_PORT, proto)
