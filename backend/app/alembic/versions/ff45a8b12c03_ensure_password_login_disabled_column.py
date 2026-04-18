"""ensure_password_login_disabled_column

Revision ID: ff45a8b12c03
Revises: ee24f7a93c01
Create Date: 2026-04-18 12:55:00.000000

"""
from alembic import op

revision = 'ff45a8b12c03'
down_revision = 'ee24f7a93c01'
branch_labels = None
depends_on = None


def upgrade():
    # Idempotent: adds the column if it was missing from a prior broken migration run
    op.execute(
        "ALTER TABLE \"user\" ADD COLUMN IF NOT EXISTS "
        "password_login_disabled BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade():
    op.execute(
        "ALTER TABLE \"user\" DROP COLUMN IF EXISTS password_login_disabled"
    )
