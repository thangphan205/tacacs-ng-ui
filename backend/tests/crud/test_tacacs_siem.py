"""SIEM sinks: RFC 5424 header and TCP framing (#373), HEC batches, test events."""

import json
import re
import socket
import threading
import uuid
from collections.abc import Generator
from datetime import datetime, timezone

import httpx
import pytest

from app.core.config import settings
from app.core.tacacs_log_parse import parse_log_line
from app.crud import tacacs_siem
from app.crud.tacacs_siem import (
    SiemTarget,
    audit_hec,
    format_audit_syslog,
    format_tacacs_syslog,
    send_syslog,
    send_test_event,
    send_webhook,
    tacacs_hec,
)
from app.models import AuditLog, TacacsLogEvent

RFC5424 = re.compile(
    r"^<(?P<pri>\d+)>1 (?P<ts>\S+) (?P<host>\S+) (?P<app>\S+) - - - (?P<msg>.*)$"
)
AUTH_LINE = (
    "2026-11-07 14:00:04 +0700\t10.0.0.1\talice\ttty0\t192.0.2.7\tshell login failed"
)


def _event(**overrides: object) -> TacacsLogEvent:
    ev = parse_log_line("authentication", AUTH_LINE)
    assert ev is not None
    return ev.model_copy(update=overrides)


@pytest.fixture(autouse=True)
def node(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    monkeypatch.setattr(settings, "NODE_NAME", "tacacs-01")
    tacacs_siem._sender.reset()
    yield
    tacacs_siem._sender.reset()


# --- formatting ---------------------------------------------------------------


def test_tacacs_message_is_rfc5424_with_event_time_and_node() -> None:
    m = RFC5424.match(format_tacacs_syslog("authentication", _event(), AUTH_LINE))
    assert m
    assert m["ts"] == "2026-11-07T07:00:04.000Z"  # the line's time, in UTC
    assert m["host"] == "tacacs-01"
    assert m["app"] == "tacacs-ng"
    assert m["pri"] == "12"  # failed → warning
    assert m["msg"] == (
        "type=authentication username=alice nas_ip=10.0.0.1 port=tty0 "
        "client_ip=192.0.2.7 result=failed msg=shell login failed"
    )


def test_success_is_informational_and_command_is_included() -> None:
    line = (
        "2026-11-07 14:00:05 +0700\t10.0.0.1\talice\ttty0\t192.0.2.7\t"
        "start shell show version <cr>"
    )
    ev = parse_log_line("accounting", line)
    m = RFC5424.match(format_tacacs_syslog("accounting", ev, line))
    assert m and m["pri"] == "14"
    assert (
        "result=start command=show_version msg=start shell show version <cr>"
        in m["msg"]
    )


def test_values_cannot_break_the_message() -> None:
    ev = _event(username="bad user\nInjected <13>1 x", nas_ip="", message="a\nb\x00c")
    msg = format_tacacs_syslog("authentication", ev, AUTH_LINE)
    assert "\n" not in msg and "\x00" not in msg
    m = RFC5424.match(msg)
    assert m
    assert "username=bad_user_Injected_<13>1_x " in m["msg"]
    assert "nas_ip=- " in m["msg"]
    assert m["msg"].endswith("msg=a b c")


def test_hostname_is_sanitised(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "NODE_NAME", "node with spaces")
    m = RFC5424.match(format_tacacs_syslog("authentication", _event(), AUTH_LINE))
    assert m and m["host"] == "node-with-spaces"


def test_tacacs_hec_event() -> None:
    hec = tacacs_hec("authentication", _event(), AUTH_LINE)
    assert (
        hec["time"] == datetime(2026, 11, 7, 7, 0, 4, tzinfo=timezone.utc).timestamp()
    )
    assert hec["host"] == "tacacs-01"
    assert hec["sourcetype"] == "tacacs-ng:authentication"
    assert hec["event"]["username"] == "alice"
    assert hec["event"]["result"] == "failed"
    assert hec["event"]["node"] == "tacacs-01"


def _audit() -> AuditLog:
    return AuditLog(
        id=uuid.uuid4(),
        action="UPDATE",
        entity_type="Host",
        entity_id="h1",
        description="Updated host core-sw",
        user_email="admin@example.com",
        ip_address="198.51.100.4",
        created_at=datetime(2026, 11, 7, 7, 0, tzinfo=timezone.utc),
    )


def test_audit_formats() -> None:
    log = _audit()
    m = RFC5424.match(format_audit_syslog(log))
    assert m and m["app"] == "tacacs-ng-ui"
    assert m["ts"] == "2026-11-07T07:00:00.000Z"
    assert m["msg"] == (
        "type=audit action=UPDATE entity_type=Host entity_id=h1 "
        "user_email=admin@example.com ip=198.51.100.4 msg=Updated host core-sw"
    )
    hec = audit_hec(log)
    assert hec["sourcetype"] == "tacacs-ng-ui:audit"
    assert hec["event"]["action"] == "UPDATE"


# --- webhook ------------------------------------------------------------------


def test_webhook_sends_one_newline_separated_batch() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"text": "Success"})

    target = SiemTarget(webhook_url="https://siem.example/hec", webhook_token="tok")
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        events = [
            tacacs_hec("authentication", _event(username=u), AUTH_LINE) for u in "ab"
        ]
        assert send_webhook(target, events, client) is None
    assert len(seen) == 1
    assert seen[0].headers["Authorization"] == "Splunk tok"
    body = seen[0].content.decode().split("\n")
    assert [json.loads(b)["event"]["username"] for b in body] == ["a", "b"]


def test_webhook_error_status_is_reported() -> None:
    target = SiemTarget(webhook_url="https://siem.example/hec")
    transport = httpx.MockTransport(lambda _r: httpx.Response(403, text="bad token"))
    with httpx.Client(transport=transport) as client:
        error = send_webhook(target, [{"event": {}}], client)
    assert error == "HTTP 403: bad token"


# --- syslog -------------------------------------------------------------------


@pytest.fixture()
def tcp_server() -> Generator[tuple[SiemTarget, list[bytes], list[int]], None, None]:
    """Collect raw bytes per connection; yield (target, chunks, connection count)."""
    srv = socket.socket()
    srv.bind(("127.0.0.1", 0))
    srv.listen()
    received: list[bytes] = []
    conns = [0]

    def serve() -> None:
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            conns[0] += 1
            with conn:
                while chunk := conn.recv(65536):
                    received.append(chunk)

    threading.Thread(target=serve, daemon=True).start()
    target = SiemTarget(
        syslog_host="127.0.0.1", syslog_port=srv.getsockname()[1], syslog_protocol="tcp"
    )
    yield target, received, conns
    srv.close()


def _drain(received: list[bytes]) -> bytes:
    tacacs_siem._sender.reset()  # close the client so the server sees EOF
    for _ in range(100):
        threading.Event().wait(0.01)
    return b"".join(received)


def _msgs(*users: str) -> list[str]:
    return [
        format_tacacs_syslog("authentication", _event(username=u), AUTH_LINE)
        for u in users
    ]


def test_tcp_messages_are_lf_framed_over_one_connection(
    tcp_server: tuple[SiemTarget, list[bytes], list[int]],
) -> None:
    target, received, conns = tcp_server
    assert send_syslog(target, _msgs("alice", "bob")) is None
    assert send_syslog(target, _msgs("carol")) is None
    data = _drain(received)

    assert b"\x00" not in data
    assert data.endswith(b"\n")
    lines = data.decode().splitlines()
    assert [RFC5424.match(ln)["host"] for ln in lines] == ["tacacs-01"] * 3  # type: ignore[index]
    assert [ln.split("username=")[1].split()[0] for ln in lines] == [
        "alice",
        "bob",
        "carol",
    ]
    assert conns[0] == 1


def test_udp_sends_one_datagram_per_message() -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    srv.settimeout(2)
    target = SiemTarget(syslog_host="127.0.0.1", syslog_port=srv.getsockname()[1])
    try:
        assert send_syslog(target, _msgs("alice", "bob")) is None
        first, second = srv.recv(65536), srv.recv(65536)
    finally:
        srv.close()
    for dgram, user in ((first, "alice"), (second, "bob")):
        assert not dgram.endswith(b"\n")
        m = RFC5424.match(dgram.decode())
        assert m and f"username={user} " in m["msg"]


def _closed_port() -> int:
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()  # nothing listens here now
    return port


def test_unreachable_receiver_does_not_raise_and_backs_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = SiemTarget(
        syslog_host="127.0.0.1", syslog_port=_closed_port(), syslog_protocol="tcp"
    )
    calls = []
    real_connect = tacacs_siem._sender._connect

    def counting_connect(*a: object) -> socket.socket:
        calls.append(a)
        return real_connect(*a)  # type: ignore[arg-type]

    monkeypatch.setattr(tacacs_siem._sender, "_connect", counting_connect)
    for _ in range(50):
        error = send_syslog(target, _msgs("alice"))  # must not raise
        assert error and "127.0.0.1" in error
    # Two attempts for the first message, then paused for the rest.
    assert len(calls) == 2


# --- test event -----------------------------------------------------------------


def test_test_event_reports_each_sink(
    tcp_server: tuple[SiemTarget, list[bytes], list[int]],
) -> None:
    target, received, _ = tcp_server
    results = send_test_event(target)
    assert [(r.sink, r.ok) for r in results] == [("syslog", True)]
    data = _drain(received).decode()
    assert "type=test" in data and data.endswith("\n")

    down = SiemTarget(
        syslog_host="127.0.0.1", syslog_port=_closed_port(), syslog_protocol="tcp"
    )
    [result] = send_test_event(down)
    assert result.ok is False and result.error
