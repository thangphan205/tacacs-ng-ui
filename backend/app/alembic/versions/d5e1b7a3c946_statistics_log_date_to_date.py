"""statistics log_date: timestamp -> date

Revision ID: d5e1b7a3c946
Revises: c3a9d7e5b102
Create Date: 2026-11-06 00:00:00.000000

The collectors wrote midnight UTC of the log day as an aware datetime into a
`timestamp without time zone` column, so PostgreSQL stored it converted to the
session time zone: west of UTC, day D became D-1 21:00 and every daily chart
showed the next day's numbers (#356).

Each stored value is turned back into the instant that was written (read in
the session time zone, as it was stored) and that instant's UTC date is the
log day. That holds as long as the server's `timezone` setting has not changed
since the rows were written: the backend sets no session time zone of its own,
so writes and this migration both use the server default.

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "d5e1b7a3c946"
down_revision = "c3a9d7e5b102"
branch_labels = None
depends_on = None

_TABLES = [
    "authenticationstatistics",
    "authorizationstatistics",
    "accountingstatistics",
]

_LOG_DAY = (
    "((log_date AT TIME ZONE current_setting('TimeZone')) AT TIME ZONE 'UTC')::date"
)


def _log_day(alias: str) -> str:
    return _LOG_DAY.replace("log_date", f"{alias}.log_date")


def upgrade():
    for table in _TABLES:
        # Two rows can only land on the same day if one was written by a
        # build that stored log_date differently; both then count the same
        # log file, so keep the most recently updated one.
        op.execute(f"""
            DELETE FROM {table} a
            USING {table} b
            WHERE a.username       = b.username
              AND a.nas_ip         = b.nas_ip
              AND a.user_source_ip = b.user_source_ip
              AND a.node_name      = b.node_name
              AND {_log_day("a")} = {_log_day("b")}
              AND (a.updated_at, a.id) < (b.updated_at, b.id)
        """)
        op.alter_column(
            table,
            "log_date",
            type_=sa.Date(),
            existing_type=sa.DateTime(),
            existing_nullable=False,
            postgresql_using=_LOG_DAY,
        )


def downgrade():
    # Back to what the old code wrote: midnight UTC of the day, as seen in the
    # session time zone.
    for table in _TABLES:
        op.alter_column(
            table,
            "log_date",
            type_=sa.DateTime(),
            existing_type=sa.Date(),
            existing_nullable=False,
            postgresql_using=(
                "(log_date::timestamp AT TIME ZONE 'UTC')"
                " AT TIME ZONE current_setting('TimeZone')"
            ),
        )
