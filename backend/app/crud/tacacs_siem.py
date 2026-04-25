import logging
import logging.handlers
import socket
import threading

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


def forward_tacacs_event_to_siem(
    log_type: str,
    username: str,
    nas_ip: str,
    client_ip: str,
    result: str,
    timestamp: float,
    *,
    background: bool = True,
) -> None:
    """Forward a parsed TACACS+ event to SIEM via HTTP webhook and/or syslog.

    background=False for batch scripts where daemon threads would be killed on exit.
    """
    if not settings.SIEM_FORWARD_TACACS_EVENTS:
        return

    def _send() -> None:
        _send_http(log_type, username, nas_ip, client_ip, result, timestamp)
        _send_syslog(log_type, username, nas_ip, client_ip, result, timestamp)

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


def _send_syslog(
    log_type: str,
    username: str,
    nas_ip: str,
    client_ip: str,
    result: str,
    timestamp: float,
) -> None:
    if not settings.SIEM_SYSLOG_HOST:
        return
    socktype = socket.SOCK_DGRAM if settings.SIEM_SYSLOG_PROTOCOL == "udp" else socket.SOCK_STREAM
    handler = logging.handlers.SysLogHandler(
        address=(settings.SIEM_SYSLOG_HOST, settings.SIEM_SYSLOG_PORT),
        socktype=socktype,
    )
    syslog_logger = logging.getLogger("tacacs_siem")
    syslog_logger.addHandler(handler)
    syslog_logger.setLevel(logging.INFO)
    from datetime import datetime, timezone

    ts_str = datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    msg = (
        f"tacacs-ng[{log_type}] ts={ts_str} "
        f"username={username} nas_ip={nas_ip} client_ip={client_ip} result={result}"
    )
    try:
        syslog_logger.info(msg)
    except Exception:
        logger.warning("Failed to forward TACACS event to syslog", exc_info=True)
    finally:
        syslog_logger.removeHandler(handler)
        handler.close()
