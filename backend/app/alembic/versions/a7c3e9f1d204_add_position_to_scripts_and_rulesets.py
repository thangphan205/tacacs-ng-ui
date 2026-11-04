"""add position to profilescript, rulesetscript and ruleset

tac_plus-ng evaluates scripts (and the rules of a ruleset) top to bottom and
stops at the first matching permit/deny, so their order is policy. Until now
the generator read them with no ORDER BY, i.e. in heap order.

The backfill numbers rows by `ctid` — the physical order a sequential scan
returns, which is what the generator emitted until now — so the first config
generated after the upgrade matches the active one. `created_at` and `id` only
break ties.

Revision ID: a7c3e9f1d204
Revises: 99cbabe9b3bc
Create Date: 2026-11-04 12:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a7c3e9f1d204"
down_revision = "99cbabe9b3bc"
branch_labels = None
depends_on = None

# (table, sibling-group column or None for one global list)
_TABLES = (
    ("profilescript", "profile_id"),
    ("rulesetscript", "ruleset_id"),
    ("ruleset", None),
)


def upgrade():
    for table, parent in _TABLES:
        op.add_column(
            table,
            sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        )
        partition = f"PARTITION BY {parent} " if parent else ""
        op.execute(
            f"""
            UPDATE {table} AS t
            SET position = numbered.rn
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           {partition}ORDER BY ctid, created_at, id
                       ) - 1 AS rn
                FROM {table}
            ) AS numbered
            WHERE t.id = numbered.id
            """
        )


def downgrade():
    for table, _ in reversed(_TABLES):
        op.drop_column(table, "position")
