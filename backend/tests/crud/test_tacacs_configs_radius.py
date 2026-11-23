"""
RADIUS in the generated config. Off by default, and while off the config is
exactly what it was before RADIUS existed, whatever RADIUS data is stored.
"""

import uuid
from collections.abc import Iterator

import pytest
from sqlmodel import Session, select

from app.core.host_keys import unused_tacacs_key
from app.core.radius_dictionary import builtin_radius_dictionary
from app.crud.tacacs_configs import (
    RADIUS_ACCESS_FORMAT,
    RADIUS_ACCOUNTING_FORMAT,
    generate_tacacs_ng_config,
)
from app.models import Host, TacacsNgSetting

EXTRA = """radius.dictionary Ubiquiti 41112 {
    attribute Ubiquiti-Admin-Role 1 string
}"""


@pytest.fixture
def setting(db: Session) -> Iterator[TacacsNgSetting]:
    row = db.exec(select(TacacsNgSetting)).first()
    assert row is not None
    saved = {
        k: getattr(row, k)
        for k in (
            "radius_enabled",
            "radius_auth_port",
            "radius_acct_port",
            "radius_dictionary_extra",
            "remote_syslog_destination",
        )
    }
    yield row
    for k, v in saved.items():
        setattr(row, k, v)
    db.add(row)
    db.commit()


@pytest.fixture
def hosts(db: Session) -> Iterator[tuple[Host, Host]]:
    suffix = uuid.uuid4().hex[:8]
    parent = Host(
        name=f"RAD_PARENT_{suffix}",
        ipv4_address="198.18.10.0/24",
        secret_key="tacacs-key",
        radius_secret_key="radius-key",
    )
    child = Host(
        name=f"RAD_CHILD_{suffix}",
        ipv4_address="198.18.10.7/32",
        parent=parent.name,
    )
    db.add(parent)
    db.add(child)
    db.commit()
    yield parent, child
    db.delete(child)
    db.delete(parent)
    db.commit()


def _set(db: Session, row: TacacsNgSetting, **values: object) -> None:
    for k, v in values.items():
        setattr(row, k, v)
    db.add(row)
    db.commit()


def test_disabled_radius_leaves_the_config_unchanged(
    db: Session, setting: TacacsNgSetting
) -> None:
    _set(db, setting, radius_enabled=False, radius_dictionary_extra=None)

    suffix = uuid.uuid4().hex[:8]
    host = Host(
        name=f"RAD_OFF_{suffix}",
        ipv4_address="198.18.20.1/32",
        secret_key="k",
    )
    db.add(host)
    db.commit()
    try:
        with_host = generate_tacacs_ng_config(session=db)
        host.radius_secret_key = "stored-but-off"
        db.add(host)
        _set(db, setting, radius_dictionary_extra=EXTRA)
        after = generate_tacacs_ng_config(session=db)
    finally:
        db.delete(host)
        db.commit()

    assert after == with_host
    assert "stored-but-off" not in after
    assert "radius" not in after.lower()
    assert "1812" not in after and "1813" not in after


def test_enabled_radius_emits_listeners_logs_and_dictionaries(
    db: Session, setting: TacacsNgSetting, hosts: tuple[Host, Host]
) -> None:
    parent, child = hosts
    _set(
        db,
        setting,
        radius_enabled=True,
        radius_auth_port=11812,
        radius_acct_port=11813,
        radius_dictionary_extra=EXTRA,
        remote_syslog_destination="192.0.2.99:514",
    )
    config = generate_tacacs_ng_config(session=db)

    spawnd = config.split("id = tac_plus-ng", 1)[0]
    assert "port = 11812\n        protocol = UDP\n" in spawnd
    assert "port = 11813\n        protocol = UDP\n        flag = accounting" in spawnd

    assert f'radius.access format = "{RADIUS_ACCESS_FORMAT}"' in config
    assert f'radius.accounting format = "{RADIUS_ACCOUNTING_FORMAT}"' in config
    assert "radius.access log = authenticationlog" in config
    assert "radius.accounting log = accountinglog" in config
    assert "radius.access log = remotelog" in config
    assert "radius.accounting log = remotelog" in config

    assert builtin_radius_dictionary().rstrip("\n") in config
    assert "    radius.dictionary Ubiquiti 41112 {" in config
    # dictionaries come before the hosts and profiles that use them
    assert config.index("radius.dictionary MikroTik") < config.index(parent.name)

    parent_block = config.split(f"host = {parent.name} {{", 1)[1].split("}", 1)[0]
    assert 'key = "tacacs-key"' in parent_block
    assert 'radius.key = "radius-key"' in parent_block
    child_block = config.split(f"host = {child.name} {{", 1)[1].split("}", 1)[0]
    assert "radius.key" not in child_block  # inherited through parent
    assert "\n        key = " not in child_block  # so is the TACACS+ key
    assert f"parent = {parent.name}" in child_block


def test_toggling_keeps_the_stored_radius_data(
    db: Session, setting: TacacsNgSetting, hosts: tuple[Host, Host]
) -> None:
    parent, _ = hosts
    _set(db, setting, radius_enabled=True, radius_dictionary_extra=EXTRA)
    on = generate_tacacs_ng_config(session=db)
    _set(db, setting, radius_enabled=False)
    off = generate_tacacs_ng_config(session=db)
    _set(db, setting, radius_enabled=True)
    again = generate_tacacs_ng_config(session=db)

    assert "radius-key" in on and "radius-key" not in off
    assert again == on
    db.refresh(parent)
    assert parent.radius_secret_key == "radius-key"


def test_a_bad_stored_dictionary_is_left_out(
    db: Session, setting: TacacsNgSetting
) -> None:
    """Only reachable around the API; never interpolate it."""
    _set(
        db,
        setting,
        radius_enabled=True,
        radius_dictionary_extra="}\nhost evil { address = 0.0.0.0/0 }",
    )
    config = generate_tacacs_ng_config(session=db)
    assert "host evil" not in config


def _host_block(config: str, name: str) -> str:
    return config.split(f"host = {name} {{", 1)[1].split("\n    }", 1)[0]


@pytest.mark.parametrize("radius_enabled", [True, False])
def test_a_host_without_a_tacacs_key_gets_one_nobody_knows(
    db: Session, setting: TacacsNgSetting, radius_enabled: bool
) -> None:
    """Without a `key` tac_plus-ng takes cleartext TACACS+ from the host's
    address (tests/core/test_radius_binary.py), so a RADIUS-only host, and a
    host whose parent is not rendered, get a derived key, RADIUS on or off."""
    suffix = uuid.uuid4().hex[:8]
    radius_only = Host(
        name=f"RAD_ONLY_{suffix}",
        ipv4_address="198.18.11.1/32",
        radius_secret_key="radius-only-key",
    )
    orphan = Host(
        name=f"RAD_ORPHAN_{suffix}",
        ipv4_address="198.18.11.2/32",
        parent=f"NOT_RENDERED_{suffix}",
    )
    db.add(radius_only)
    db.add(orphan)
    _set(db, setting, radius_enabled=radius_enabled)
    try:
        config = generate_tacacs_ng_config(session=db)
        for host in (radius_only, orphan):
            key = unused_tacacs_key(host.id)
            assert len(key) == 64 and int(key, 16) >= 0
            assert f'\n        key = "{key}"' in _host_block(config, host.name)
        assert unused_tacacs_key(radius_only.id) != unused_tacacs_key(orphan.id)
        # the same on every Generate, so the preview matches the active config
        assert generate_tacacs_ng_config(session=db) == config
    finally:
        db.delete(radius_only)
        db.delete(orphan)
        db.commit()
