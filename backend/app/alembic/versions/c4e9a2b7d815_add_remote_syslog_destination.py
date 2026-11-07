"""add remote_syslog_destination to tacacsngsetting

Revision ID: c4e9a2b7d815
Revises: b2d7e4f9a613
Create Date: 2026-11-07 00:00:00.000000

Optional IPv4[:port] that tac_plus-ng also sends every log to as UDP syslog
(#373). Empty string = disabled, so existing installs generate the same config.

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "c4e9a2b7d815"
down_revision = "b2d7e4f9a613"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "tacacsngsetting",
        sa.Column(
            "remote_syslog_destination",
            sa.String(length=21),
            nullable=False,
            server_default="",
        ),
    )


def downgrade() -> None:
    op.drop_column("tacacsngsetting", "remote_syslog_destination")
