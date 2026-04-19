"""add auditlog composite index

Revision ID: c4d5e6f7a8b9
Revises: b1c2d3e4f5a6
Create Date: 2026-04-19 14:00:00.000000

"""
from alembic import op


revision = 'c4d5e6f7a8b9'
down_revision = 'b1c2d3e4f5a6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        'ix_auditlog_entity_action_created',
        'auditlog',
        ['entity_type', 'action', 'created_at'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_auditlog_entity_action_created', table_name='auditlog')
