"""stats timezone: take TZ where the setting is still the UTC default

Revision ID: e7f2c4a8b153
Revises: d5e1b7a3c946
Create Date: 2026-11-06 00:00:00.000000

TacacsNgSetting.timezone decides which log file is "today" for the AAA
statistics. It was seeded from TACACS_TIMEZONE, which defaulted to "UTC" and
is not passed by docker-compose, so installs with a non-UTC TZ still counted
days in UTC (#356). The seed now defaults to TZ; this applies the same value
once to existing rows that still hold "UTC".

A "UTC" chosen on purpose is changed as well, since the two are
indistinguishable. The new value shows in TACACS NG Settings and can be set
back there; later changes are never touched again.

"""

import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "e7f2c4a8b153"
down_revision = "d5e1b7a3c946"
branch_labels = None
depends_on = None

logger = logging.getLogger("alembic.runtime.migration")


def zone_from_env(tz: str | None) -> str | None:
    """TZ, if it names a valid zone that is not UTC all year; else None."""
    if not tz:
        return None
    try:
        zone = ZoneInfo(tz)
    except Exception:
        return None
    offsets = {
        zone.utcoffset(datetime(2026, 1, 1)),
        zone.utcoffset(datetime(2026, 7, 1)),
    }
    if offsets == {timedelta(0)}:  # UTC in winter and in summer
        return None
    return tz


def upgrade():
    tz = zone_from_env(os.environ.get("TZ"))
    if tz is None:
        return
    result = op.get_bind().execute(
        sa.text("UPDATE tacacsngsetting SET timezone = :tz WHERE timezone = 'UTC'"),
        {"tz": tz},
    )
    if result.rowcount:
        logger.info("TACACS NG Settings timezone set from TZ: UTC -> %s", tz)


def downgrade():
    # Which rows were defaulted is not recorded, and the old code reads any
    # valid zone, so there is nothing to undo.
    pass
