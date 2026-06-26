"""add ha multi-node tables (haconfig, hapeernode, hanodestate)

Revision ID: a1b2c3d4e5f7
Revises: 89abf27ed80c
Create Date: 2026-06-26 21:00:00.000000

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f7"
down_revision = "89abf27ed80c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "haconfig",
        sa.Column("node_name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False, server_default="primary"),
        sa.Column("sync_mode", sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default="auto"),
        sa.Column("scheduler_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("stats_interval_minutes", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hapeernode",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column("url", sqlmodel.sql.sqltypes.AutoString(length=500), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "hanodestate",
        sa.Column("peer_id", sa.Uuid(), nullable=False),
        sa.Column("last_push_at", sa.DateTime(), nullable=True),
        sa.Column("last_available", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["peer_id"], ["hapeernode.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("peer_id"),
    )


def downgrade():
    op.drop_table("hanodestate")
    op.drop_table("hapeernode")
    op.drop_table("haconfig")
