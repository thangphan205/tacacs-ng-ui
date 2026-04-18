"""add_password_login_disabled_to_user

Revision ID: dd13bdaceafd
Revises: c3e7f8a91b02
Create Date: 2026-04-18 12:25:29.292535

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = 'dd13bdaceafd'
down_revision = 'c3e7f8a91b02'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('user', sa.Column('password_login_disabled', sa.Boolean(), nullable=False, server_default=sa.text('false')))
    op.alter_column('authproviderconfig', 'config_json',
               existing_type=sa.TEXT(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=False,
               existing_server_default=sa.text("'{}'::text"))
    op.alter_column('authproviderconfig', 'encrypted_secret',
               existing_type=sa.TEXT(),
               type_=sqlmodel.sql.sqltypes.AutoString(),
               existing_nullable=True)
    op.drop_index(op.f('ix_webauthchallenge_expires_at'), table_name='webauthchallenge')


def downgrade():
    op.create_index(op.f('ix_webauthchallenge_expires_at'), 'webauthchallenge', ['expires_at'], unique=False)
    op.alter_column('authproviderconfig', 'encrypted_secret',
               existing_type=sqlmodel.sql.sqltypes.AutoString(),
               type_=sa.TEXT(),
               existing_nullable=True)
    op.alter_column('authproviderconfig', 'config_json',
               existing_type=sqlmodel.sql.sqltypes.AutoString(),
               type_=sa.TEXT(),
               existing_nullable=False,
               existing_server_default=sa.text("'{}'::text"))
    op.drop_column('user', 'password_login_disabled')
