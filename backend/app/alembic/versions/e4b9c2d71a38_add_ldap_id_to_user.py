"""add ldap_id to user

Revision ID: e4b9c2d71a38
Revises: d8a41f6b2c95
Create Date: 2026-11-17 15:08:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

revision = "e4b9c2d71a38"
down_revision = "d8a41f6b2c95"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column("ldap_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index("ix_user_ldap_id", "user", ["ldap_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_user_ldap_id", table_name="user")
    op.drop_column("user", "ldap_id")
