"""seed passkey provider as enabled by default

Revision ID: ab12cd34ef56
Revises: aa01b2c3d4e5
Create Date: 2026-04-30 00:00:00.000000

"""
import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = 'ab12cd34ef56'
down_revision = 'aa01b2c3d4e5'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    row = conn.execute(
        sa.text("SELECT id FROM authproviderconfig WHERE provider = 'passkey'")
    ).fetchone()
    if row is None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        conn.execute(
            sa.text(
                "INSERT INTO authproviderconfig (id, provider, enabled, config_json, created_at, updated_at) "
                "VALUES (:id, 'passkey', TRUE, '{}', :now, :now)"
            ),
            {"id": str(uuid.uuid4()), "now": now},
        )


def downgrade() -> None:
    pass
