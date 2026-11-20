"""
RADIUS end to end against the real tac_plus-ng: the config the generator
writes when RADIUS is enabled parses, answers RADIUS on UDP, returns the
attributes a profile sets, and logs lines the shared log parser reads.

Needs the binary, so it runs only inside the backend image (see
tests/crud/test_tacacs_configs_validate.py for the same skip).
"""

import hashlib
import hmac
import os
import socket
import struct
import subprocess
import time
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from passlib.hash import sha512_crypt
from sqlmodel import Session, select

from app.core.tacacs_log_parse import (
    authentication_outcome,
    log_protocol,
    parse_log_line,
    split_log_line,
)
from app.crud.tacacs_configs import generate_tacacs_ng_config, validate_config_text
from app.models import (
    ConfigurationOption,
    Host,
    Profile,
    TacacsGroup,
    TacacsNgSetting,
    TacacsUser,
)

TAC_PLUS_NG_BIN = "/usr/local/sbin/tac_plus-ng"
pytestmark = pytest.mark.skipif(
    not os.path.exists(TAC_PLUS_NG_BIN),
    reason="tac_plus-ng binary only present inside the backend container",
)

SECRET = b"radius-test-secret"
PASSWORD = "Rad1us-pass"
TACACS_PORT = 14949
AUTH_PORT = 11812
ACCT_PORT = 11813

ACCESS_REQUEST, ACCESS_ACCEPT, ACCESS_REJECT = 1, 2, 3
ACCOUNTING_REQUEST, ACCOUNTING_RESPONSE = 4, 5
VENDOR_SPECIFIC, MIKROTIK, MIKROTIK_GROUP = 26, 14988, 3


# --- a minimal RADIUS client (RFC 2865 / 2866 / 3579) ---------------------------


def _attr(kind: int, value: bytes) -> bytes:
    return struct.pack("BB", kind, len(value) + 2) + value


def _hide_password(password: bytes, authenticator: bytes) -> bytes:
    padded = password + b"\0" * (-len(password) % 16)
    out, last = b"", authenticator
    for i in range(0, len(padded), 16):
        mask = hashlib.md5(SECRET + last).digest()
        last = bytes(a ^ b for a, b in zip(padded[i : i + 16], mask, strict=True))
        out += last
    return out


def _send(port: int, packet: bytes) -> tuple[int, list[tuple[int, bytes]]] | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        s.settimeout(3)
        s.sendto(packet, ("127.0.0.1", port))
        try:
            reply = s.recv(4096)
        except TimeoutError:
            return None
    attrs, i = [], 20
    while i + 2 <= len(reply):
        kind, length = reply[i], reply[i + 1]
        attrs.append((kind, reply[i + 2 : i + length]))
        i += length
    return reply[0], attrs


def access_request(user: str, password: str) -> tuple[int, list[tuple[int, bytes]]]:
    authenticator = os.urandom(16)
    body = (
        _attr(1, user.encode())
        + _attr(2, _hide_password(password.encode(), authenticator))
        + _attr(4, socket.inet_aton("127.0.0.1"))
        + _attr(31, b"198.51.100.7")
        + _attr(80, b"\0" * 16)
    )
    packet = (
        struct.pack("!BBH", ACCESS_REQUEST, 1, 20 + len(body)) + authenticator + body
    )
    signature = hmac.new(SECRET, packet, hashlib.md5).digest()
    reply = _send(AUTH_PORT, packet[:-16] + signature)
    assert reply is not None, "no answer to Access-Request"
    return reply


def accounting_request(user: str, status: int) -> int:
    body = (
        _attr(1, user.encode())
        + _attr(40, struct.pack("!I", status))
        + _attr(44, b"session-1")
        + _attr(4, socket.inet_aton("127.0.0.1"))
        + _attr(31, b"198.51.100.7")
    )
    packet = (
        struct.pack("!BBH", ACCOUNTING_REQUEST, 2, 20 + len(body)) + b"\0" * 16 + body
    )
    authenticator = hashlib.md5(packet + SECRET).digest()
    reply = _send(ACCT_PORT, packet[:4] + authenticator + packet[20:])
    assert reply is not None, "no answer to Accounting-Request"
    return reply[0]


def _vsa(attrs: list[tuple[int, bytes]], vendor: int, kind: int) -> bytes | None:
    for t, value in attrs:
        if t == VENDOR_SPECIFIC and struct.unpack("!I", value[:4])[0] == vendor:
            if value[4] == kind:
                return value[6 : 4 + value[5]]
    return None


# --- fixtures -------------------------------------------------------------------


@pytest.fixture
def radius_config(db: Session, tmp_path: Path) -> Iterator[tuple[str, Path, str]]:
    setting = db.exec(select(TacacsNgSetting)).first()
    assert setting is not None
    saved = setting.model_dump()
    suffix = uuid.uuid4().hex[:8]
    logs = tmp_path / "logs"
    logs.mkdir()

    for k, v in {
        "ipv4_address": "127.0.0.1",
        "ipv4_port": TACACS_PORT,
        "background": "no",
        "access_logfile_destination": str(logs / "access.log"),
        "authentication_logfile_destination": str(logs / "authentication.log"),
        "authorization_logfile_destination": str(logs / "authorization.log"),
        "accounting_logfile_destination": str(logs / "accounting.log"),
        "remote_syslog_destination": "",
        "radius_enabled": True,
        "radius_auth_port": AUTH_PORT,
        "radius_acct_port": ACCT_PORT,
        "radius_dictionary_extra": (
            "radius.dictionary Ubiquiti 41112 {\n"
            "    attribute Ubiquiti-Admin-Role 1 string\n}"
        ),
    }.items():
        setattr(setting, k, v)
    group = TacacsGroup(group_name=f"RADGRP_{suffix}", generate_config=True)
    user = TacacsUser(
        username=f"radalice{suffix}",
        password_type="crypt",
        password=sha512_crypt.using(rounds=5000).hash(PASSWORD),
        member=group.group_name,
        generate_config=True,
    )
    host = Host(
        name=f"RADHOST_{suffix}",
        ipv4_address="127.0.0.1/32",
        radius_secret_key=SECRET.decode(),
    )
    profile = Profile(
        name=f"radprofile{suffix}",
        action="permit",
        generate_config=True,
        raw_script=(
            "if (aaa.protocol == radius) {\n"
            "    set radius[MikroTik:MikroTik-Group] = full\n"
            "    permit\n"
            "}\n"
            "permit"
        ),
    )
    rule = ConfigurationOption(
        name="rule",
        config_option=(
            f"rule radrule{suffix} {{ script {{ "
            f'if (user == "{user.username}") {{ profile = {profile.name} permit }} '
            "} }"
        ),
    )
    rows = [group, user, host, profile, rule]
    for row in [setting, *rows]:
        db.add(row)
    db.commit()
    try:
        yield generate_tacacs_ng_config(session=db), logs, user.username
    finally:
        for row in reversed(rows):
            db.delete(row)
        for k, v in saved.items():
            setattr(setting, k, v)
        db.add(setting)
        db.commit()


@pytest.fixture
def daemon(radius_config: tuple[str, Path, str], tmp_path: Path) -> Iterator[Path]:
    config, logs, _ = radius_config
    path = tmp_path / "tac_plus-ng.cfg"
    path.write_text(config)
    proc = subprocess.Popen(
        [TAC_PLUS_NG_BIN, "-f", str(path)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(("127.0.0.1", TACACS_PORT)) == 0:
                    break
            time.sleep(0.2)
        else:
            pytest.fail("tac_plus-ng did not start")
        yield logs
    finally:
        proc.terminate()
        proc.wait(timeout=10)


def _lines(path: Path) -> list[str]:
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if path.exists() and path.read_text().strip():
            break
        time.sleep(0.2)
    return path.read_text().splitlines() if path.exists() else []


# --- tests ----------------------------------------------------------------------


def test_generated_radius_config_parses(radius_config: tuple[str, Path, str]) -> None:
    config, _, _ = radius_config
    result = validate_config_text(text=config)
    assert result["status"] == "success", result["raw_output"]


def test_radius_login_accounting_and_logs(
    daemon: Path, radius_config: tuple[str, Path, str]
) -> None:
    _, _, username = radius_config

    code, attrs = access_request(username, PASSWORD)
    assert code == ACCESS_ACCEPT
    assert _vsa(attrs, MIKROTIK, MIKROTIK_GROUP) == b"full"

    code, attrs = access_request(username, "wrong-password")
    assert code == ACCESS_REJECT
    assert _vsa(attrs, MIKROTIK, MIKROTIK_GROUP) is None

    assert accounting_request(username, 1) == ACCOUNTING_RESPONSE  # Start
    assert accounting_request(username, 3) == ACCOUNTING_RESPONSE  # Interim-Update
    assert accounting_request(username, 2) == ACCOUNTING_RESPONSE  # Stop

    auth = [split_log_line(line) for line in _lines(daemon / "authentication.log")]
    assert [f is not None for f in auth] == [True, True], auth
    outcomes = []
    for fields in auth:
        assert fields is not None
        assert (fields.nas_ip, fields.username, fields.client) == (
            "127.0.0.1",
            username,
            "198.51.100.7",
        )
        assert log_protocol("authentication", fields.message) == "radius"
        outcomes.append(authentication_outcome(fields.message))
    assert outcomes == ["success", "fail"]
    # the reply attributes are logged; the request attributes are not
    assert "MikroTik:MikroTik-Group=full" in auth[0].message  # type: ignore[union-attr]
    assert "Calling-Station-Id" not in auth[0].message  # type: ignore[union-attr]

    events = [
        parse_log_line("accounting", line) for line in _lines(daemon / "accounting.log")
    ]
    assert all(e is not None and e.protocol == "radius" for e in events), events
    assert [e.result for e in events if e] == ["start", "unknown", "stop"]
    assert all(e.username == username for e in events if e)
