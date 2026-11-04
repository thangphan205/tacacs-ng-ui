"""Explicit ordering for rows that tac_plus-ng evaluates top to bottom.

Profile scripts, ruleset scripts and the rulesets themselves are emitted in the
order the generator reads them, and tac_plus-ng stops at the first `permit` or
`deny` it reaches. That order is therefore part of the authorization policy, so
it is stored in a `position` column instead of being left to the heap order of
an unordered SELECT.

Every mutation of an ordered row goes through `create` / `update` / `delete`
here, which:

- take a transaction-scoped advisory lock on the sibling group, so concurrent
  creates, moves and deletes in one profile (or among the rulesets) serialize
  instead of interleaving their renumbering;
- keep positions dense (0..n-1), so the value the API returns is also the row's
  index;
- refuse, with `ValueError`, any change that leaves more broken if/elif/else
  chains than there were before. A chain that was already broken can still be
  edited, so legacy data never gets stuck.

`created_at` then `id` break ties in the ORDER BY, so the order stays total even
if positions ever collide.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, text
from sqlmodel import Session, col, select

# Conditions that continue the chain opened by the script just above them.
_CONTINUATIONS = frozenset({"elif", "else"})


@dataclass(frozen=True)
class Siblings:
    """How one ordered model is grouped.

    `parent_attr` names the foreign key that groups siblings (`profile_id`), or
    is `None` when every row belongs to one list (rulesets). `condition_attr`
    names the if/elif/else field whose chain must stay valid, if any.
    """

    model: Any
    parent_attr: str | None
    condition_attr: str | None = None

    def parent_of(self, row: Any) -> Any:
        return getattr(row, self.parent_attr) if self.parent_attr else None


def order_columns(model: Any) -> tuple[Any, ...]:
    """The ORDER BY used everywhere these rows are read."""
    return (col(model.position), col(model.created_at), col(model.id))


def chain_errors(conditions: Sequence[str]) -> list[str]:
    """Problems in an if/elif/else chain, in reading order.

    An `elif` or `else` continues the chain opened by the script directly above
    it, so it is only valid right after an `if` or an `elif`. A list of plain
    `if` scripts is always valid.
    """
    errors: list[str] = []
    previous: str | None = None
    for index, raw in enumerate(conditions):
        condition = raw.strip()
        if condition in _CONTINUATIONS and previous not in ("if", "elif"):
            where = "first" if previous is None else f"after an '{previous}'"
            errors.append(
                f"Script #{index + 1} would be an '{condition}' that comes {where}; "
                "it must directly follow an 'if' or an 'elif'."
            )
        previous = condition
    return errors


def next_position(*, session: Session, spec: Siblings, parent_id: Any) -> int:
    """`max(position) + 1` among the siblings, or 0 for the first one."""
    statement = select(func.max(spec.model.position))
    if spec.parent_attr:
        statement = statement.where(getattr(spec.model, spec.parent_attr) == parent_id)
    current = session.exec(statement).one()
    return 0 if current is None else int(current) + 1


def ordered_siblings(*, session: Session, spec: Siblings, parent_id: Any) -> list[Any]:
    statement = select(spec.model)
    if spec.parent_attr:
        statement = statement.where(getattr(spec.model, spec.parent_attr) == parent_id)
    return list(session.exec(statement.order_by(*order_columns(spec.model))).all())


def create(
    *, session: Session, spec: Siblings, data: dict[str, Any], position: int | None
) -> Any:
    """Insert a row at the end, or at index `position`, and commit."""
    parent = data.get(spec.parent_attr) if spec.parent_attr else None
    _lock(session, spec, [parent])
    before = {parent: _errors(session, spec, parent)}

    data = {
        **data,
        "position": next_position(session=session, spec=spec, parent_id=parent),
    }
    row = spec.model.model_validate(data)
    session.add(row)
    _place(session, spec, row, parent, position)
    return _finish(session, spec, before, row)


def update(*, session: Session, spec: Siblings, row: Any, data: dict[str, Any]) -> Any:
    """Apply field changes and an optional `position` move, and commit.

    Without a `position` the row keeps its place. A row moved to another parent
    is appended there and the gap it leaves is closed.
    """
    data = dict(data)
    position = data.pop("position", None)
    old_parent = spec.parent_of(row)
    new_parent = data.get(spec.parent_attr, old_parent) if spec.parent_attr else None
    parents = [old_parent] if new_parent == old_parent else [old_parent, new_parent]

    _lock(session, spec, parents)
    before = {p: _errors(session, spec, p) for p in parents}
    # Computed before the row is touched: once it is dirty, autoflush would
    # write it into the new parent first and count it in the max.
    appended = (
        next_position(session=session, spec=spec, parent_id=new_parent)
        if new_parent != old_parent
        else None
    )

    row.sqlmodel_update(data)
    if appended is not None:
        row.position = appended
    session.add(row)
    if new_parent != old_parent:
        _renumber(
            session, ordered_siblings(session=session, spec=spec, parent_id=old_parent)
        )
    _place(session, spec, row, new_parent, position)
    return _finish(session, spec, before, row)


def delete(*, session: Session, spec: Siblings, row: Any) -> None:
    """Delete a row, close the gap it leaves, and commit."""
    parent = spec.parent_of(row)
    _lock(session, spec, [parent])
    before = {parent: _errors(session, spec, parent)}
    session.delete(row)
    session.flush()
    _renumber(session, ordered_siblings(session=session, spec=spec, parent_id=parent))
    _finish(session, spec, before, None)


def _lock(session: Session, spec: Siblings, parents: Sequence[Any]) -> None:
    """Serialize writers per sibling group until the transaction ends.

    Locks are taken in a fixed order so two writers touching the same pair of
    groups (a script moved between two profiles) cannot deadlock.
    """
    for parent in sorted({str(p) for p in parents}):
        session.connection().execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": f"{spec.model.__tablename__}:{parent}"},
        )


def _errors(session: Session, spec: Siblings, parent: Any) -> list[str]:
    if spec.condition_attr is None:
        return []
    rows = ordered_siblings(session=session, spec=spec, parent_id=parent)
    return chain_errors([getattr(r, spec.condition_attr) for r in rows])


def _place(
    session: Session, spec: Siblings, row: Any, parent: Any, position: int | None
) -> None:
    """Renumber `parent`'s rows densely, with `row` at index `position` if given."""
    rows = ordered_siblings(session=session, spec=spec, parent_id=parent)
    if position is not None:
        rows = [r for r in rows if r is not row]
        target = max(0, min(position, len(rows)))
        rows.insert(target, row)
    _renumber(session, rows)


def _finish(
    session: Session, spec: Siblings, before: dict[Any, list[str]], row: Any
) -> Any:
    """Commit, unless the change broke more if/elif/else chains than it found."""
    for parent, errors_before in before.items():
        errors_after = _errors(session, spec, parent)
        if len(errors_after) > len(errors_before):
            session.rollback()
            raise ValueError(" ".join(errors_after))
    session.commit()
    if row is not None:
        session.refresh(row)
    return row


def _renumber(session: Session, rows: Sequence[Any]) -> None:
    for index, row in enumerate(rows):
        if row.position != index:
            row.position = index
            session.add(row)
