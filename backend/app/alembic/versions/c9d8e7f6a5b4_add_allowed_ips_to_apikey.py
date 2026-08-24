"""add allowed_ips to apikey

Revision ID: c9d8e7f6a5b4
Revises: b2c3d4e5f6a8
Create Date: 2026-08-24 00:00:00.000000

"""

import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "c9d8e7f6a5b4"
down_revision = "b2c3d4e5f6a8"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "apikey",
        sa.Column(
            "allowed_ips",
            sqlmodel.sql.sqltypes.AutoString(length=1024),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("apikey", "allowed_ips")
