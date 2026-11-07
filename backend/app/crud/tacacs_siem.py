"""SIEM sinks: HTTP webhook (Splunk HEC format) and syslog (RFC 5424).

Settings come from the ``SiemConfig`` row (edited in the UI), resolved into a
``SiemTarget``. Two producers use the sinks:

- the real-time shipper (``crud/siem_tailer.py``, ``scripts/siem_shipper.py``),
  one per node, which sends every tac_plus-ng log line as it is written;
- the audit log (``crud/audit_logs.py``), which sends each entry on creation.

Syslog messages follow RFC 5424 so receivers get a timestamp and the node as
hostname (#373). Over TCP each message ends with LF (RFC 6587 non-transparent
framing), which is what Graylog's and most collectors' default TCP inputs
split on; the stdlib SysLogHandler ends them with NUL instead, which those
inputs silently drop.
"""

import json
import logging
import re
import socket
import threading
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlmodel import Session

from app.core.config import settings
from app.core.security import decrypt_secret
from app.models import (
    SIEM_TACACS_LOG_TYPES,
    AuditLog,
    SiemConfig,
    SiemSinkTestResult,
    TacacsLogEvent,
)

logger = logging.getLogger(__name__)

TACACS_APP_NAME = "tacacs-ng"
AUDIT_APP_NAME = "tacacs-ng-ui"
# facility user (1) * 8 + severity: informational (6) / warning (4)
_PRI_INFO = 14
_PRI_WARNING = 12
_WARNING_RESULTS = frozenset({"failed", "deny"})
_CONNECT_TIMEOUT = 3.0
_HTTP_TIMEOUT = 5.0
# After a failed connect or send, skip syslog for this long instead of paying
# the connect timeout once per message.
_BACKOFF_SECONDS = 60.0

_UNSAFE = re.compile(r"[\s\x00-\x1f\x7f]+")
_CONTROL = re.compile(r"[\x00-\x1f\x7f]+")
_HOSTNAME_UNSAFE = re.compile(r"[^\x21-\x7e]")
_LOG_TS_FORMAT = "%Y-%m-%d %H:%M:%S %z"


@dataclass(frozen=True)
class SiemTarget:
    """Resolved SIEM settings: where to send and what to ship."""

    webhook_url: str | None = None
    webhook_token: str | None = None
    webhook_verify_tls: bool = True
    syslog_host: str | None = None
    syslog_port: int = 514
    syslog_protocol: str = "udp"
    # Enabled sources: tac_plus-ng log types and/or "audit".
    ship: frozenset[str] = frozenset()

    @property
    def has_sink(self) -> bool:
        return bool(self.webhook_url or self.syslog_host)

    def ships(self, source: str) -> bool:
        return source in self.ship


def target_from_config(cfg: SiemConfig) -> SiemTarget:
    token: str | None = None
    if cfg.webhook_token_encrypted:
        try:
            token = decrypt_secret(cfg.webhook_token_encrypted)
        except Exception:
            # SECRET_KEY changed since the token was saved.
            logger.warning("Cannot decrypt the SIEM webhook token; sending without it")
    ship = {t for t in SIEM_TACACS_LOG_TYPES if getattr(cfg, f"ship_{t}")}
    if cfg.ship_audit:
        ship.add("audit")
    return SiemTarget(
        webhook_url=cfg.webhook_url or None,
        webhook_token=token,
        webhook_verify_tls=cfg.webhook_verify_tls,
        syslog_host=cfg.syslog_host or None,
        syslog_port=cfg.syslog_port,
        syslog_protocol="tcp" if cfg.syslog_protocol == "tcp" else "udp",
        ship=frozenset(ship),
    )


def load_target(session: Session, *, require_enabled: bool = True) -> SiemTarget | None:
    """The SIEM target, or None when forwarding is off or has nowhere to send."""
    cfg = session.get(SiemConfig, 1)
    if cfg is None or (require_enabled and not cfg.enabled):
        return None
    target = target_from_config(cfg)
    return target if target.has_sink else None


# --- formatting ---------------------------------------------------------------


def _value(v: str | None) -> str:
    """A key=value value: no whitespace or control characters, never empty."""
    return _UNSAFE.sub("_", v or "") or "-"


def _free_text(v: str | None) -> str:
    """Trailing ``msg=`` text: spaces kept, control characters (incl. LF) not."""
    return _CONTROL.sub(" ", v or "").strip() or "-"


def _hostname(name: str | None) -> str:
    """RFC 5424 HOSTNAME: 1-255 printable US-ASCII, no spaces; NILVALUE if none."""
    cleaned = _HOSTNAME_UNSAFE.sub("-", (name or "").strip())[:255]
    return cleaned or "-"


def node_name() -> str:
    """This node's name. NODE_NAME is per node; HaConfig is the primary's."""
    return settings.NODE_NAME


def _rfc5424(pri: int, when: datetime, app_name: str, body: str) -> str:
    ts = when.astimezone(timezone.utc).isoformat(timespec="milliseconds")
    ts = ts.replace("+00:00", "Z")
    return f"<{pri}>1 {ts} {_hostname(node_name())} {app_name} - - - {body}"


def event_time(event: TacacsLogEvent | None) -> datetime:
    """The time tac_plus-ng stamped on the line; now if it cannot be read."""
    if event is not None:
        try:
            return datetime.strptime(event.timestamp, _LOG_TS_FORMAT)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def format_tacacs_syslog(log_type: str, event: TacacsLogEvent | None, raw: str) -> str:
    """One RFC 5424 message for one tac_plus-ng log line, without framing.

    MSGID is NILVALUE: Graylog 5.2's syslog input keeps a MSGID in the
    ``message`` text, and the log type is already in the body as ``type=``.
    The raw message goes last as ``msg=``, the only value that keeps spaces.
    """
    when = event_time(event)
    if event is None:
        body = f"type={_value(log_type)} msg={_free_text(raw)}"
        return _rfc5424(_PRI_INFO, when, TACACS_APP_NAME, body)
    parts = [
        f"type={_value(log_type)}",
        f"username={_value(event.username)}",
        f"nas_ip={_value(event.nas_ip)}",
        f"port={_value(event.port)}",
        f"client_ip={_value(event.client_ip)}",
        f"result={_value(event.result)}",
    ]
    if event.command:
        parts.append(f"command={_value(event.command)}")
    parts.append(f"msg={_free_text(event.message)}")
    pri = _PRI_WARNING if event.result in _WARNING_RESULTS else _PRI_INFO
    return _rfc5424(pri, when, TACACS_APP_NAME, " ".join(parts))


def tacacs_hec(log_type: str, event: TacacsLogEvent | None, raw: str) -> dict[str, Any]:
    body: dict[str, Any] = {"type": log_type, "node": node_name()}
    if event is None:
        body["message"] = raw.rstrip("\r\n")
    else:
        body.update(
            timestamp=event.timestamp,
            username=event.username,
            nas_ip=event.nas_ip,
            port=event.port,
            client_ip=event.client_ip,
            result=event.result,
            command=event.command,
            message=event.message,
        )
    return {
        "time": event_time(event).timestamp(),
        "host": node_name(),
        "source": TACACS_APP_NAME,
        "sourcetype": f"{TACACS_APP_NAME}:{log_type}",
        "event": body,
    }


def format_audit_syslog(log: AuditLog, when: datetime | None = None) -> str:
    """``when`` is the aware creation time; a naive ``created_at`` is read as UTC."""
    body = (
        f"type=audit action={_value(log.action)} "
        f"entity_type={_value(log.entity_type)} entity_id={_value(log.entity_id)} "
        f"user_email={_value(log.user_email)} ip={_value(log.ip_address)} "
        f"msg={_free_text(log.description)}"
    )
    return _rfc5424(_PRI_INFO, when or _aware(log.created_at), AUDIT_APP_NAME, body)


def audit_hec(log: AuditLog, when: datetime | None = None) -> dict[str, Any]:
    return {
        "time": (when or _aware(log.created_at)).timestamp(),
        "host": node_name(),
        "source": AUDIT_APP_NAME,
        "sourcetype": f"{AUDIT_APP_NAME}:audit",
        "event": {
            "id": str(log.id),
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "user_id": str(log.user_id) if log.user_id else None,
            "user_email": log.user_email,
            "ip_address": log.ip_address,
            "description": log.description,
        },
    }


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --- webhook ------------------------------------------------------------------


def _webhook_headers(target: SiemTarget) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if target.webhook_token:
        headers["Authorization"] = f"Splunk {target.webhook_token}"
    return headers


def send_webhook(
    target: SiemTarget,
    events: list[dict[str, Any]],
    client: httpx.Client | None = None,
) -> str | None:
    """POST events as one HEC batch (newline-separated JSON). Returns an error or None.

    Splunk HEC accepts concatenated event objects in one request, and the
    newline between them also makes the body valid ``json_lines`` for Logstash.
    """
    if not target.webhook_url or not events:
        return None
    content = "\n".join(json.dumps(e, separators=(",", ":")) for e in events)
    try:
        if client is None:
            with httpx.Client(
                verify=target.webhook_verify_tls, timeout=_HTTP_TIMEOUT
            ) as c:
                resp = c.post(
                    target.webhook_url,
                    content=content,
                    headers=_webhook_headers(target),
                )
        else:
            resp = client.post(
                target.webhook_url, content=content, headers=_webhook_headers(target)
            )
    except httpx.HTTPError as e:
        return f"{type(e).__name__}: {e}"
    if resp.status_code >= 300:
        return f"HTTP {resp.status_code}: {resp.text[:200]}"
    return None


# --- syslog -------------------------------------------------------------------


class _SyslogSender:
    """One connection per process, reused across messages.

    The shipper sends a message per log line; a TCP connection each was what
    the old SysLogHandler-per-record code did.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._sock: socket.socket | None = None
        self._target: tuple[str, int, str] | None = None
        self._paused_until = 0.0
        self.last_error: str | None = None

    def _close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass
        self._sock = None

    def _connect(self, host: str, port: int, proto: str) -> socket.socket:
        return _open_socket(host, port, proto)

    def send(self, message: str, host: str, port: int, proto: str) -> bool:
        return self.send_many([message], host, port, proto)

    def send_many(
        self, messages: Iterable[str], host: str, port: int, proto: str
    ) -> bool:
        """Send messages in order. False if they were dropped (unreachable/paused)."""
        target = (host, port, proto)
        with self._lock:
            if time.monotonic() < self._paused_until:
                return False
            if self._target != target:
                self._close()
                self._target = target
            for message in messages:
                if not self._send_one(_frame(message, proto), host, port, proto):
                    return False
            return True

    def _send_one(self, data: bytes, host: str, port: int, proto: str) -> bool:
        # One retry: a peer that closed an idle TCP connection only shows up on
        # the next send.
        for attempt in (1, 2):
            try:
                if self._sock is None:
                    self._sock = self._connect(host, port, proto)
                self._sock.sendall(data)
                return True
            except OSError as e:
                self._close()
                if attempt == 2:
                    self._paused_until = time.monotonic() + _BACKOFF_SECONDS
                    self.last_error = f"syslog {host}:{port}/{proto}: {e}"
                    logger.warning(
                        "Failed to forward to syslog %s:%s/%s; "
                        "pausing syslog forwarding for %ds",
                        host,
                        port,
                        proto,
                        int(_BACKOFF_SECONDS),
                        exc_info=True,
                    )
        return False

    def reset(self) -> None:
        with self._lock:
            self._close()
            self._target = None
            self._paused_until = 0.0
            self.last_error = None


def _frame(message: str, proto: str) -> bytes:
    data = message.encode("utf-8")
    return data + b"\n" if proto == "tcp" else data


def _open_socket(host: str, port: int, proto: str) -> socket.socket:
    if proto == "tcp":
        return socket.create_connection((host, port), timeout=_CONNECT_TIMEOUT)
    family, type_, protocol, _, addr = socket.getaddrinfo(
        host, port, type=socket.SOCK_DGRAM
    )[0]
    sock = socket.socket(family, type_, protocol)
    sock.connect(addr)
    return sock


_sender = _SyslogSender()


def send_syslog(target: SiemTarget, messages: list[str]) -> bool:
    """Send messages over the shared connection. True if sent (or nothing to do)."""
    if not target.syslog_host or not messages:
        return True
    return _sender.send_many(
        messages, target.syslog_host, target.syslog_port, target.syslog_protocol
    )


# --- audit log and test ---------------------------------------------------------


def forward_audit_log(
    target: SiemTarget, log: AuditLog, *, when: datetime | None = None
) -> None:
    """Send one audit entry to the configured sinks, off the request thread."""
    syslog_msg = format_audit_syslog(log, when) if target.syslog_host else None
    hec = audit_hec(log, when) if target.webhook_url else None

    def _send() -> None:
        if syslog_msg is not None:
            send_syslog(target, [syslog_msg])
        if hec is not None:
            error = send_webhook(target, [hec])
            if error:
                logger.warning("Failed to forward audit log to SIEM webhook: %s", error)

    threading.Thread(target=_send, daemon=True).start()


def send_test_event(target: SiemTarget) -> list[SiemSinkTestResult]:
    """Send one test event to each configured sink and report each outcome.

    Uses its own socket rather than the shared sender, so the result reflects
    the receiver now and not a backoff left by an earlier failure.
    """
    now = datetime.now(timezone.utc)
    text = f"SIEM test event from tacacs-ng-ui node {node_name()}"
    results: list[SiemSinkTestResult] = []
    if target.syslog_host:
        msg = _rfc5424(_PRI_INFO, now, AUDIT_APP_NAME, f"type=test msg={text}")
        try:
            sock = _open_socket(
                target.syslog_host, target.syslog_port, target.syslog_protocol
            )
            with sock:
                sock.sendall(_frame(msg, target.syslog_protocol))
            results.append(SiemSinkTestResult(sink="syslog", ok=True))
        except OSError as e:
            results.append(SiemSinkTestResult(sink="syslog", ok=False, error=str(e)))
    if target.webhook_url:
        event = {
            "time": now.timestamp(),
            "host": node_name(),
            "source": AUDIT_APP_NAME,
            "sourcetype": f"{AUDIT_APP_NAME}:test",
            "event": {"type": "test", "message": text},
        }
        error = send_webhook(target, [event])
        results.append(
            SiemSinkTestResult(sink="webhook", ok=error is None, error=error)
        )
    return results
