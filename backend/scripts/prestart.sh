#! /usr/bin/env bash

set -e
set -x

# Let the DB start (safe on both primary and standby — only runs SELECT 1)
python app/backend_pre_start.py

if [ "${NODE_ROLE:-primary}" = "standby" ]; then
    # Standby DB is a read-only streaming replica of primary.
    # Schema changes and initial data arrive via PostgreSQL replication — no writes needed here.
    echo "Standby node: skipping migrations and initial data seeding."
else
    # Run migrations
    alembic upgrade head

    # Create initial data in DB
    python app/initial_data.py
fi
