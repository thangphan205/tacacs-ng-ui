from typing import Any

from sqlmodel import Session, select

from app.models import Host, HostCreate, HostUpdate


def get_host_by_name(*, session: Session, name: str) -> Host | None:
    statement = select(Host).where(Host.name == name)
    session_host = session.exec(statement).first()
    return session_host


def create_host(*, session: Session, host_create: HostCreate) -> Host:
    """Create a host. Raises ``ValueError`` if ``parent`` is not a valid parent."""
    parent_error = check_parent(
        session=session, name=host_create.name, parent=host_create.parent
    )
    if parent_error:
        raise ValueError(parent_error)
    db_obj = Host.model_validate(host_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_host(*, session: Session, db_host: Host, host_in: HostUpdate) -> Any:
    """Update a host. Raises ``ValueError`` on an invalid parent or a rename that
    would orphan child hosts."""
    new_name = host_in.name if host_in.name is not None else db_host.name
    new_parent = (
        host_in.parent if "parent" in host_in.model_fields_set else db_host.parent
    )
    parent_error = check_parent(session=session, name=new_name, parent=new_parent)
    if parent_error:
        raise ValueError(parent_error)
    if new_name != db_host.name and get_child_names(session=session, name=db_host.name):
        raise ValueError(
            f"Host '{db_host.name}' is the parent of other hosts and cannot be renamed."
        )
    host_data = host_in.model_dump(exclude_unset=True)
    db_host.sqlmodel_update(host_data)
    session.add(db_host)
    session.commit()
    session.refresh(db_host)
    return db_host


def get_child_names(*, session: Session, name: str) -> list[str]:
    """Names of hosts that list ``name`` as their parent."""
    statement = select(Host.name).where(Host.parent == name)
    return list(session.exec(statement).all())


def check_can_delete(*, session: Session, host: Host) -> str | None:
    """Return an error message if deleting ``host`` would orphan child hosts."""
    children = get_child_names(session=session, name=host.name)
    if children:
        return (
            f"Host '{host.name}' is the parent of {', '.join(sorted(children))}; "
            "reassign or delete those first."
        )
    return None


def check_parent(*, session: Session, name: str, parent: str | None) -> str | None:
    """Return an error message if ``parent`` is not a valid parent for host ``name``."""
    if not parent:
        return None
    if parent == name:
        return "A host cannot be its own parent."
    seen = {name}
    current: str | None = parent
    while current:
        if current in seen:
            return "Parent host chain contains a cycle."
        seen.add(current)
        parent_host = get_host_by_name(session=session, name=current)
        if parent_host is None:
            return f"Parent host '{current}' does not exist."
        current = parent_host.parent
    return None


def order_hosts_parent_first(hosts: list[Host]) -> list[Host]:
    """Order hosts so every parent is emitted before its children."""
    by_name = {h.name: h for h in hosts}
    ordered: list[Host] = []
    done: set[str] = set()

    def visit(host: Host, trail: frozenset[str]) -> None:
        if host.name in done or host.name in trail:
            return
        parent = by_name.get(host.parent) if host.parent else None
        if parent is not None:
            visit(parent, trail | {host.name})
        done.add(host.name)
        ordered.append(host)

    for host in sorted(hosts, key=lambda h: h.name):
        visit(host, frozenset())
    return ordered
