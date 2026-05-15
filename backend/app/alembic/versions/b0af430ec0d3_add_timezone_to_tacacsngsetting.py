"""add timezone to tacacsngsetting

Revision ID: b0af430ec0d3
Revises: b2c3d4e5f6a7
Create Date: 2026-05-15 09:40:10.267651

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'b0af430ec0d3'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('tacacsngsetting', sa.Column('timezone', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='UTC'))


def downgrade():
    op.drop_column('tacacsngsetting', 'timezone')
