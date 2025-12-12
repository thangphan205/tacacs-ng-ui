#!/bin/sh

# This script is the entrypoint for the container. It ensures that the cron
# daemon has access to the same environment variables as the main application.

set -e

# Start supervisord, which will manage the main app and the cron daemon.
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/supervisord.conf