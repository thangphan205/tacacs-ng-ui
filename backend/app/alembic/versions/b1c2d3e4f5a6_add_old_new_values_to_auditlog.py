"""add old_new_values to auditlog

Revision ID: b1c2d3e4f5a6
Revises: a3f9c2e01d45
Create Date: 2026-04-19 13:20:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b1c2d3e4f5a6'
down_revision = 'a3f9c2e01d45'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('auditlog', sa.Column('old_values', sa.Text(), nullable=True))
    op.add_column('auditlog', sa.Column('new_values', sa.Text(), nullable=True))


def downgrade():
    op.drop_column('auditlog', 'new_values')
    op.drop_column('auditlog', 'old_values')
