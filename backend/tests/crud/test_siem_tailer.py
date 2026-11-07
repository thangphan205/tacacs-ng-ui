"""Real-time SIEM shipper: what gets read, when, and what happens on failure."""

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.crud import siem_tailer, tacacs_siem
from app.crud.siem_tailer import LogTailer
from app.crud.tacacs_siem import SiemTarget

DAY = date(2026, 11, 7)
NEXT = date(2026, 11, 8)


def line(user: str, msg: str = "shell login succeeded", day: date = DAY) -> str:
    return (
        f"{day.isoformat()} 10:00:00 +0700\t10.0.0.1\t{user}\ttty0\t192.0.2.7\t{msg}\n"
    )


class Sinks:
    """Records what the tailer sends; the webhook can be made to fail."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.syslog: list[str] = []
        self.webhook: list[dict[str, Any]] = []
        self.webhook_error: str | None = None
        self.webhook_calls = 0

        def fake_syslog(_t: SiemTarget, msgs: list[str]) -> bool:
            self.syslog.extend(msgs)
            return True

        def fake_webhook(
            _t: SiemTarget, events: list[dict[str, Any]], _c: object = None
        ) -> str | None:
            self.webhook_calls += 1
            if self.webhook_error:
                return self.webhook_error
            self.webhook.extend(events)
            return None

        monkeypatch.setattr(tacacs_siem, "send_syslog", fake_syslog)
        monkeypatch.setattr(tacacs_siem, "send_webhook", fake_webhook)

    def syslog_users(self) -> list[str]:
        return [m.split("username=")[1].split()[0] for m in self.syslog]

    def webhook_users(self) -> list[str]:
        return [e["event"]["username"] for e in self.webhook]


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture()
def sinks(monkeypatch: pytest.MonkeyPatch) -> Sinks:
    return Sinks(monkeypatch)


@pytest.fixture()
def env(tmp_path: Path) -> dict[str, Any]:
    return {"dir": tmp_path, "today": [DAY], "clock": Clock()}


def tailer(env: dict[str, Any]) -> LogTailer:
    return LogTailer(
        log_dir=str(env["dir"]),
        offsets_path=str(env["dir"] / "offsets.json"),
        status_path=str(env["dir"] / "status.json"),
        today=lambda: env["today"][0],
        clock=env["clock"],
    )


def log_path(
    env: dict[str, Any], log_type: str = "authentication", day: date = DAY
) -> Path:
    p = env["dir"] / day.strftime(f"%Y/%m/{log_type}-%Y-%m-%d.log")
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def append(p: Path, text: str) -> None:
    with p.open("a") as f:
        f.write(text)


BOTH = SiemTarget(
    webhook_url="https://siem.example/hec",
    syslog_host="127.0.0.1",
    ship=frozenset({"authentication"}),
)
SYSLOG = SiemTarget(syslog_host="127.0.0.1", ship=frozenset({"authentication"}))


def test_existing_content_is_skipped_on_first_start(
    env: dict[str, Any], sinks: Sinks
) -> None:
    p = log_path(env)
    append(p, line("old1") + line("old2"))
    t = tailer(env)
    t.tick(SYSLOG)
    assert sinks.syslog == []
    append(p, line("alice"))
    t.tick(SYSLOG)
    assert sinks.syslog_users() == ["alice"]


def test_partial_line_waits_for_its_newline(env: dict[str, Any], sinks: Sinks) -> None:
    p = log_path(env)
    t = tailer(env)
    p.touch()
    t.tick(SYSLOG)
    full = line("alice")
    append(p, full[:20])
    t.tick(SYSLOG)
    assert sinks.syslog == []
    append(p, full[20:])
    t.tick(SYSLOG)
    assert sinks.syslog_users() == ["alice"]


def test_file_created_while_running_is_read_from_start(
    env: dict[str, Any], sinks: Sinks
) -> None:
    t = tailer(env)
    t.tick(SYSLOG)  # no file yet; the type is now primed
    append(log_path(env), line("alice") + line("bob"))
    t.tick(SYSLOG)
    assert sinks.syslog_users() == ["alice", "bob"]


def test_restart_resumes_from_saved_offset(env: dict[str, Any], sinks: Sinks) -> None:
    p = log_path(env)
    p.touch()
    t = tailer(env)
    t.tick(SYSLOG)
    append(p, line("alice"))
    t.tick(SYSLOG)
    append(p, line("bob"))  # written while the shipper is down
    t2 = tailer(env)
    t2.tick(SYSLOG)
    assert sinks.syslog_users() == ["alice", "bob"]


def test_truncated_file_is_read_again_from_start(
    env: dict[str, Any], sinks: Sinks
) -> None:
    p = log_path(env)
    p.touch()
    t = tailer(env)
    t.tick(SYSLOG)
    append(p, line("alice") + line("bob"))
    t.tick(SYSLOG)
    p.write_text(line("carol"))
    t.tick(SYSLOG)
    assert sinks.syslog_users() == ["alice", "bob", "carol"]


def test_midnight_drains_yesterday_then_reads_new_day(
    env: dict[str, Any], sinks: Sinks
) -> None:
    old = log_path(env)
    old.touch()
    t = tailer(env)
    t.tick(SYSLOG)
    append(old, line("late"))  # written just before midnight, not yet read
    env["today"][0] = NEXT
    append(log_path(env, day=NEXT), line("early", day=NEXT))
    t.tick(SYSLOG)
    assert sinks.syslog_users() == ["late", "early"]
    state = json.loads((env["dir"] / "offsets.json").read_text())
    assert list(state) == [str(log_path(env, day=NEXT))]


def test_restart_after_midnight_reads_whole_new_day(
    env: dict[str, Any], sinks: Sinks
) -> None:
    """Down over midnight: yesterday's offset is known, so today's file is not
    skipped to its end."""
    old = log_path(env)
    old.touch()
    tailer(env).tick(SYSLOG)
    env["today"][0] = NEXT
    append(log_path(env, day=NEXT), line("early", day=NEXT))
    tailer(env).tick(SYSLOG)
    assert sinks.syslog_users() == ["early"]


def test_only_enabled_types_are_shipped(env: dict[str, Any], sinks: Sinks) -> None:
    auth, acct = log_path(env), log_path(env, "accounting")
    auth.touch()
    acct.touch()
    t = tailer(env)
    t.tick(SYSLOG)
    append(auth, line("alice"))
    append(acct, line("bob", "start shell show version"))
    t.tick(SYSLOG)
    assert sinks.syslog_users() == ["alice"]


def test_reenabling_a_type_does_not_replay_the_gap(
    env: dict[str, Any], sinks: Sinks
) -> None:
    p = log_path(env)
    p.touch()
    t = tailer(env)
    t.tick(SYSLOG)
    t.tick(None)  # forwarding switched off
    append(p, line("while_off"))
    t.tick(SYSLOG)
    append(p, line("alice"))
    t.tick(SYSLOG)
    assert sinks.syslog_users() == ["alice"]


def test_webhook_failure_keeps_offset_and_does_not_resend_syslog(
    env: dict[str, Any], sinks: Sinks
) -> None:
    p = log_path(env)
    p.touch()
    t = tailer(env)
    t.tick(BOTH)
    append(p, line("alice"))
    sinks.webhook_error = "HTTP 503: busy"
    t.tick(BOTH)
    assert sinks.syslog_users() == ["alice"]
    assert sinks.webhook == []
    assert t.status.last_error == "webhook: HTTP 503: busy"

    append(p, line("bob"))
    calls = sinks.webhook_calls
    t.tick(BOTH)  # still inside the backoff window: nothing is attempted
    assert sinks.webhook_calls == calls

    sinks.webhook_error = None
    env["clock"].now += 120
    t.tick(BOTH)
    assert sinks.webhook_users() == ["alice", "bob"]
    assert sinks.syslog_users() == ["alice", "bob"]  # alice not sent twice


def test_webhook_failure_survives_restart(env: dict[str, Any], sinks: Sinks) -> None:
    p = log_path(env)
    p.touch()
    t = tailer(env)
    t.tick(BOTH)
    append(p, line("alice"))
    sinks.webhook_error = "connection refused"
    t.tick(BOTH)
    sinks.webhook_error = None
    tailer(env).tick(BOTH)  # restarted shipper
    assert sinks.webhook_users() == ["alice"]


def test_unparsed_line_is_still_shipped(env: dict[str, Any], sinks: Sinks) -> None:
    p = log_path(env)
    p.touch()
    t = tailer(env)
    t.tick(BOTH)
    append(p, "something tac_plus-ng wrote\n")
    t.tick(BOTH)
    assert sinks.webhook[0]["event"] == {
        "type": "authentication",
        "node": tacacs_siem.node_name(),
        "message": "something tac_plus-ng wrote",
    }
    assert sinks.syslog[0].endswith(
        "type=authentication msg=something tac_plus-ng wrote"
    )


@pytest.mark.usefixtures("sinks")
def test_status_file_reports_counts(env: dict[str, Any]) -> None:
    p = log_path(env)
    p.touch()
    t = tailer(env)
    t.tick(SYSLOG)
    append(p, line("alice") + line("bob"))
    t.tick(SYSLOG)
    status = siem_tailer.read_status(str(env["dir"] / "status.json"))
    assert status is not None
    assert status["running"] is True
    assert status["events_sent"] == {"authentication": 2}
    assert status["last_event_at"]


@pytest.mark.usefixtures("sinks")
def test_offsets_file_is_written_atomically(env: dict[str, Any]) -> None:
    p = log_path(env)
    append(p, line("x"))
    tailer(env).tick(SYSLOG)
    assert not os.path.exists(env["dir"] / "offsets.json.tmp")
    state = json.loads((env["dir"] / "offsets.json").read_text())
    assert state[str(p)]["offset"] == p.stat().st_size
