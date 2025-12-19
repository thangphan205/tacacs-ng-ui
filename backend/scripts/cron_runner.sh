#!/bin/sh
#
# This script loads the full container environment and then executes the
# command passed to it. This ensures that cron jobs run with the same
# environment as the main application.

set -e

# Source the environment file created by the entrypoint script.
# The '.' command is a POSIX-compliant equivalent of 'source'.
. /etc/cron_env.sh

# Execute the command passed to this script
exec "$@"