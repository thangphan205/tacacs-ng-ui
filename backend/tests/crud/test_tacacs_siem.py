"""Syslog SIEM forwarding: RFC 5424 header and TCP framing (#373)."""

import re
import socket
import threading
from collections.abc import Generator
from datetime import datetime, timezone

import pytest

from app.core.config import settings
from app.crud import tacacs_siem
from app.crud.tacacs_siem import format_syslog_message, forward_tacacs_event_to_siem

DAY_START = datetime(2026, 10, 25, 17, 0, tzinfo=timezone.utc).timestamp()
NOW = datetime(2026, 11, 7, 6, 7, 19, 939000, tzinfo=timezone.utc)

RFC5424 = re.compile(r"^<14>1 (?P<ts>\S+) (?P<host>\S+) tacacs-ng - - - (?P<msg>.*)$")


def _send(**overrides: object) -> None:
    args: dict[str, object] = {
        "log_type": "authentication",
        "username": "alice",
        "nas_ip": "10.0.0.1",
        "client_ip": "192.0.2.7",
        "result": "failed",
        "timestamp": DAY_START,
        "node_name": "tacacs-01",
        "background": False,
    }
    args.update(overrides)
    forward_tacacs_event_to_siem(**args)  # type: ignore[arg-type]


@pytest.fixture(autouse=True)
def siem(monkeypatch: pytest.MonkeyPatch) -> Generator[None, None, None]:
    s = settings
    monkeypatch.setattr(s, "SIEM_FORWARD_TACACS_EVENTS", True)
    monkeypatch.setattr(s, "SIEM_WEBHOOK_URL", None)
    tacacs_siem._sender.reset()
    yield
    tacacs_siem._sender.reset()


def test_message_is_rfc5424_with_node_and_time() -> None:
    msg = format_syslog_message(
        "authentication", "alice", "10.0.0.1", "192.0.2.7", "failed",
        DAY_START, "tacacs-01", now=NOW,
    )  # fmt: skip
    m = RFC5424.match(msg)
    assert m, msg
    assert m["ts"] == "2026-11-07T06:07:19.939Z"
    assert m["host"] == "tacacs-01"
    assert m["msg"] == (
        "type=authentication ts=2026-10-25T17:00:00Z username=alice "
        "nas_ip=10.0.0.1 client_ip=192.0.2.7 result=failed"
    )


def test_values_cannot_break_the_message() -> None:
    msg = format_syslog_message(
        "authentication", "bad user\nInjected <13>1 x", "", "192.0.2.7", "ok",
        DAY_START, "node with spaces", now=NOW,
    )  # fmt: skip
    assert "\n" not in msg and "\x00" not in msg
    m = RFC5424.match(msg)
    assert m, msg
    assert m["host"] == "node-with-spaces"
    assert "username=bad_user_Injected_<13>1_x " in m["msg"]
    assert "nas_ip=- " in m["msg"]


def test_hostname_falls_back_to_node_name_setting(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "NODE_NAME", "standby-2")
    msg = format_syslog_message("accounting", "a", "b", "c", "start", DAY_START, None)
    m = RFC5424.match(msg)
    assert m and m["host"] == "standby-2"


@pytest.fixture()
def tcp_server(
    monkeypatch: pytest.MonkeyPatch,
) -> Generator[tuple[list[bytes], list[int]], None, None]:
    """Collect raw bytes per connection; return (chunks, connection count)."""
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

    t = threading.Thread(target=serve, daemon=True)
    t.start()
    s = settings
    monkeypatch.setattr(s, "SIEM_SYSLOG_HOST", "127.0.0.1")
    monkeypatch.setattr(s, "SIEM_SYSLOG_PORT", srv.getsockname()[1])
    monkeypatch.setattr(s, "SIEM_SYSLOG_PROTOCOL", "tcp")
    yield received, conns
    srv.close()


def _drain(received: list[bytes]) -> bytes:
    tacacs_siem._sender.reset()  # close the client so the server sees EOF
    for _ in range(100):
        threading.Event().wait(0.01)
    return b"".join(received)


def test_tcp_messages_are_lf_framed_over_one_connection(
    tcp_server: tuple[list[bytes], list[int]],
) -> None:
    received, conns = tcp_server
    for user in ("alice", "bob", "carol"):
        _send(username=user)
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


def test_udp_sends_one_datagram_per_record(monkeypatch: pytest.MonkeyPatch) -> None:
    srv = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    srv.bind(("127.0.0.1", 0))
    srv.settimeout(2)
    s = settings
    monkeypatch.setattr(s, "SIEM_SYSLOG_HOST", "127.0.0.1")
    monkeypatch.setattr(s, "SIEM_SYSLOG_PORT", srv.getsockname()[1])
    monkeypatch.setattr(s, "SIEM_SYSLOG_PROTOCOL", "udp")
    try:
        _send(username="alice")
        _send(username="bob")
        first, second = srv.recv(65536), srv.recv(65536)
    finally:
        srv.close()
    for dgram, user in ((first, "alice"), (second, "bob")):
        assert not dgram.endswith(b"\n")
        m = RFC5424.match(dgram.decode())
        assert m and f"username={user} " in m["msg"]


def test_unreachable_receiver_does_not_raise_and_backs_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()  # nothing listens here now
    s = settings
    monkeypatch.setattr(s, "SIEM_SYSLOG_HOST", "127.0.0.1")
    monkeypatch.setattr(s, "SIEM_SYSLOG_PORT", port)
    monkeypatch.setattr(s, "SIEM_SYSLOG_PROTOCOL", "tcp")

    calls = []
    real_connect = tacacs_siem._sender._connect

    def counting_connect(*a: object) -> socket.socket:
        calls.append(a)
        return real_connect(*a)  # type: ignore[arg-type]

    monkeypatch.setattr(tacacs_siem._sender, "_connect", counting_connect)
    for _ in range(50):
        _send()  # must not raise
    # Two attempts for the first record, then paused for the rest.
    assert len(calls) == 2


def test_disabled_sends_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "SIEM_FORWARD_TACACS_EVENTS", False)
    monkeypatch.setattr(settings, "SIEM_SYSLOG_HOST", "127.0.0.1")
    called = []
    monkeypatch.setattr(tacacs_siem._sender, "send", lambda *a: called.append(a))
    _send()
    assert called == []
