"""add config_text to tacacsconfig

Revision ID: c3a9d7e5b102
Revises: b8d4f2a6c913
Create Date: 2026-11-05 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c3a9d7e5b102"
down_revision = "b8d4f2a6c913"
branch_labels = None
depends_on = None


def upgrade():
    # Nullable: configs saved before this column existed have no stored text and
    # a standby falls back to regenerating from the database for them.
    op.add_column("tacacsconfig", sa.Column("config_text", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("tacacsconfig", "config_text")
