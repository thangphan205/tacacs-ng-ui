"""add apikey table

Revision ID: b2c3d4e5f6a8
Revises: a1b2c3d4e5f7
Create Date: 2026-08-20 15:55:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "b2c3d4e5f6a8"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "apikey",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column(
            "scopes",
            sqlmodel.sql.sqltypes.AutoString(length=512),
            nullable=False,
            server_default="mcp:read",
        ),
        sa.Column(
            "description", sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True
        ),
        # Timezone-aware: an aware UTC value written into a naive column is
        # converted to the server's local zone and loses its offset, which would
        # push expiry hours into the future when read back as UTC.
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "key_prefix", sqlmodel.sql.sqltypes.AutoString(length=20), nullable=False
        ),
        sa.Column(
            "key_hash", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "last_used_ip", sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_apikey_user_id"), "apikey", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_apikey_key_prefix"), "apikey", ["key_prefix"], unique=False
    )
    op.create_index(op.f("ix_apikey_key_hash"), "apikey", ["key_hash"], unique=True)
    op.create_index(
        op.f("ix_apikey_created_by_id"), "apikey", ["created_by_id"], unique=False
    )


def downgrade():
    op.drop_index(op.f("ix_apikey_created_by_id"), table_name="apikey")
    op.drop_index(op.f("ix_apikey_key_hash"), table_name="apikey")
    op.drop_index(op.f("ix_apikey_key_prefix"), table_name="apikey")
    op.drop_index(op.f("ix_apikey_user_id"), table_name="apikey")
    op.drop_table("apikey")
