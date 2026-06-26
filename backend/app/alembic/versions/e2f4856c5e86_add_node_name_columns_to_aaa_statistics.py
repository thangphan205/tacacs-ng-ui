"""add_node_name_columns_to_aaa_statistics

Revision ID: e2f4856c5e86
Revises: 9ebbf2329bba
Create Date: 2026-06-26 10:09:01.570099

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'e2f4856c5e86'
down_revision = '9ebbf2329bba'
branch_labels = None
depends_on = None


def upgrade():
    # --- authenticationstatistics ---
    op.add_column(
        'authenticationstatistics',
        sa.Column('node_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False, server_default='primary'),
    )
    op.create_index('ix_authenticationstatistics_node_name', 'authenticationstatistics', ['node_name'], unique=False)
    op.drop_constraint('uq_authenticationstatistics_username_nas_ip_src_ip_log_date', 'authenticationstatistics', type_='unique')
    op.create_unique_constraint(
        'uq_authenticationstatistics_username_nas_ip_src_ip_log_date_nod',
        'authenticationstatistics',
        ['username', 'nas_ip', 'user_source_ip', 'log_date', 'node_name'],
    )

    # --- authorizationstatistics ---
    op.add_column(
        'authorizationstatistics',
        sa.Column('node_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False, server_default='primary'),
    )
    op.create_index('ix_authorizationstatistics_node_name', 'authorizationstatistics', ['node_name'], unique=False)
    op.drop_constraint('uq_authorizationstatistics_username_nas_ip_src_ip_log_date', 'authorizationstatistics', type_='unique')
    op.create_unique_constraint(
        'uq_authorizationstatistics_username_nas_ip_src_ip_log_date_node',
        'authorizationstatistics',
        ['username', 'nas_ip', 'user_source_ip', 'log_date', 'node_name'],
    )

    # --- accountingstatistics ---
    op.add_column(
        'accountingstatistics',
        sa.Column('node_name', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False, server_default='primary'),
    )
    op.create_index('ix_accountingstatistics_node_name', 'accountingstatistics', ['node_name'], unique=False)
    op.drop_constraint('uq_accountingstatistics_username_nas_ip_src_ip_log_date', 'accountingstatistics', type_='unique')
    op.create_unique_constraint(
        'uq_accountingstatistics_username_nas_ip_src_ip_log_date_node',
        'accountingstatistics',
        ['username', 'nas_ip', 'user_source_ip', 'log_date', 'node_name'],
    )


def downgrade():
    # --- accountingstatistics ---
    op.drop_constraint('uq_accountingstatistics_username_nas_ip_src_ip_log_date_node', 'accountingstatistics', type_='unique')
    op.create_unique_constraint(
        'uq_accountingstatistics_username_nas_ip_src_ip_log_date',
        'accountingstatistics',
        ['username', 'nas_ip', 'user_source_ip', 'log_date'],
    )
    op.drop_index('ix_accountingstatistics_node_name', table_name='accountingstatistics')
    op.drop_column('accountingstatistics', 'node_name')

    # --- authorizationstatistics ---
    op.drop_constraint('uq_authorizationstatistics_username_nas_ip_src_ip_log_date_node', 'authorizationstatistics', type_='unique')
    op.create_unique_constraint(
        'uq_authorizationstatistics_username_nas_ip_src_ip_log_date',
        'authorizationstatistics',
        ['username', 'nas_ip', 'user_source_ip', 'log_date'],
    )
    op.drop_index('ix_authorizationstatistics_node_name', table_name='authorizationstatistics')
    op.drop_column('authorizationstatistics', 'node_name')

    # --- authenticationstatistics ---
    op.drop_constraint('uq_authenticationstatistics_username_nas_ip_src_ip_log_date_nod', 'authenticationstatistics', type_='unique')
    op.create_unique_constraint(
        'uq_authenticationstatistics_username_nas_ip_src_ip_log_date',
        'authenticationstatistics',
        ['username', 'nas_ip', 'user_source_ip', 'log_date'],
    )
    op.drop_index('ix_authenticationstatistics_node_name', table_name='authenticationstatistics')
    op.drop_column('authenticationstatistics', 'node_name')
