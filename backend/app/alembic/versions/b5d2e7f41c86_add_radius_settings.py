"""add RADIUS settings and host RADIUS secret

RADIUS is off on every existing install: `radius_enabled` defaults to false,
so the generated config does not change until an admin turns it on.

Revision ID: b5d2e7f41c86
Revises: a8c4e1b93d20
Create Date: 2026-11-20 10:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "b5d2e7f41c86"
down_revision = "a8c4e1b93d20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tacacsngsetting",
        sa.Column(
            "radius_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "tacacsngsetting",
        sa.Column(
            "radius_auth_port",
            sa.Integer(),
            nullable=False,
            server_default="1812",
        ),
    )
    op.add_column(
        "tacacsngsetting",
        sa.Column(
            "radius_acct_port",
            sa.Integer(),
            nullable=False,
            server_default="1813",
        ),
    )
    op.add_column(
        "tacacsngsetting",
        sa.Column("radius_dictionary_extra", sa.Text(), nullable=True),
    )
    op.add_column(
        "host",
        sa.Column("radius_secret_key", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("host", "radius_secret_key")
    op.drop_column("tacacsngsetting", "radius_dictionary_extra")
    op.drop_column("tacacsngsetting", "radius_acct_port")
    op.drop_column("tacacsngsetting", "radius_auth_port")
    op.drop_column("tacacsngsetting", "radius_enabled")
