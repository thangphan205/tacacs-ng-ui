"""add microsoft_id to user

Revision ID: 7c4d9e2b1f30
Revises: c9d8e7f6a5b4
Create Date: 2026-10-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

revision = '7c4d9e2b1f30'
down_revision = 'c9d8e7f6a5b4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        'user',
        sa.Column('microsoft_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index('ix_user_microsoft_id', 'user', ['microsoft_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_user_microsoft_id', table_name='user')
    op.drop_column('user', 'microsoft_id')
