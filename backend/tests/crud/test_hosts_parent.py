import uuid

import pytest
from pydantic import ValidationError
from sqlmodel import Session

from app.crud import hosts as hosts_crud
from app.models import Host, HostCreate


def _host(name: str, parent: str | None = None, key: str | None = "k") -> Host:
    return Host(name=name, parent=parent, secret_key=key, ipv4_address="10.0.0.1")


def test_host_create_requires_key_without_parent() -> None:
    with pytest.raises(ValidationError):
        HostCreate(name="h1", ipv4_address="10.0.0.1")


def test_host_create_allows_missing_key_with_parent() -> None:
    host = HostCreate(name="h1", ipv4_address="10.0.0.1", parent="tpl")
    assert host.secret_key is None


def test_order_hosts_parent_first() -> None:
    child = _host("a-child", parent="z-parent", key=None)
    parent = _host("z-parent")
    ordered = hosts_crud.order_hosts_parent_first([child, parent])
    assert [h.name for h in ordered] == ["z-parent", "a-child"]


def test_order_hosts_survives_cycle() -> None:
    a = _host("a", parent="b")
    b = _host("b", parent="a")
    assert {h.name for h in hosts_crud.order_hosts_parent_first([a, b])} == {"a", "b"}


def test_check_parent(db: Session) -> None:
    tag = uuid.uuid4().hex[:8]
    root, mid = f"tpl-root-{tag}", f"tpl-mid-{tag}"
    db.add(_host(root))
    db.add(_host(mid, parent=root, key=None))
    db.commit()

    assert hosts_crud.check_parent(session=db, name="x", parent=None) is None
    assert hosts_crud.check_parent(session=db, name="x", parent=mid) is None
    assert "own parent" in (
        hosts_crud.check_parent(session=db, name="x", parent="x") or ""
    )
    assert "does not exist" in (
        hosts_crud.check_parent(session=db, name="x", parent="nope") or ""
    )
    # tpl-root -> tpl-mid would close the loop tpl-mid -> tpl-root -> tpl-mid
    assert "cycle" in (hosts_crud.check_parent(session=db, name=root, parent=mid) or "")


def test_generated_config_renders_parent_before_child(db: Session) -> None:
    from app.crud.tacacs_configs import generate_tacacs_ng_config

    tag = uuid.uuid4().hex[:8]
    parent, child = f"zz-parent-{tag}", f"aa-child-{tag}"
    db.add(_host(parent, key="parent-secret"))
    db.add(_host(child, parent=parent, key=None))
    db.commit()

    config = generate_tacacs_ng_config(session=db)

    for name in (child, parent):
        db.delete(hosts_crud.get_host_by_name(session=db, name=name))
    db.commit()

    assert config.index(f"host = {parent} {{") < config.index(f"host = {child} {{")
    child_block = config[config.index(f"host = {child} {{") :].split("}", 1)[0]
    assert f"parent = {parent}" in child_block
    assert "key =" not in child_block


def test_crud_rejects_bad_parent_and_guards_children(db: Session) -> None:
    from app.models import HostUpdate

    tag = uuid.uuid4().hex[:8]
    parent, child = f"gp-{tag}", f"gc-{tag}"

    with pytest.raises(ValueError, match="does not exist"):
        hosts_crud.create_host(
            session=db,
            host_create=HostCreate(name=child, ipv4_address="10.0.0.2", parent="nope"),
        )

    p = hosts_crud.create_host(
        session=db,
        host_create=HostCreate(name=parent, ipv4_address="10.0.0.1", secret_key="k"),
    )
    c = hosts_crud.create_host(
        session=db,
        host_create=HostCreate(name=child, ipv4_address="10.0.0.2", parent=parent),
    )

    assert "parent of" in (hosts_crud.check_can_delete(session=db, host=p) or "")
    assert hosts_crud.check_can_delete(session=db, host=c) is None
    with pytest.raises(ValueError, match="cannot be renamed"):
        hosts_crud.update_host(
            session=db,
            db_host=p,
            host_in=HostUpdate(
                name=f"{parent}-x", ipv4_address="10.0.0.1", secret_key="k"
            ),
        )

    db.delete(c)
    db.delete(p)
    db.commit()
