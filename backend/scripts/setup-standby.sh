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

# Step 2: Resolve the Docker volume name for the DB data directory.
# Docker Compose prefixes volumes with the project name (derived from compose config,
# not the directory name, to be safe).
echo "[2/5] Running pg_basebackup from primary ($PRIMARY_DB_HOST)..."

COMPOSE_PROJECT="$(docker compose config --format json 2>/dev/null \
  | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('name',''))" 2>/dev/null \
  || echo "")"
if [[ -z "$COMPOSE_PROJECT" ]]; then
  COMPOSE_PROJECT="${STACK_NAME:-$(basename "$(pwd)")}"
fi
PG_DATA_VOLUME="${COMPOSE_PROJECT}_app-db-data"
echo "Using DB volume: $PG_DATA_VOLUME"

# Run pg_basebackup inside a temporary postgres container that shares the DB volume.
# Mount the volume at the same path the db service uses (/var/lib/postgresql/data/pgdata)
# so pg_basebackup writes PG files directly into the volume root — not a subdirectory.
docker run --rm \
  -e PGPASSWORD="$REPLICATION_PASSWORD" \
  -v "${PG_DATA_VOLUME}:/var/lib/postgresql/data/pgdata" \
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

# Step 3: Write primary_conninfo into postgresql.auto.conf.
# Password is passed via env var and escaped inside the container to avoid:
#   - shell quoting issues in the outer script
#   - single-quote injection into the PostgreSQL connection string
echo "[3/5] Writing standby replication config..."
docker run --rm -i \
  -e REPL_HOST="$PRIMARY_DB_HOST" \
  -e REPL_PORT="$POSTGRES_PORT" \
  -e REPL_PASS="$REPLICATION_PASSWORD" \
  -v "${PG_DATA_VOLUME}:/var/lib/postgresql/data/pgdata" \
  postgres:18 \
  bash << 'INNERSCRIPT'
pgdata=/var/lib/postgresql/data/pgdata
# Escape for PostgreSQL libpq connection string: \ -> \\ then ' -> \'
p="${REPL_PASS//\\/\\\\}"
p="${p//\'/\\\'}"
{
  printf '\n# HA streaming replication (written by setup-standby.sh)\n'
  printf "primary_conninfo = 'host=%s port=%s user=replicator password=%s application_name=standby'\n" \
    "$REPL_HOST" "$REPL_PORT" "$p"
  printf "recovery_target_timeline = 'latest'\n"
} >> "$pgdata/postgresql.auto.conf"
touch "$pgdata/standby.signal"
echo "Replication config written."
INNERSCRIPT

echo "[4/5] Starting all services..."
docker compose up -d

echo "[5/5] Verifying replication..."
echo "Waiting for PostgreSQL to start in standby mode (up to 30s)..."
VERIFIED=0
for i in $(seq 1 30); do
  result=$(docker compose exec -T db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
    -tAc "SELECT pg_is_in_recovery();" 2>/dev/null || echo "")
  if [[ "$result" == "t" ]]; then
    docker compose exec db psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
      -c "SELECT pg_is_in_recovery() AS is_standby, now() - pg_last_xact_replay_timestamp() AS replication_lag;"
    VERIFIED=1
    break
  fi
  sleep 1
done

if [[ "$VERIFIED" -eq 0 ]]; then
  echo "WARNING: Replication not confirmed after 30s. Check with: docker compose logs db" >&2
fi

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
