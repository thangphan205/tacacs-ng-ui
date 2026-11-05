#!/bin/sh
#
# This script loads the full container environment and then executes the
# command passed to it. This ensures that cron jobs run with the same
# environment as the main application.

set -e

# Source the environment file created by the entrypoint script.
# The '.' command is a POSIX-compliant equivalent of 'source'.
. /etc/cron_env.sh

# A standby's database is a read-only streaming replica, so the nightly stats
# scripts would fail on every write. Skip them there.
if [ "${NODE_ROLE:-primary}" = "standby" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') NODE_ROLE=standby: skipping $*"
    exit 0
fi

# Execute the command passed to this script
exec "$@"