"""add siemconfig

Revision ID: a9c4e7f21d36
Revises: b7d3f1a9c2e4
Create Date: 2026-11-07 12:00:00.000000

SIEM forwarding settings, editable in the UI. Singleton row (id=1), seeded
once from the SIEM_* env vars by init_db on the primary. A new table, so
existing rows are untouched.

"""

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision = "a9c4e7f21d36"
down_revision = "b7d3f1a9c2e4"
branch_labels = None
depends_on = None


def _bool(name: str, default: bool) -> sa.Column:  # type: ignore[type-arg]
    return sa.Column(
        name,
        sa.Boolean(),
        nullable=False,
        server_default=sa.true() if default else sa.false(),
    )


def upgrade() -> None:
    op.create_table(
        "siemconfig",
        sa.Column("id", sa.Integer(), nullable=False),
        _bool("enabled", False),
        sa.Column(
            "webhook_url", sqlmodel.sql.sqltypes.AutoString(length=1000), nullable=True
        ),
        sa.Column("webhook_token_encrypted", sa.String(), nullable=True),
        _bool("webhook_verify_tls", True),
        sa.Column(
            "syslog_host", sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True
        ),
        sa.Column("syslog_port", sa.Integer(), nullable=False, server_default="514"),
        sa.Column(
            "syslog_protocol",
            sqlmodel.sql.sqltypes.AutoString(length=3),
            nullable=False,
            server_default="udp",
        ),
        _bool("ship_access", False),
        _bool("ship_authentication", False),
        _bool("ship_authorization", False),
        _bool("ship_accounting", False),
        _bool("ship_audit", False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("siemconfig")
