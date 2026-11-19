"""add last_login_at to user

Revision ID: a8c4e1b93d20
Revises: f7a1c3d92b40
Create Date: 2026-11-19 14:18:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "a8c4e1b93d20"
down_revision = "f7a1c3d92b40"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user",
        sa.Column(
            "last_login_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    # Backfill from existing LOGIN_SUCCESS audit entries without touching updated_at.
    op.execute(
        """
        UPDATE "user" AS u
        SET last_login_at = a.last_login_at
        FROM (
            SELECT user_id, MAX(created_at) AS last_login_at
            FROM auditlog
            WHERE action = 'LOGIN_SUCCESS' AND user_id IS NOT NULL
            GROUP BY user_id
        ) AS a
        WHERE u.id = a.user_id
        """
    )


def downgrade() -> None:
    op.drop_column("user", "last_login_at")
