"""add authenticationhourlystatistics

Revision ID: b7d3f1a9c2e4
Revises: c4e9a2b7d815
Create Date: 2026-11-07 00:00:00.000000

Logins per user and hour of day: the baseline for the "Login at Unusual Hour"
alert rule. A new table, so existing rows are untouched; it fills from the
next statistics run (or by re-running the authentication script for past
dates, while their log files are still on disk).

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "b7d3f1a9c2e4"
down_revision = "c4e9a2b7d815"
branch_labels = None
depends_on = None

_TABLE = "authenticationhourlystatistics"


def upgrade() -> None:
    op.create_table(
        _TABLE,
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("node_name", sqlmodel.AutoString(length=255), nullable=False),
        sa.Column("username", sqlmodel.AutoString(length=255), nullable=False),
        sa.Column("log_date", sa.Date(), nullable=False),
        sa.Column("hour", sa.Integer(), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False),
        sa.Column("fail_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "username",
            "log_date",
            "hour",
            "node_name",
            name="uq_authenticationhourlystatistics_user_date_hour_node",
        ),
    )
    op.create_index(f"ix_{_TABLE}_node_name", _TABLE, ["node_name"], unique=False)
    op.create_index(f"ix_{_TABLE}_username", _TABLE, ["username"], unique=False)
    op.create_index(f"ix_{_TABLE}_log_date", _TABLE, ["log_date"], unique=False)


def downgrade() -> None:
    op.drop_index(f"ix_{_TABLE}_log_date", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_username", table_name=_TABLE)
    op.drop_index(f"ix_{_TABLE}_node_name", table_name=_TABLE)
    op.drop_table(_TABLE)
