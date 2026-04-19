"""add auditlog table

Revision ID: a3f9c2e01d45
Revises: ff45a8b12c03
Create Date: 2026-04-19 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


revision = 'a3f9c2e01d45'
down_revision = 'ff45a8b12c03'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'auditlog',
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('entity_type', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('entity_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(length=1024), nullable=True),
        sa.Column('user_agent', sqlmodel.sql.sqltypes.AutoString(length=512), nullable=True),
        sa.Column('old_values', sa.Text(), nullable=True),
        sa.Column('new_values', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=True),
        sa.Column('user_email', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('ip_address', sqlmodel.sql.sqltypes.AutoString(length=45), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_auditlog_action'), 'auditlog', ['action'], unique=False)
    op.create_index(op.f('ix_auditlog_entity_type'), 'auditlog', ['entity_type'], unique=False)
    op.create_index(op.f('ix_auditlog_user_id'), 'auditlog', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_auditlog_user_id'), table_name='auditlog')
    op.drop_index(op.f('ix_auditlog_entity_type'), table_name='auditlog')
    op.drop_index(op.f('ix_auditlog_action'), table_name='auditlog')
    op.drop_table('auditlog')
