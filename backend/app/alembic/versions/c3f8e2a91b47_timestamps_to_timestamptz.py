"""timestamp columns: timestamp → timestamptz

Revision ID: c3f8e2a91b47
Revises: a9c4e7f21d36
Create Date: 2026-11-07 18:00:00.000000

Every `timestamp without time zone` column becomes `timestamptz`.

The app wrote aware UTC values into naive columns, which PostgreSQL converts
to the session's TimeZone and stores as local wall time. Sessions used the
server default (the db container's TZ, e.g. Asia/Ho_Chi_Minh), so the stored
values are wall times in that zone. The app read them back as if they were
UTC, shifting alert cooldowns and every timestamp the API returned by the
server's UTC offset.

The USING clause reads each stored value in that same zone. This migration's
connection is not pinned (alembic/env.py), so current_setting('TimeZone') is
the server default the app wrote with. From here on core/db.py pins the app's
sessions to UTC.

Rewrites each listed table once; large auditlog tables take a moment.
"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "c3f8e2a91b47"
down_revision = "a9c4e7f21d36"
branch_labels = None
depends_on = None

# Snapshot at this revision; migrations must not import the models.
COLUMNS: dict[str, tuple[str, ...]] = {
    "accountingstatistics": ("created_at", "updated_at"),
    "alertevent": ("created_at", "updated_at", "triggered_at"),
    "alertrule": ("created_at", "updated_at", "last_fired_at"),
    "anomalydetectionresult": ("created_at", "updated_at", "scored_at"),
    "apikey": ("created_at", "updated_at"),
    "auditlog": ("created_at", "updated_at"),
    "authenticationhourlystatistics": ("created_at", "updated_at"),
    "authenticationstatistics": ("created_at", "updated_at"),
    "authorizationstatistics": ("created_at", "updated_at"),
    "authproviderconfig": ("created_at", "updated_at"),
    "configurationoption": ("created_at", "updated_at"),
    "haconfig": ("created_at", "updated_at"),
    "hanodestate": ("last_push_at",),
    "hapeernode": ("created_at", "updated_at"),
    "hastate": ("last_push_at", "last_received_at"),
    "host": ("created_at", "updated_at"),
    "item": ("created_at", "updated_at"),
    "mavis": ("created_at", "updated_at"),
    "notificationchannel": ("created_at", "updated_at"),
    "profile": ("created_at", "updated_at"),
    "profilescript": ("created_at", "updated_at"),
    "profilescriptset": ("created_at", "updated_at"),
    "ruleset": ("created_at", "updated_at"),
    "rulesetscript": ("created_at", "updated_at"),
    "rulesetscriptset": ("created_at", "updated_at"),
    "siemconfig": ("created_at", "updated_at"),
    "statsexcludeduser": ("created_at", "updated_at"),
    "tacacsconfig": ("created_at", "updated_at"),
    "tacacsgroup": ("created_at", "updated_at"),
    "tacacslog": ("created_at", "updated_at"),
    "tacacsngsetting": ("created_at", "updated_at"),
    "tacacsservice": ("created_at", "updated_at"),
    "tacacsuser": ("created_at", "updated_at"),
    "user": ("created_at", "updated_at"),
    "webauthchallenge": ("created_at",),
    "webauthncredential": ("created_at", "last_used_at"),
}


def _alter(table: str, columns: tuple[str, ...], type_: str) -> None:
    clauses = ", ".join(
        f'ALTER COLUMN "{c}" TYPE {type_} '
        f"USING \"{c}\" AT TIME ZONE current_setting('TimeZone')"
        for c in columns
    )
    op.execute(f'ALTER TABLE "{table}" {clauses}')


def upgrade() -> None:
    for table, columns in COLUMNS.items():
        _alter(table, columns, "timestamp with time zone")


def downgrade() -> None:
    # timestamptz AT TIME ZONE <zone> gives that zone's wall time back.
    for table, columns in COLUMNS.items():
        _alter(table, columns, "timestamp without time zone")
