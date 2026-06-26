#!/usr/bin/env bash
# setup-standby.sh — Bootstrap Zone B as a PostgreSQL streaming replica of Zone A.
#
# Prerequisites:
#   - docker compose stack is NOT yet running on this server
#   - .env is configured with NODE_ROLE=standby, PRIMARY_DB_HOST, REPLICATION_PASSWORD,
#     POSTGRES_USER, POSTGRES_DB, POSTGRES_PASSWORD, SCHEDULER_ENABLED=false
#
# Run once on Zone B before starting the stack.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$(cd "$SCRIPT_DIR/../.." && pwd)/.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env file not found at $ENV_FILE" >&2
  exit 1
fi

# Load .env values
set -a; source "$ENV_FILE"; set +a

: "${PRIMARY_DB_HOST:?ERROR: PRIMARY_DB_HOST must be set in .env}"
: "${REPLICATION_PASSWORD:?ERROR: REPLICATION_PASSWORD must be set in .env}"
: "${POSTGRES_USER:?ERROR: POSTGRES_USER must be set in .env}"
: "${POSTGRES_PASSWORD:?ERROR: POSTGRES_PASSWORD must be set in .env}"
: "${POSTGRES_DB:?ERROR: POSTGRES_DB must be set in .env}"
: "${POSTGRES_PORT:=5432}"

echo "=== tacacs-ng-ui HA Standby Setup ==="
echo "Primary DB host : $PRIMARY_DB_HOST:$POSTGRES_PORT"
echo "Node role       : ${NODE_ROLE:-standby}"
echo ""

# Step 1: Build/pull images and create volumes without starting services
echo "[1/5] Building/pulling images..."
# Pull third-party images (db, proxy, etc.); ignore failures for locally-built images
docker compose pull --ignore-pull-failures || true
# Build backend and frontend from source (handles local-only images with no registry)
docker compose build

# Step 2: Start only the db container with a temporary entry point to do pg_basebackup
echo "[2/5] Running pg_basebackup from primary ($PRIMARY_DB_HOST)..."

PG_DATA_VOLUME="$(docker compose config --format json 2>/dev/null | python3 -c "
import json,sys
cfg = json.load(sys.stdin)
vols = cfg.get('volumes', {})
# find the volume used by db service
for svc_name, svc in cfg.get('services', {}).items():
    if svc_name == 'db':
        for m in svc.get('volumes', []):
            if isinstance(m, dict) and 'pgdata' in m.get('target', ''):
                print(m['source'])
                sys.exit(0)
" 2>/dev/null || echo "")"

if [[ -z "$PG_DATA_VOLUME" ]]; then
  PG_DATA_VOLUME="$(docker compose ps -q db 2>/dev/null || true)"
  PG_DATA_VOLUME="app-db-data"
fi

# Run pg_basebackup inside a temporary postgres container that shares the DB volume.
# Mount the volume at the same path the db service uses (/var/lib/postgresql/data/pgdata)
# so pg_basebackup writes PG files directly into the volume root — not a subdirectory.
docker run --rm \
  -e PGPASSWORD="$REPLICATION_PASSWORD" \
  -v "${STACK_NAME:-tacacs-ng-ui}_app-db-data:/var/lib/postgresql/data/pgdata" \
  postgres:18 \
  bash -c "
    find /var/lib/postgresql/data/pgdata -mindepth 1 -delete 2>/dev/null || true
    pg_basebackup \
      -h $PRIMARY_DB_HOST \
      -p $POSTGRES_PORT \
      -U replicator \
      -D /var/lib/postgresql/data/pgdata \
      -Fp -Xs -P -R
  "

echo "[3/5] Writing standby replication config..."
docker run --rm \
  -v "${STACK_NAME:-tacacs-ng-ui}_app-db-data:/var/lib/postgresql/data/pgdata" \
  postgres:18 \
  bash -c "
    cat >> /var/lib/postgresql/data/pgdata/postgresql.auto.conf <<EOF

# HA streaming replication (written by setup-standby.sh)
primary_conninfo = 'host=$PRIMARY_DB_HOST port=$POSTGRES_PORT user=replicator password=$REPLICATION_PASSWORD application_name=standby'
recovery_target_timeline = 'latest'
EOF
    # standby.signal tells PostgreSQL to start in standby (hot standby) mode
    touch /var/lib/postgresql/data/pgdata/standby.signal
  "

echo "[4/5] Starting all services..."
docker compose up -d

echo "[5/5] Verifying replication..."
sleep 10
docker compose exec db psql \
  -U "$POSTGRES_USER" \
  -d "$POSTGRES_DB" \
  -c "SELECT pg_is_in_recovery() AS is_standby, now() - pg_last_xact_replay_timestamp() AS replication_lag;"

echo ""
echo "=== Setup complete ==="
echo "Zone B is now running as a hot standby replica of $PRIMARY_DB_HOST."
echo ""
echo "Dashboard : https://${DOMAIN:-localhost}"
echo "API       : ${VITE_API_URL:-https://api.${DOMAIN:-localhost}}"
echo ""
echo "To verify ongoing replication, run on Zone A:"
echo "  docker compose exec db psql -U \$POSTGRES_USER -c 'SELECT * FROM pg_stat_replication;'"
echo ""
echo "To promote Zone B to primary (failover):"
echo "  docker compose exec db psql -U \$POSTGRES_USER -c 'SELECT pg_promote();'"
echo "  # Then update .env: NODE_ROLE=primary  SCHEDULER_ENABLED=true"
echo "  docker compose up -d backend"
