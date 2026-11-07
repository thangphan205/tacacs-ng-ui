"""Alert notifications read as sentences, never as Python reprs."""

import uuid
from typing import Any

import pytest

from app.crud.alert_formatter import (
    DISCORD,
    HTML,
    SLACK,
    build_alert_message,
    render,
    render_text,
)
from app.models import AlertRule


def _rule(**overrides: Any) -> AlertRule:
    defaults: dict[str, Any] = {
        "id": uuid.uuid4(),
        "name": "[System] New Username Detected",
        "log_type": "auth",
        "condition_field": "username",
        "condition_operator": "new_value",
        "threshold": None,
        "time_window_minutes": 60,
        "severity": "medium",
        "cooldown_minutes": 240,
    }
    defaults.update(overrides)
    return AlertRule(**defaults)


NEW_USER_PAYLOAD = {
    "new_usernames": ["abc", "zz"],
    "users": [
        {
            "username": "abc",
            "success": 2,
            "fail": 3,
            "source_ips": ["192.168.252.1"],
            "devices": ["core-sw1 (10.1.1.1)"],
            "first_seen": "2026-11-07T14:02:11+00:00",
            "last_seen": "2026-11-07T14:07:40+00:00",
        },
        {
            "username": "zz",
            "success": 0,
            "fail": 1,
            "source_ips": ["10.0.0.2"],
            "devices": ["10.1.1.2"],
            "first_seen": "2026-11-07T14:05:00+00:00",
            "last_seen": "2026-11-07T14:05:00+00:00",
        },
    ],
    "window_minutes": 60,
    "rule": "[System] New Username Detected",
    "node": "primary",
    "fired_at": "2026-11-07T14:08:00+00:00",
}

CONFIG_PAYLOAD = {
    "config_change_count": 2,
    "changes": [
        {
            "action": "ACTIVATE",
            "filename": "tacacs_2100.cfg",
            "entity_id": "03d816f9-9627-4c22-9fde-03fcccd06035",
            "by": "admin@9ping.cloud",
            "ip_address": "10.0.0.4",
            "at": "2026-11-07T14:00:25+00:00",
        },
        {
            "action": "ACTIVATE",
            "filename": None,
            "entity_id": "9457d29a-c0b3-48e7-8a2b-0d8039bae5e5",
            "by": "admin@9ping.cloud",
            "ip_address": None,
            "at": "2026-11-07T13:59:15+00:00",
        },
    ],
    "window_minutes": 5,
    "rule": "[System] TACACS Config Activated",
}


@pytest.fixture(autouse=True)
def utc_log_timezone(monkeypatch: pytest.MonkeyPatch) -> None:
    from zoneinfo import ZoneInfo

    monkeypatch.setattr(
        "app.crud.alert_formatter.local_tz", lambda: ZoneInfo("Asia/Ho_Chi_Minh")
    )


def _no_repr(text: str) -> None:
    assert "{'" not in text and "['" not in text and "':" not in text


def test_new_username_message_answers_who_where_when() -> None:
    msg = build_alert_message(rule=_rule(), payload=NEW_USER_PAYLOAD)
    text = render_text(msg)
    _no_repr(text)

    assert msg.subject == "[MEDIUM] New Username Detected"
    assert text.startswith("🟠 MEDIUM · New Username Detected")
    assert (
        "2 usernames not seen in the past 30 days appeared in the last 60 min." in text
    )
    assert "⚠️ Logged in successfully: abc" in text
    assert "👤 abc — ✅ 2 ok · ❌ 3 failed" in text
    assert "Source: 192.168.252.1" in text
    assert "Device: core-sw1 (10.1.1.1)" in text
    # shown in the log timezone, the range collapsed on one day
    assert "Seen: 2026-11-07 21:02:11 +07 → 21:07:40" in text
    assert "Node primary · fired 2026-11-07 21:08:00 +07" in text
    assert text.rstrip().endswith("/aaa_statistics")


def test_config_message_names_file_actor_and_ip() -> None:
    rule = _rule(
        name="[System] TACACS Config Activated",
        log_type="config",
        condition_field="config_action",
        condition_operator="activated",
        threshold=1.0,
        time_window_minutes=5,
        severity="critical",
    )
    text = render_text(build_alert_message(rule=rule, payload=CONFIG_PAYLOAD))
    _no_repr(text)

    assert text.startswith("🚨 CRITICAL · TACACS Config Activated")
    assert "2 TACACS config activations in the last 5 min." in text
    assert "1. 🚀 ACTIVATE tacacs_2100.cfg" in text
    assert "By: admin@9ping.cloud from 10.0.0.4" in text
    assert "At: 2026-11-07 21:00:25 +07" in text
    # no filename recorded: falls back to the id, no "from None"
    assert "2. 🚀 ACTIVATE 9457d29a" in text
    assert "None" not in text
    assert "/audit_logs" in text


def test_threshold_messages_explain_the_condition() -> None:
    rule = _rule(
        name="[System] High Auth Failure Rate",
        condition_field="fail_count",
        condition_operator="gt",
        threshold=10.0,
        time_window_minutes=10,
        severity="high",
    )
    payload = {
        "fail_count": 14,
        "top_users": [{"name": "alice", "count": 8}, {"name": "bob", "count": 6}],
        "top_sources": [{"name": "10.0.0.5", "count": 14}],
        "top_devices": [{"name": "core-sw1 (10.1.1.1)", "count": 14}],
        "window_minutes": 10,
    }
    text = render_text(build_alert_message(rule=rule, payload=payload))
    assert "14 failed logins in the last 10 min (threshold > 10)." in text
    assert "Top users: alice 8 · bob 6" in text
    assert "Top devices: core-sw1 (10.1.1.1) 14" in text


def test_entries_are_capped() -> None:
    names = [f"u{i:02d}" for i in range(13)]
    payload = {
        "new_usernames": names,
        "users": [{"username": n, "success": 0, "fail": 1} for n in names],
    }
    text = render_text(build_alert_message(rule=_rule(), payload=payload))
    assert "u09" in text
    assert "u10" not in text
    assert "… +3 more" in text


def test_identifiers_are_escaped_per_channel() -> None:
    payload = {
        "new_usernames": ["<b>x</b>"],
        "users": [{"username": "<b>x</b>", "success": 1, "fail": 0}],
    }
    msg = build_alert_message(rule=_rule(), payload=payload)

    telegram = render(msg, HTML)
    assert "<code>&lt;b&gt;x&lt;/b&gt;</code>" in telegram
    assert "<b>x</b>" not in telegram

    slack = render(msg, SLACK, heading=False)
    assert "`&lt;b&gt;x&lt;/b&gt;`" in slack

    underscored = build_alert_message(
        rule=_rule(),
        payload={
            "new_usernames": ["user_admin"],
            "users": [{"username": "user_admin"}],
        },
    )
    # in a code span, so Discord does not italicise the underscore
    assert "`user_admin`" in render(underscored, DISCORD, heading=False)


def test_unknown_payload_falls_back_to_readable_lines() -> None:
    rule = _rule(name="Custom", condition_field="something", condition_operator="gt")
    payload = {"weird_list": [{"a": 1}], "plain": 3, "rule": "Custom"}
    text = render_text(build_alert_message(rule=rule, payload=payload))
    _no_repr(text)
    assert "Weird list: a=1" in text
    assert "Plain: 3" in text
