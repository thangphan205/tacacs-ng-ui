"""
Lines with an empty port or a missing / non-IP client must be parsed (#400).

tac_plus-ng writes ``${TIMESTAMP} ${nas}<TAB>${user}<TAB>${port}<TAB>${nac}<TAB>…``
and leaves ``port`` and ``nac`` empty, or puts free text in ``nac``, depending
on the device and the session. The old regexes required a non-empty port and
an IP-shaped client, and dropped most lines from some devices from the Events
tab, the SIEM fields and the authorization / accounting statistics.

The sample lines are the anonymized ones from the issue.
"""

from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from app.core.tacacs_log_parse import parse_log_line, split_log_line
from app.crud import alert_evaluator
from app.crud.tacacs_siem import format_tacacs_syslog
from scripts._log_stats_base import (
    build_log_file_path,
    parse_accounting_logs,
    parse_authentication_logs,
    parse_authorization_logs,
)

DAY = date(2026, 11, 8)
TS = "2026-11-08 08:00:00 +0700"


def _line(*columns: str) -> str:
    return f"{TS} " + "\t".join(columns) + "\n"


# --- authentication -----------------------------------------------------------

AUTH_EMPTY_PORT = _line(
    "192.0.2.10", "collector", "", "198.51.100.4", "shell login succeeded"
)
AUTH_NON_IP_CLIENT = _line(
    "172.19.0.1", "probe", "python_tty0", "python_device", "shell login succeeded"
)
AUTH_NO_CLIENT = _line(
    "192.0.2.20", "alice", "mgmt", "", "pap login failed [Invalid credentials.]"
)

# --- authorization ------------------------------------------------------------

AUTHZ_EMPTY_PORT = _line(
    "192.0.2.10",
    "collector",
    "",
    "198.51.100.4",
    "ro_profile",
    "permit",
    "junos-exec",
    "",
)
AUTHZ_NO_CLIENT = _line(
    "192.0.2.20", "alice", "mgmt", "", "super_profile", "permit", "shell", ""
)
# A profile name must not decide the result: the result column does.
AUTHZ_DENY_WITH_PERMIT_PROFILE = _line(
    "192.0.2.20", "alice", "mgmt", "", "permit_all", "deny", "shell", "show run"
)

# --- accounting ---------------------------------------------------------------

ACCT_NO_CLIENT = _line(
    "192.0.2.30", "collector", "non-tty", "", "start", "shell", "login"
)
ACCT_LOCALHOST = _line(
    "192.0.2.31", "collector", "non-tty", "localhost", "start", "shell", "login"
)
ACCT_UNKNOWN_HOST = _line(
    "192.0.2.32",
    "collector",
    "non-tty",
    "Unknown host - non-tty",
    "stop",
    "shell",
    "request-end-session<cr>",
)
ACCT_CONSOLE = _line("192.0.2.33", "root", "unknown", "console", "start", "shell", "")


@pytest.mark.parametrize(
    ("log_type", "line", "port", "client", "result"),
    [
        ("authentication", AUTH_EMPTY_PORT, None, "198.51.100.4", "success"),
        (
            "authentication",
            AUTH_NON_IP_CLIENT,
            "python_tty0",
            "python_device",
            "success",
        ),
        ("authentication", AUTH_NO_CLIENT, "mgmt", None, "failed"),
        ("authorization", AUTHZ_EMPTY_PORT, None, "198.51.100.4", "permit"),
        ("authorization", AUTHZ_NO_CLIENT, "mgmt", None, "permit"),
        ("authorization", AUTHZ_DENY_WITH_PERMIT_PROFILE, "mgmt", None, "deny"),
        ("accounting", ACCT_NO_CLIENT, "non-tty", None, "start"),
        ("accounting", ACCT_LOCALHOST, "non-tty", "localhost", "start"),
        ("accounting", ACCT_UNKNOWN_HOST, "non-tty", "Unknown host - non-tty", "stop"),
        ("accounting", ACCT_CONSOLE, "unknown", "console", "start"),
    ],
)
def test_events_keep_lines_with_empty_or_non_ip_columns(
    log_type: str, line: str, port: str | None, client: str | None, result: str
) -> None:
    event = parse_log_line(log_type, line)
    assert event is not None, line
    assert event.timestamp == TS
    assert event.port == port
    assert event.client_ip == client
    assert event.result == result


def test_columns_are_read_by_position() -> None:
    fields = split_log_line(AUTH_NON_IP_CLIENT)
    assert fields is not None
    assert fields.nas_ip == "172.19.0.1"
    assert fields.username == "probe"
    # the client column is not folded into the message any more
    assert fields.message == "shell login succeeded"

    # An authorization line with no profile starts its message with a TAB;
    # the result column must still be the second one.
    line = _line("10.0.0.1", "bob", "", "", "", "deny", "shell", "show run")
    event = parse_log_line("authorization", line)
    assert event is not None
    assert event.result == "deny"
    assert event.command == "show run"


def test_usernames_are_not_limited_to_word_characters() -> None:
    for user in ("alice@example.com", "CORP\\alice"):
        event = parse_log_line(
            "authentication",
            _line("10.0.0.1", user, "tty0", "", "shell login succeeded"),
        )
        assert event is not None and event.username == user


@pytest.mark.parametrize(
    "line",
    [
        "",
        "not a log line\n",
        "2026-11-08 08:00:00\t10.0.0.1\talice\ttty0\t192.0.2.7\tshell login succeeded\n",
        _line("10.0.0.1", "alice", "tty0", "192.0.2.7"),  # no message column
        _line("10.0.0.1", "", "tty0", "192.0.2.7", "shell login succeeded"),
        _line("", "alice", "tty0", "192.0.2.7", "shell login succeeded"),
    ],
)
def test_lines_in_another_shape_are_still_rejected(line: str) -> None:
    assert split_log_line(line) is None
    assert parse_log_line("authentication", line) is None


def test_source_ip_falls_back_to_the_nas_for_a_non_ip_client() -> None:
    def source(line: str) -> str:
        fields = split_log_line(line)
        assert fields is not None
        return fields.source_ip

    assert source(AUTH_EMPTY_PORT) == "198.51.100.4"
    assert source(AUTH_NON_IP_CLIENT) == "172.19.0.1"
    assert source(AUTH_NO_CLIENT) == "192.0.2.20"
    assert source(ACCT_LOCALHOST) == "192.0.2.31"
    v6 = _line("10.0.0.1", "alice", "tty0", "2001:db8::7", "shell login succeeded")
    assert source(v6) == "2001:db8::7"


def test_siem_ships_structured_fields_for_a_line_without_client() -> None:
    event = parse_log_line("authentication", AUTH_NO_CLIENT)
    msg = format_tacacs_syslog("authentication", event, AUTH_NO_CLIENT)
    assert (
        "username=alice nas_ip=192.0.2.20 port=mgmt client_ip=- result=failed "
        "msg=pap login failed [Invalid credentials.]"
    ) in msg


# --- statistics -----------------------------------------------------------------


def _write(tmp_path: Path, log_type: str, *lines: str) -> str:
    log_dir = f"{tmp_path}/"
    path = Path(build_log_file_path(DAY, log_type, log_dir))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines))
    return log_dir


def test_authentication_statistics_attribute_lines_to_the_right_source(
    tmp_path: Path,
) -> None:
    log_dir = _write(
        tmp_path, "authentication", AUTH_EMPTY_PORT, AUTH_NON_IP_CLIENT, AUTH_NO_CLIENT
    )
    ok, failed = parse_authentication_logs(DAY, log_dir)
    assert ok == {
        ("collector", "192.0.2.10", "198.51.100.4"): 1,
        ("probe", "172.19.0.1", "172.19.0.1"): 1,
    }
    assert failed == {("alice", "192.0.2.20", "192.0.2.20"): 1}


def test_authorization_statistics_count_every_line(tmp_path: Path) -> None:
    log_dir = _write(
        tmp_path,
        "authorization",
        AUTHZ_EMPTY_PORT,
        AUTHZ_NO_CLIENT,
        AUTHZ_DENY_WITH_PERMIT_PROFILE,
    )
    permitted, denied = parse_authorization_logs(DAY, log_dir)
    assert permitted == {
        ("collector", "192.0.2.10", "198.51.100.4"): 1,
        ("alice", "192.0.2.20", "192.0.2.20"): 1,
    }
    assert denied == {("alice", "192.0.2.20", "192.0.2.20"): 1}


def test_accounting_statistics_count_every_line(tmp_path: Path) -> None:
    log_dir = _write(
        tmp_path,
        "accounting",
        ACCT_NO_CLIENT,
        ACCT_LOCALHOST,
        ACCT_UNKNOWN_HOST,
        ACCT_CONSOLE,
    )
    start, stop = parse_accounting_logs(DAY, log_dir)
    assert start == {
        ("collector", "192.0.2.30", "192.0.2.30"): 1,
        ("collector", "192.0.2.31", "192.0.2.31"): 1,
        ("root", "192.0.2.33", "192.0.2.33"): 1,
    }
    assert stop == {("collector", "192.0.2.32", "192.0.2.32"): 1}


# --- alert evaluator ------------------------------------------------------------


def test_alert_evaluator_reads_the_same_lines(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    auth = Path(
        _write(tmp_path / "a", "authentication", AUTH_NO_CLIENT, AUTH_EMPTY_PORT)
    )
    authz = Path(
        _write(tmp_path / "z", "authorization", AUTHZ_DENY_WITH_PERMIT_PROFILE)
    )
    paths = {
        "authentication": [build_log_file_path(DAY, "authentication", f"{auth}/")],
        "authorization": [build_log_file_path(DAY, "authorization", f"{authz}/")],
    }
    monkeypatch.setattr(
        alert_evaluator,
        "_log_paths_for_window",
        lambda _start, _now, log_type: paths[log_type],
    )
    start = datetime(2026, 11, 7, tzinfo=timezone.utc)
    now = datetime(2026, 11, 9, tzinfo=timezone.utc)

    window = alert_evaluator._parse_auth_log(start, now)
    assert window.fail_by_user == {"alice": 1}
    assert window.fail_by_ip == {"192.0.2.20": 1}
    assert window.seen_ips == {"192.0.2.20", "198.51.100.4"}

    deny_by_user, deny_by_nas = alert_evaluator._parse_authz_log(start, now)
    assert deny_by_user == {"alice": 1}
    assert deny_by_nas == {"192.0.2.20": 1}
