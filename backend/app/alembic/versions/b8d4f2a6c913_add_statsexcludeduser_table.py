"""add statsexcludeduser table

Revision ID: b8d4f2a6c913
Revises: a7c3e9f1d204
Create Date: 2026-11-04 00:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "b8d4f2a6c913"
down_revision = "a7c3e9f1d204"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "statsexcludeduser",
        sa.Column(
            "pattern", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False
        ),
        sa.Column("note", sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_statsexcludeduser_pattern"),
        "statsexcludeduser",
        ["pattern"],
        unique=True,
    )


def downgrade():
    op.drop_index(op.f("ix_statsexcludeduser_pattern"), table_name="statsexcludeduser")
    op.drop_table("statsexcludeduser")
