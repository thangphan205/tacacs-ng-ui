"""Reading and downloading TACACS+ log files (#371)."""

from collections.abc import Callable, Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.api.routes import tacacs_logs
from app.core.config import settings
from app.models import TacacsLog

URL = f"{settings.API_V1_STR}/tacacs_logs"

MakeLog = Callable[[str], TacacsLog]


@pytest.fixture()
def log_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "tacacs"
    (root / "2026" / "11").mkdir(parents=True)
    monkeypatch.setattr(tacacs_logs, "LOG_DIRECTORY", str(root))
    return root


@pytest.fixture()
def make_log(db: Session) -> Generator[MakeLog, None, None]:
    created: list[TacacsLog] = []

    def _make(filepath: str) -> TacacsLog:
        row = TacacsLog(filename=Path(filepath).name, filepath=filepath)
        db.add(row)
        db.commit()
        db.refresh(row)
        created.append(row)
        return row

    yield _make
    for row in created:
        db.delete(row)
    db.commit()


def _write(log_dir: Path, rel: str, n: int) -> None:
    lines = [
        f"2026-11-06 10:00:{i % 60:02d} +0700 10.0.0.1 user{i} line {i}\n"
        for i in range(n)
    ]
    (log_dir / rel).write_text("".join(lines))


def test_read_returns_only_the_tail_by_default(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    log_dir: Path,
    make_log: MakeLog,
) -> None:
    rel = "2026/11/accounting-2026-11-06.log"
    _write(log_dir, rel, 2500)
    row = make_log(rel)

    r = client.get(f"{URL}/{row.id}", headers=superuser_token_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["total_lines"] == 2500
    assert body["shown_lines"] == tacacs_logs.DEFAULT_TAIL_LINES == 1000
    shown = body["data"].splitlines()
    assert len(shown) == 1000
    assert shown[0].endswith("line 1500") and shown[-1].endswith("line 2499")


def test_read_lines_param_and_bounds(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    log_dir: Path,
    make_log: MakeLog,
) -> None:
    rel = "2026/11/authentication-2026-11-06.log"
    _write(log_dir, rel, 30)
    row = make_log(rel)

    r = client.get(
        f"{URL}/{row.id}", params={"lines": 5}, headers=superuser_token_headers
    )
    assert r.json()["shown_lines"] == 5
    assert r.json()["data"].splitlines()[-1].endswith("line 29")

    # A small file comes back whole.
    r = client.get(f"{URL}/{row.id}", headers=superuser_token_headers)
    assert r.json()["total_lines"] == r.json()["shown_lines"] == 30

    for bad in (0, tacacs_logs.MAX_TAIL_LINES + 1):
        r = client.get(
            f"{URL}/{row.id}", params={"lines": bad}, headers=superuser_token_headers
        )
        assert r.status_code == 422


def test_search_counts_matches_and_tails_them(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    log_dir: Path,
    make_log: MakeLog,
) -> None:
    rel = "2026/11/authorization-2026-11-06.log"
    _write(log_dir, rel, 100)  # "user1" matches user1, user10..user19 → 11 lines
    row = make_log(rel)

    r = client.get(
        f"{URL}/{row.id}",
        params={"search": "USER1", "lines": 3},
        headers=superuser_token_headers,
    )
    body = r.json()
    assert body["total_lines"] == 11
    assert body["shown_lines"] == 3
    assert [ln.split()[-1] for ln in body["data"].splitlines()] == ["17", "18", "19"]


def test_download_returns_the_whole_file_as_attachment(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    log_dir: Path,
    make_log: MakeLog,
) -> None:
    rel = "2026/11/accounting-2026-11-07.log"
    _write(log_dir, rel, 2500)
    row = make_log(rel)

    r = client.get(f"{URL}/{row.id}/download", headers=superuser_token_headers)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/plain")
    assert "attachment" in r.headers["content-disposition"]
    assert "accounting-2026-11-07.log" in r.headers["content-disposition"]
    assert r.content == (log_dir / rel).read_bytes()


@pytest.mark.parametrize("suffix", ["", "/download"])
def test_paths_outside_the_log_directory_are_refused(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    log_dir: Path,
    make_log: MakeLog,
    suffix: str,
) -> None:
    secret = log_dir.parent / "secret.txt"
    secret.write_text("not a log\n")
    (log_dir / "2026" / "link.log").symlink_to(secret)

    for rel in ("../secret.txt", str(secret), "2026/link.log"):
        row = make_log(rel)
        r = client.get(f"{URL}/{row.id}{suffix}", headers=superuser_token_headers)
        assert r.status_code == 404, rel
        assert "not a log" not in r.text


@pytest.mark.parametrize("suffix", ["", "/download"])
def test_missing_file_and_auth(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    log_dir: Path,  # noqa: ARG001 - points LOG_DIRECTORY at an empty dir
    make_log: MakeLog,
    suffix: str,
) -> None:
    row = make_log("2026/11/gone.log")
    assert (
        client.get(
            f"{URL}/{row.id}{suffix}", headers=superuser_token_headers
        ).status_code
        == 404
    )
    assert client.get(f"{URL}/{row.id}{suffix}").status_code == 401


def test_list_filters_by_log_type_and_combines_with_search(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    log_dir: Path,
    make_log: MakeLog,
) -> None:
    # A date no other test or seed uses, so ``search`` isolates these rows.
    day = "2031-01-17"
    for kind in ("authentication", "authorization", "accounting"):
        rel = f"2026/11/{kind}-{day}.log"
        _write(log_dir, rel, 1)
        make_log(rel)  # pre-registered, so the listing adds no rows to clean up

    r = client.get(
        f"{URL}/files",
        headers=superuser_token_headers,
        params={"search": day, "log_type": "authentication"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert [f["filename"] for f in body["data"]] == [f"authentication-{day}.log"]

    r = client.get(
        f"{URL}/files", headers=superuser_token_headers, params={"search": day}
    )
    assert r.json()["count"] == 3

    # "auth" is a prefix of two types; only an exact type name is accepted.
    r = client.get(
        f"{URL}/files", headers=superuser_token_headers, params={"log_type": "auth"}
    )
    assert r.status_code == 422


def test_list_skips_dot_entries(
    client: TestClient,
    superuser_token_headers: dict[str, str],
    log_dir: Path,
    db: Session,
) -> None:
    """The SIEM shipper's state in .siem/ is not a TACACS+ log file."""
    (log_dir / ".siem").mkdir()
    (log_dir / ".siem" / "offsets.json").write_text("{}")
    (log_dir / ".siem" / "offsets.json.tmp").write_text("{}")
    (log_dir / "2026" / "11" / ".hidden.log").write_text("x\n")

    r = client.get(f"{URL}/files", headers=superuser_token_headers)
    assert r.status_code == 200
    rows = db.exec(select(TacacsLog)).all()
    assert not [
        row for row in rows if "siem" in row.filepath or "hidden" in row.filepath
    ]
