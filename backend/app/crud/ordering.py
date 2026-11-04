"""Explicit ordering for rows that tac_plus-ng evaluates top to bottom.

Profile scripts, ruleset scripts and the rulesets themselves are emitted in the
order the generator reads them, and tac_plus-ng stops at the first `permit` or
`deny` it reaches. That order is therefore part of the authorization policy, so
it is stored in a `position` column instead of being left to the heap order of
an unordered SELECT.

Positions are kept dense (0..n-1) so the value the API returns is also the
row's index: a new row is appended at `max + 1`, and a move or a delete
renumbers the siblings in the same transaction. `created_at` then `id` break
ties, so the order stays total even when two concurrent creates both compute
the same `max + 1`; the next move or delete re-densifies it.
"""

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func
from sqlmodel import Session, SQLModel, col, select

# Conditions that continue the chain opened by the script just above them.
_CONTINUATIONS = frozenset({"elif", "else"})


def order_columns(model: Any) -> tuple[Any, ...]:
    """The ORDER BY used everywhere these rows are read."""
    return (col(model.position), col(model.created_at), col(model.id))


def next_position(
    *, session: Session, model: Any, parent_column: Any | None, parent_id: Any
) -> int:
    """`max(position) + 1` among the row's siblings, or 0 for the first one."""
    statement = select(func.max(model.position))
    if parent_column is not None:
        statement = statement.where(parent_column == parent_id)
    current = session.exec(statement).one()
    return 0 if current is None else int(current) + 1


def ordered_siblings(
    *, session: Session, model: Any, parent_column: Any | None, parent_id: Any
) -> list[Any]:
    statement = select(model)
    if parent_column is not None:
        statement = statement.where(parent_column == parent_id)
    return list(session.exec(statement.order_by(*order_columns(model))).all())


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
                f"Script #{index + 1} is an '{condition}' but comes {where}; "
                "it must directly follow an 'if' or an 'elif'."
            )
        previous = condition
    return errors


def move(
    *,
    session: Session,
    row: SQLModel,
    model: Any,
    parent_column: Any | None,
    parent_id: Any,
    position: int,
    condition_attr: str | None = None,
) -> SQLModel:
    """Move `row` to index `position` among its siblings and renumber them.

    `position` is a 0-based index into the current order and is clamped to the
    list bounds. When `condition_attr` names the if/elif/else field, a move that
    would break a valid chain is refused with `ValueError`; a chain that was
    already broken may still be rearranged, so legacy data never gets stuck.
    """
    siblings = ordered_siblings(
        session=session, model=model, parent_column=parent_column, parent_id=parent_id
    )
    row_id = row.id  # type: ignore[attr-defined]
    remaining = [s for s in siblings if s.id != row_id]
    target = max(0, min(position, len(remaining)))
    reordered = [*remaining[:target], row, *remaining[target:]]

    if condition_attr is not None:
        before = chain_errors([getattr(s, condition_attr) for s in siblings])
        after = chain_errors([getattr(s, condition_attr) for s in reordered])
        if after and len(after) > len(before):
            raise ValueError(" ".join(after))

    _renumber(session, reordered)
    session.commit()
    session.refresh(row)
    return row


def compact(
    *, session: Session, model: Any, parent_column: Any | None, parent_id: Any
) -> None:
    """Renumber siblings 0..n-1 in their current order, closing any gaps.

    Does not commit: callers fold it into the transaction that made the gap.
    """
    _renumber(
        session,
        ordered_siblings(
            session=session,
            model=model,
            parent_column=parent_column,
            parent_id=parent_id,
        ),
    )


def _renumber(session: Session, rows: Sequence[Any]) -> None:
    for index, row in enumerate(rows):
        if row.position != index:
            row.position = index
            session.add(row)
