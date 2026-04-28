"""add unique constraints to statistics tables

Revision ID: aa01b2c3d4e5
Revises: ff45a8b12c03
Create Date: 2026-04-28 00:00:00.000000

"""
from alembic import op


revision = "aa01b2c3d4e5"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None

_TABLES = [
    "authenticationstatistics",
    "authorizationstatistics",
    "accountingstatistics",
]
_COLS = ["username", "nas_ip", "user_source_ip", "log_date"]


def upgrade():
    for table in _TABLES:
        # Remove duplicates first — keep the row with the largest id per key
        op.execute(f"""
            DELETE FROM {table} a
            USING {table} b
            WHERE a.id < b.id
              AND a.username       = b.username
              AND a.nas_ip         = b.nas_ip
              AND a.user_source_ip = b.user_source_ip
              AND a.log_date       = b.log_date
        """)
        op.create_unique_constraint(
            f"uq_{table}_username_nas_ip_src_ip_log_date",
            table,
            _COLS,
        )


def downgrade():
    for table in _TABLES:
        op.drop_constraint(
            f"uq_{table}_username_nas_ip_src_ip_log_date",
            table,
            type_="unique",
        )
