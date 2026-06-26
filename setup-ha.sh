#!/usr/bin/env bash
# setup-ha.sh — One-click high availability setup script.
#
# Usage:
#   1. Configure .env file on this node.
#   2. Run: bash setup-ha.sh

set -euo pipefail

ENV_FILE="./.env"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: .env file not found. Please copy .env.example to .env and configure it first." >&2
  exit 1
fi

# Load .env values
set -a; source "$ENV_FILE"; set +a

NODE_ROLE="${NODE_ROLE:-primary}"

echo "=== tacacs-ng-ui HA Setup ==="
echo "Node Role: $NODE_ROLE"
echo "============================="

if [[ "$NODE_ROLE" == "primary" ]]; then
  echo "[1/4] Starting primary docker compose stack..."
  docker compose up -d

  # Wait for DB to be ready
  echo "[2/4] Waiting for PostgreSQL database to be ready..."
  until docker compose exec db pg_isready -U "${POSTGRES_USER:-postgres}" >/dev/null 2>&1; do
    sleep 1
  done

  # Create replication role
  if [[ -z "${REPLICATION_PASSWORD:-}" ]]; then
    echo "ERROR: REPLICATION_PASSWORD is not configured in .env" >&2
    exit 1
  fi

  echo "[3/4] Configuring replication role..."
  role_exists=$(docker compose exec db psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-app}" -tAc "SELECT 1 FROM pg_roles WHERE rolname='replicator';" 2>/dev/null || echo "")
  if [[ "$role_exists" != "1" ]]; then
    echo "Creating 'replicator' role..."
    docker compose exec db psql -U "${POSTGRES_USER:-postgres}" -d "${POSTGRES_DB:-app}" -c \
      "CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '$REPLICATION_PASSWORD';"
  else
    echo "Replication role 'replicator' already exists."
  fi

  # Parse and allow peer IP
  echo "[4/4] Configuring replication client access..."
  PEER_IP=""
  if [[ -n "${PEER_BACKEND_URL:-}" ]]; then
    PEER_HOST=$(python3 -c "from urllib.parse import urlparse; print(urlparse('$PEER_BACKEND_URL').hostname or '')" 2>/dev/null || echo "")
    if [[ -n "$PEER_HOST" ]]; then
      echo "Resolving peer host '$PEER_HOST'..."
      PEER_IP=$(python3 -c "import socket; print(socket.gethostbyname('$PEER_HOST'))" 2>/dev/null || echo "")
    fi
  fi

  if [[ -z "$PEER_IP" ]]; then
    echo "Could not automatically resolve standby node IP from PEER_BACKEND_URL."
    read -rp "Please enter the standby node IP address (or leave empty to skip pg_hba.conf configuration): " input_ip
    PEER_IP="${input_ip// /}"
  fi

  if [[ -n "$PEER_IP" ]]; then
    echo "Standby Node IP: $PEER_IP"
    # Check if already added
    has_hba=$(docker compose exec db bash -c "grep -F '$PEER_IP/32' \$PGDATA/pg_hba.conf || true")
    if [[ -z "$has_hba" ]]; then
      echo "Adding replication entry to pg_hba.conf..."
      docker compose exec db bash -c "echo 'host replication replicator $PEER_IP/32 md5' >> \$PGDATA/pg_hba.conf"
      echo "Reloading PostgreSQL configuration..."
      docker compose kill -s HUP db
    else
      echo "Replication entry for $PEER_IP already exists in pg_hba.conf."
    fi
  else
    echo "Skipping pg_hba.conf peer configuration."
  fi

  echo ""
  echo "=== Primary Setup Complete ==="
  echo "You can now run setup-ha.sh on the standby node."

elif [[ "$NODE_ROLE" == "standby" ]]; then
  echo "Starting standby node bootstrap..."
  bash backend/scripts/setup-standby.sh

else
  echo "ERROR: Invalid NODE_ROLE '$NODE_ROLE' in .env. Must be 'primary' or 'standby'." >&2
  exit 1
fi
