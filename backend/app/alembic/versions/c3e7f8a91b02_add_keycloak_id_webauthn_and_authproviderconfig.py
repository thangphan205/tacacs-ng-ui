"""add keycloak_id, webauthn tables, and authproviderconfig

Revision ID: c3e7f8a91b02
Revises: 4b38d11f24e1
Create Date: 2026-04-17 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

revision = 'c3e7f8a91b02'
down_revision = '4b38d11f24e1'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add keycloak_id to user table
    op.add_column(
        'user',
        sa.Column('keycloak_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    )
    op.create_index('ix_user_keycloak_id', 'user', ['keycloak_id'], unique=True)

    # WebAuthn credential table
    op.create_table(
        'webauthncredential',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('credential_id', sa.LargeBinary(), nullable=False),
        sa.Column('public_key', sa.LargeBinary(), nullable=False),
        sa.Column('sign_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webauthncredential_user_id', 'webauthncredential', ['user_id'])
    op.create_index(
        'ix_webauthncredential_credential_id',
        'webauthncredential',
        ['credential_id'],
        unique=True,
    )

    # WebAuthn challenge table
    op.create_table(
        'webauthchallenge',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('challenge', sa.LargeBinary(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_webauthchallenge_user_id', 'webauthchallenge', ['user_id'])
    op.create_index('ix_webauthchallenge_expires_at', 'webauthchallenge', ['expires_at'])

    # Auth provider config table
    op.create_table(
        'authproviderconfig',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('provider', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('config_json', sa.Text(), nullable=False, server_default='{}'),
        sa.Column('encrypted_secret', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_authproviderconfig_provider', 'authproviderconfig', ['provider'], unique=True)


def downgrade() -> None:
    op.drop_table('authproviderconfig')
    op.drop_table('webauthchallenge')
    op.drop_table('webauthncredential')
    op.drop_index('ix_user_keycloak_id', table_name='user')
    op.drop_column('user', 'keycloak_id')
