"""Remote syslog destination for tac_plus-ng logs (#373)."""

import os
from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.core.config import settings
from app.crud.tacacs_configs import generate_tacacs_ng_config, validate_config_text
from app.models import TacacsNgSetting, check_remote_syslog_destination

URL = f"{settings.API_V1_STR}/tacacs_ng_settings/"

TAC_PLUS_NG_BIN = "/usr/local/sbin/tac_plus-ng"
needs_binary = pytest.mark.skipif(
    not os.path.exists(TAC_PLUS_NG_BIN),
    reason="tac_plus-ng binary only present inside the backend container",
)

REMOTE_LINES = [
    "log remotelog { destination = 192.0.2.10:5141 }",
    "access log = remotelog",
    "authentication log = remotelog",
    "authorization log = remotelog",
    "accounting log = remotelog",
]


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("192.0.2.10", "192.0.2.10"),
        (" 192.0.2.10:5141 ", "192.0.2.10:5141"),
        ("192.0.2.10:0514", "192.0.2.10:514"),
    ],
)
def test_valid_destinations(raw: str, expected: str) -> None:
    assert check_remote_syslog_destination(raw) == expected


# Each refused form was checked against tac_plus-ng: a hostname silently
# creates no log, an IPv6 port is ambiguous, and -P accepts the junk ones.
@pytest.mark.parametrize(
    "raw",
    [
        "graylog",
        "graylog:1514",
        "2001:db8::1",
        "[2001:db8::1]:514",
        "192.0.2.10:0",
        "192.0.2.10:99999",
        "192.0.2.10:",
        "192.0.2.10:514;x",
        "192.0.2.10 }\n    include = /etc/passwd",
        "999.0.2.10",
    ],
)
def test_invalid_destinations(raw: str) -> None:
    with pytest.raises(ValueError):
        check_remote_syslog_destination(raw)


@pytest.fixture()
def setting_row(db: Session) -> Generator[TacacsNgSetting, None, None]:
    row = db.exec(select(TacacsNgSetting)).first()
    assert row is not None
    saved = row.remote_syslog_destination
    yield row
    db.refresh(row)
    row.remote_syslog_destination = saved
    db.add(row)
    db.commit()


def _set(db: Session, row: TacacsNgSetting, value: str) -> None:
    row.remote_syslog_destination = value
    db.add(row)
    db.commit()


def test_disabled_by_default_emits_nothing(
    db: Session, setting_row: TacacsNgSetting
) -> None:
    _set(db, setting_row, "")
    assert "remotelog" not in generate_tacacs_ng_config(session=db)


def test_set_adds_lines_after_the_local_logs(
    db: Session, setting_row: TacacsNgSetting
) -> None:
    _set(db, setting_row, "192.0.2.10:5141")
    lines = [ln.strip() for ln in generate_tacacs_ng_config(session=db).splitlines()]
    for expected in REMOTE_LINES:
        assert expected in lines
    # The local files keep their own lines; remote ones come after them.
    assert lines.index("accounting log = accountinglog") < lines.index(REMOTE_LINES[0])
    assert "authentication log = authenticationlog" in lines


def test_a_bad_stored_value_is_never_written(
    db: Session, setting_row: TacacsNgSetting
) -> None:
    _set(db, setting_row, "1.2.3.4 }\ninclude")  # bypasses the API validator
    config = generate_tacacs_ng_config(session=db)
    assert "remotelog" not in config
    assert "1.2.3.4" not in config


def test_api_validates_and_normalises(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    setting_row: TacacsNgSetting,  # noqa: ARG001 - restores the value
) -> None:
    r = client.put(
        URL,
        headers=superuser_token_headers,
        json={"remote_syslog_destination": "graylog:1514"},
    )
    assert r.status_code == 422, r.text
    assert "IPv4" in r.text

    r = client.put(
        URL,
        headers=superuser_token_headers,
        json={"remote_syslog_destination": " 192.0.2.10:05141 "},
    )
    assert r.status_code == 200, r.text
    assert r.json()["remote_syslog_destination"] == "192.0.2.10:5141"

    r = client.put(
        URL, headers=superuser_token_headers, json={"remote_syslog_destination": ""}
    )
    assert r.status_code == 200
    assert r.json()["remote_syslog_destination"] == ""


@needs_binary
def test_generated_config_passes_tac_plus_ng(
    db: Session, setting_row: TacacsNgSetting
) -> None:
    _set(db, setting_row, "192.0.2.10:5141")
    result = validate_config_text(text=generate_tacacs_ng_config(session=db))
    assert result["status"] == "success", result["raw_output"]
