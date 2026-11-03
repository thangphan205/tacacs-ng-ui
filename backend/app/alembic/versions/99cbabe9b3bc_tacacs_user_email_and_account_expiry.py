"""tacacs user email and account expiry

Revision ID: 99cbabe9b3bc
Revises: d5e8f1a2b3c4
Create Date: 2026-11-03 11:37:14.803306

"""
import sqlalchemy as sa
import sqlmodel.sql.sqltypes
from alembic import op

# revision identifiers, used by Alembic.
revision = "99cbabe9b3bc"
down_revision = "d5e8f1a2b3c4"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "tacacsuser",
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
    )
    op.add_column(
        "tacacsuser", sa.Column("account_expires_at", sa.Date(), nullable=True)
    )


def downgrade():
    op.drop_column("tacacsuser", "account_expires_at")
    op.drop_column("tacacsuser", "email")
