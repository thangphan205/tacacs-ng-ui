"""add last_authenticated_at to tacacsuser

Revision ID: f7a1c3d92b40
Revises: e4b9c2d71a38
Create Date: 2026-11-19 14:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = "f7a1c3d92b40"
down_revision = "e4b9c2d71a38"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tacacsuser",
        sa.Column(
            "last_authenticated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tacacsuser", "last_authenticated_at")
