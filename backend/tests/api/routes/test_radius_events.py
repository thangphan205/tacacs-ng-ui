"""The Events tab tells RADIUS lines from TACACS+ lines in the shared files."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings

DAY = "2026-11-08"
TS = "2026-11-08 08:00:00 +0700"
LINES = (
    f"{TS} 192.0.2.10\tbob\ttty0\t198.51.100.4\tshell login succeeded\n"
    f"{TS} 192.0.2.50\talice\t\t198.51.100.7\t"
    "radius pap login succeeded\tMikroTik:MikroTik-Group=full\n"
)


def test_events_filter_by_protocol(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "2026" / "11" / f"authentication-{DAY}.log"
    path.parent.mkdir(parents=True)
    path.write_text(LINES)
    monkeypatch.setattr(settings, "TACACS_LOG_DIRECTORY", f"{tmp_path}/")

    def users(**params: str) -> list[tuple[str, str]]:
        r = client.get(
            f"{settings.API_V1_STR}/tacacs_logs/events",
            headers=superuser_token_headers,
            params={"date_from": DAY, "date_to": DAY, "log_type": "all"} | params,
        )
        assert r.status_code == 200, r.text
        return sorted((e["username"], e["protocol"]) for e in r.json()["data"])

    assert users() == [("alice", "radius"), ("bob", "tacacs")]
    assert users(protocol="radius") == [("alice", "radius")]
    assert users(protocol="tacacs") == [("bob", "tacacs")]
    assert users(search="radius") == [("alice", "radius")]
