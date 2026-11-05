"""A standby runs the activated config text, not a regeneration (issue #348)."""

import os
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from sqlmodel import Session, select

from app.crud import tacacs_configs as crud
from app.models import Host, TacacsConfig, TacacsConfigCreate, TacacsConfigUpdate

NEW_HOST = "RB_NEW_HOST"


@pytest.fixture
def workdir(
    db: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Generator[MagicMock, None, None]:
    """Redirect config files to tmp_path; yield the mocked daemon restart."""
    monkeypatch.setattr(crud, "CONFIG_PATH", str(tmp_path))
    monkeypatch.setattr(crud, "CONFIG_FILE_PATH", str(tmp_path / "tac_plus-ng.cfg"))
    monkeypatch.setattr(crud, "_notify_peer_reload", lambda: None)
    restart = MagicMock()
    monkeypatch.setattr(crud, "_restart_tacacs", restart)

    for row in db.exec(select(TacacsConfig)).all():
        row.active = False
        db.add(row)
    db.commit()

    yield restart

    for row in db.exec(select(TacacsConfig).where(TacacsConfig.filename.like("rb-%"))):
        db.delete(row)
    for host in db.exec(select(Host).where(Host.name == NEW_HOST)):
        db.delete(host)
    db.commit()


def _save(db: Session, name: str) -> TacacsConfig:
    created = crud.create_tacacs_config(
        session=db, tacacs_config_create=TacacsConfigCreate(filename=name)
    )
    assert isinstance(created, TacacsConfig)
    return created


def _activate(db: Session, config: TacacsConfig) -> None:
    result = crud.update_tacacs_config(
        session=db,
        db_tacacs_config=config,
        tacacs_config_in=TacacsConfigUpdate(active=True),
    )
    assert isinstance(result, TacacsConfig), result


def test_standby_gets_rolled_back_config_not_current_db(
    db: Session, workdir: MagicMock
) -> None:
    running = Path(crud.CONFIG_FILE_PATH)

    v1 = _save(db, "rb-v1")
    _activate(db, v1)
    db.add(Host(name=NEW_HOST, ipv4_address="10.9.9.9", secret_key="s3cret"))
    db.commit()
    v2 = _save(db, "rb-v2")
    _activate(db, v2)
    assert NEW_HOST in running.read_text()

    # Roll back: the host is still in the database, but v1 is what is activated.
    _activate(db, v1)
    primary_text = running.read_text()
    assert NEW_HOST not in primary_text

    # Standby: no running file yet, replicated DB holds the same rows.
    running.unlink()
    assert crud.reload_active_config_from_db(session=db) is True

    assert running.read_text() == primary_text
    assert NEW_HOST not in running.read_text()
    assert workdir.call_count == 1


def test_reload_is_a_no_op_when_file_already_current(
    db: Session, workdir: MagicMock
) -> None:
    _activate(db, _save(db, "rb-noop"))
    os.remove(crud.CONFIG_FILE_PATH)

    assert crud.reload_active_config_from_db(session=db) is True
    assert crud.reload_active_config_from_db(session=db) is False
    assert workdir.call_count == 1


@pytest.mark.usefixtures("workdir")
def test_config_without_stored_text_falls_back_to_regeneration(db: Session) -> None:
    legacy = _save(db, "rb-legacy")
    legacy.active = True
    legacy.config_text = None  # saved before the column existed
    db.add(legacy)
    db.commit()

    assert crud.reload_active_config_from_db(session=db) is True
    assert Path(crud.CONFIG_FILE_PATH).read_text() == crud.generate_tacacs_ng_config(
        session=db
    )


@pytest.mark.usefixtures("workdir")
def test_activating_a_legacy_config_stores_its_text(db: Session) -> None:
    legacy = _save(db, "rb-legacy2")
    legacy.config_text = None
    db.add(legacy)
    db.commit()

    _activate(db, legacy)

    db.refresh(legacy)
    assert legacy.config_text == (Path(crud.CONFIG_PATH) / "rb-legacy2.cfg").read_text()
