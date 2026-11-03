"""host secret_key nullable (inherit key from parent host)

Revision ID: d5e8f1a2b3c4
Revises: 7c4d9e2b1f30
Create Date: 2026-11-03 12:00:00.000000

"""
import sqlalchemy as sa
from alembic import op

revision = "d5e8f1a2b3c4"
down_revision = "7c4d9e2b1f30"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "host", "secret_key", existing_type=sa.String(length=255), nullable=True
    )


def downgrade():
    # Children that inherited their key get an empty one so NOT NULL can be restored.
    op.execute("UPDATE host SET secret_key = '' WHERE secret_key IS NULL")
    op.alter_column(
        "host", "secret_key", existing_type=sa.String(length=255), nullable=False
    )
