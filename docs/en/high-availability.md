# High Availability (HA) Deployment Guide

This guide explains how to run two tacacs-ng-ui instances across different zones so network devices always have a reachable TACACS+ server.

---

## Choose Your Deployment Model

| | **Model A — Independent** | **Model B — Primary–Standby** | **Model C — Multi-Node** |
|-|--------------------------|-------------------------------|--------------------------|
| Database | Each zone has its own DB | Zone B replicates from Zone A | N standbys replicate from primary |
| Config sync | Manual (admin manages both) | Automatic or one-click | Fan-out to all standbys |
| Complexity | Low | Medium | Medium |
| Failover | Devices switch server automatically | Promote standby with one command | Promote any standby |
| Best for | Zones serve different device populations, or full isolation needed | Single admin team, consistent config across zones | Multi-datacenter, >2 zones |

All models require no changes to existing deployments — Model A needs zero code changes.

---

## Model A — Independent (No Sync)

<p align="center">
  <img src="../../img/high-availability-model-a.svg" alt="Model A — Independent Deployment" width="800px" />
</p>

Two completely separate stacks. No connection between zones.

### Deploy Zone A

```bash
git clone <repo> && cd tacacs-ng-ui
cp .env.example .env
# Edit .env for Zone A (DOMAIN, SECRET_KEY, POSTGRES_*, etc.)
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

### Deploy Zone B

```bash
git clone <repo> && cd tacacs-ng-ui
cp .env.example .env
# Edit .env for Zone B — use different DOMAIN, SECRET_KEY, POSTGRES_PASSWORD
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

Each zone has its own admin dashboard. Config changes must be applied on both zones separately.

---

## Model B — Primary–Standby (Synced)

<p align="center">
  <img src="../../img/high-availability-model-b.svg" alt="Model B — Primary–Standby Deployment" width="800px" />
</p>

Zone A is the primary (all writes). Zone B is a hot standby — its PostgreSQL replicates from Zone A automatically. When config changes on Zone A, Zone B picks it up via [auto-sync or manual sync](#config-sync-modes).

### Prerequisites

**Ports required between zones:**

| Port | Direction | Purpose |
|------|-----------|---------|
| `5432` | Zone B → Zone A | PostgreSQL streaming replication |
| `8000` | Zone A → Zone B | Internal config reload trigger (optional, auto-sync only) |
| `49` | Network devices → both zones | TACACS+ authentication |
| `443` | Admin browsers → both zones | HTTPS dashboard |

> **Security:** Expose port 5432 only on a private/VPN network, never to the public internet.

---

### Step 1 — Deploy Zone A (Primary)

Add HA variables to Zone A's `.env`:

```bash
# Zone A .env additions
NODE_ROLE=primary
SCHEDULER_ENABLED=true
SYNC_MODE=auto            # or: manual
PEER_BACKEND_URL=https://api-b.yourdomain.com   # Zone B internal API URL — must include http:// or https://
INTERNAL_SYNC_TOKEN=<generate-with: openssl rand -hex 32>
```

> **`PEER_BACKEND_URL` must include the scheme.** Use `http://172.25.x.x:8000` for direct IP access or `https://api-b.yourdomain.com` for domain-based setups. Omitting the scheme (e.g. `172.25.x.x:8000`) causes httpx to fail silently and peer health checks to always return unreachable.

Run the one-click setup script (handles stack startup + replication config):

```bash
bash setup-ha.sh
```

The script:
1. Starts `docker compose up -d`
2. Waits for PostgreSQL to be ready
3. Creates the `replicator` role (idempotent — skips if already exists)
4. Resolves Zone B IP from `PEER_BACKEND_URL` and adds it to `pg_hba.conf`
5. Reloads PostgreSQL config (no restart needed)

<details>
<summary>Manual alternative (if you prefer step-by-step)</summary>

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d

# Create replication role (load .env variables first to resolve $POSTGRES_USER)
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER -c \
  "CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'your-replication-password';"

# Allow Zone B IP to connect for replication
# ↓ Replace with your actual Zone B IP address
ZONE_B_IP=192.168.1.100

docker compose exec db bash -c \
  "echo 'host replication replicator ${ZONE_B_IP}/32 md5' >> \$PGDATA/pg_hba.conf"

# Reload PostgreSQL config (no restart needed)
docker compose kill -s HUP db
```

</details>

---

### Step 2 — Deploy Zone B (Standby)

Clone the repo on Zone B and configure `.env`:

```bash
git clone <repo> && cd tacacs-ng-ui
cp .env.example .env
```

Zone B `.env` — same base settings as Zone A, plus:

```bash
# Zone B — same as Zone A except these overrides:
NODE_ROLE=standby
SCHEDULER_ENABLED=false           # alerts, ML scoring, cron run on Zone A only
SYNC_MODE=auto                    # or: manual
PEER_BACKEND_URL=https://api-a.yourdomain.com   # Zone A URL — must include http:// or https://
INTERNAL_SYNC_TOKEN=<same-value-as-zone-a>
PRIMARY_DB_HOST=<ZONE_A_IP>       # IP only, no port (e.g. 172.25.245.214)
REPLICATION_PASSWORD=your-replication-password

# Point Zone B to its own local LDAP server (see MAVIS section below)
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ldap-zone-b.yourdomain.com:636
```

Run the one-click setup script (does pg_basebackup + starts all services):

```bash
bash setup-ha.sh
```

The script:
1. Pulls Docker images
2. Runs `pg_basebackup` from Zone A over PostgreSQL port 5432 (no SSH needed)
3. Writes streaming replication config (`standby.signal`, `primary_conninfo`)
4. Starts `docker compose up -d`
5. Verifies replication is active

**Verify replication is working:**

```bash
# Load .env variables into current shell first
export $(grep -v '^#' .env | xargs)

# On Zone B — should return: t (true = standby mode)
docker compose exec db psql -U $POSTGRES_USER -c "SELECT pg_is_in_recovery();"

# On Zone A — should show Zone B connected
docker compose exec db psql -U $POSTGRES_USER -c "SELECT * FROM pg_stat_replication;"
```

---

### Config Sync Modes

Set `SYNC_MODE` in Zone B's `.env` to control how tac_plus-ng picks up config changes from Zone A.

#### `SYNC_MODE=auto` (default)

Zone B's `config_sync_watcher` daemon polls the local (replicated) DB every 10 seconds. When it detects a config change, it regenerates `tac_plus-ng.cfg` and reloads the daemon automatically — no admin action needed.

**Flow:**
1. Admin changes policy on Zone A dashboard → activates config
2. Zone A API reloads its own tac_plus-ng daemon
3. Zone A API calls Zone B's internal reload endpoint (fire-and-forget)
4. Zone B regenerates config from local replicated DB + reloads daemon
5. Both zones are consistent within ~10 seconds

#### `SYNC_MODE=manual`

Zone B does **not** auto-reload. The DB replicates continuously (users, policies always in sync), but tac_plus-ng only picks up new config when the admin explicitly pushes it.

**How to push:**

- **Dashboard:** Click **"Sync to Zone B"** button on the TACACS+ Configuration page (visible only on primary node with manual sync mode)
- **API:**
  ```bash
  curl -X POST https://api-a.yourdomain.com/api/v1/sync/push-config \
    -H "Authorization: Bearer <your-token>"
  ```

Use manual mode when you want to validate config on Zone A first before it reaches Zone B.

---

## Per-Node AAA Statistics

In a multi-node deployment each TACACS-NG node serves its own traffic and writes its own local log files. The primary node collects statistics from all peers and stores them tagged with each node's `NODE_NAME`, so the dashboard can show per-node breakdowns and side-by-side comparisons.

### How It Works

```
Primary                     Standby(s)
  │                              │
  │  POST /internal/collect-stats│
  │ ─────────────────────────────►
  │                              │
  │  { node_name, auth, authz,   │
  │    accounting stats (JSON) } │
  │ ◄─────────────────────────── │
  │                              │
  upsert rows tagged with        │
  standby's NODE_NAME into DB    │
```

1. **Primary** runs its own cron scripts (saves stats with its `NODE_NAME`)
2. **Primary** calls `POST /api/v1/sync/internal/collect-stats?date=YYYY-MM-DD` on each peer listed in `PEER_NODES`
3. **Standby** parses its local log files and returns raw JSON — it does **not** write to its read-only DB
4. **Primary** upserts the received stats into the primary DB, tagged with the standby's `NODE_NAME`

Authentication uses the shared `INTERNAL_SYNC_TOKEN` header (`X-Internal-Token`).

### Configuration

**Primary `.env`:**

```bash
NODE_NAME=dc1-primary          # identifies this node in stats
PEER_NODES=http://dc2-standby:8000,http://dc3-standby:8000   # comma-separated
INTERNAL_SYNC_TOKEN=<same-secret-as-standbys>
STATS_INTERVAL_MINUTES=30      # collect today's stats every 30 minutes (0 = disable)
```

**Each Standby `.env`:**

```bash
NODE_NAME=dc2-standby          # must be unique per node
INTERNAL_SYNC_TOKEN=<same-secret-as-primary>
# PEER_NODES not required on standbys (only primary orchestrates)
```

### Near Real-Time Stats Collection

The primary backend runs a background loop that collects today's statistics on a configurable interval. This keeps the range and node comparison pages fresh without waiting for the 1 AM nightly cron.

| Setting | Default | Effect |
|---------|---------|--------|
| `STATS_INTERVAL_MINUTES=30` | 30 | Collect today's stats every 30 minutes |
| `STATS_INTERVAL_MINUTES=5` | — | Near real-time (higher CPU/DB load) |
| `STATS_INTERVAL_MINUTES=1` | — | Real-time (only if log files are small) |
| `STATS_INTERVAL_MINUTES=0` | — | Disable background loop (nightly cron only) |

The loop also calls all peers in `PEER_NODES` on the same interval, so standby stats stay current.

**Dashboard auto-refresh:** All three stats pages (Today, Range, Node Comparison) automatically re-fetch data from the backend every 5 minutes while the browser tab is open.

### Dashboard Features

| Page | Path | Description |
|------|------|-------------|
| AAA Statistics (Today) | Sidebar → AAA Statistics | Node filter dropdown — filter today's stats by node |
| AAA Statistics Range | Sidebar → AAA Range Stats | Node filter dropdown — filter date-range stats by node |
| Node Comparison | Sidebar → Node Comparison | Side-by-side cards: one per node, showing stat totals + trend chart |

### Trigger Collection Manually

```bash
# Force-collect stats for today across all nodes
curl -X POST -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/aaa_statistics/run/

# Collect for a specific date
curl -X POST -H "Authorization: Bearer <token>" \
  "https://api-a.yourdomain.com/api/v1/aaa_statistics/run/?date=2026-06-25"
```

The endpoint runs own-node scripts and then calls each peer in `PEER_NODES`.

### List Available Nodes

```bash
curl -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/aaa_statistics/nodes/
# ["dc1-primary", "dc2-standby", "dc3-standby"]
```

---

## Standby Node Behavior

When `NODE_ROLE=standby`, the backend behaves differently to protect the read-only replica DB:

| Feature | Primary | Standby |
|---------|---------|---------|
| Write to DB (users, configs, policies) | ✅ | ❌ HTTP 403 |
| Read from DB (dashboard, logs, stats) | ✅ | ✅ |
| Audit log writes | ✅ | ⏭ Silently skipped (replicated from primary) |
| DB migrations on startup | ✅ | ⏭ Skipped (schema arrives via replication) |
| Alert evaluation / ML scoring / cron | ✅ | ❌ Disabled (`SCHEDULER_ENABLED=false`) |
| TACACS+ authentication (port 49) | ✅ | ✅ |
| Dashboard — view | ✅ | ✅ |
| Dashboard — edit | ✅ | ❌ Blocked with "read-only mode" message |

### HA Status Dashboard

The sidebar includes a **High Availability** page (under Monitoring) that shows real-time sync status for both nodes. It auto-refreshes every 30 seconds and displays:

- Node role (Primary / Standby)
- Peer connection status (Connected / Unreachable)
- Sync mode (Auto / Manual)
- Last config sync timestamp
- Manual sync button (primary + manual mode only)

---

## MAVIS / LDAP Per-Zone Configuration

Each zone can point to a different LDAP server using `MAVIS_OVERRIDE_*` env vars. These override specific MAVIS keys from the database at config-generation time — no schema change needed.

```bash
# Zone A .env
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ldap-zone-a.yourdomain.com:636

# Zone B .env
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ldap-zone-b.yourdomain.com:636
```

Any MAVIS key stored in the database can be overridden:

```bash
MAVIS_OVERRIDE_LDAP_SERVER_TYPE=freeipa
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ipa-zone-b.example.com:636
MAVIS_OVERRIDE_LDAP_BASE=dc=example,dc=com
MAVIS_OVERRIDE_LDAP_USER=uid=svc_tacacs,cn=users,cn=accounts,dc=example,dc=com
MAVIS_OVERRIDE_LDAP_PASSWD=zone-b-service-account-password
```

If no override is set, the database value is used (same on both zones).

---

## Network Device Configuration

Configure all network devices with both zone IPs. The device tries Zone A first and fails over to Zone B within the TACACS timeout (typically 5 seconds).

**Cisco IOS / IOS-XE:**

```
aaa group server tacacs+ TACACS_HA
 server-private <ZONE_A_IP> key <your-secret>
 server-private <ZONE_B_IP> key <your-secret>
 ip tacacs source-interface Loopback0

aaa authentication login default group TACACS_HA local
aaa authorization exec default group TACACS_HA local
aaa authorization commands 15 default group TACACS_HA local
aaa accounting exec default start-stop group TACACS_HA
```

**Juniper Junos:**

```
system {
    tacplus-server {
        <ZONE_A_IP> {
            secret "<your-secret>";
            timeout 5;
        }
        <ZONE_B_IP> {
            secret "<your-secret>";
            timeout 5;
        }
    }
    authentication-order [ tacplus password ];
}
```

**Arista EOS:**

```
tacacs-server host <ZONE_A_IP> key <your-secret>
tacacs-server host <ZONE_B_IP> key <your-secret>

aaa group server tacacs+ TACACS_HA
   server <ZONE_A_IP>
   server <ZONE_B_IP>
```

---

## Upgrading to a New Version

> **How it works:** DB schema migrations run on Zone A only. PostgreSQL replication delivers the schema change to Zone B automatically before Zone B restarts — no migration runs on the standby.

### Rolling upgrade (zero TACACS downtime)

```bash
# ── On BOTH zones ──────────────────────────────────────────────
git pull origin main

# ── Zone A first ───────────────────────────────────────────────
# Devices fail over to Zone B during Zone A restart (~5 s)
docker compose up -d --build backend

# Wait until Zone A is healthy and migration has replicated to Zone B
docker compose logs -f backend | grep "Application startup complete"

# ── Zone B second ──────────────────────────────────────────────
# Devices fail over to Zone A during Zone B restart (~5 s)
docker compose up -d --build backend
```

That's it. TACACS authentication is never interrupted — devices use the other zone while each backend restarts.

### If a migration adds a new NOT NULL column

Alembic migrations in this project always include `server_default` on NOT NULL columns so they apply online without locking. No extra steps needed.

### Verify after upgrade

```bash
# Zone A — confirm new version running
docker compose exec backend python -c "import app; print('ok')"

# Zone B — confirm replication lag is low
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER -c \
  "SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;"
```

---

## Model C — Multi-Node (N Standbys)

For deployments with more than two zones (e.g. DC1 primary + DC2 + DC3 standbys).

The architecture is identical to Model B, with one primary and N standbys. Config sync fans out to all enabled peer nodes automatically.

### Step 1 — Deploy the Primary Node

Follow [Model B Step 1](#step-1--deploy-zone-a-primary) exactly — configure `.env` with `NODE_ROLE=primary` and run `bash setup-ha.sh` on the primary server. No additional steps needed for multi-node; peer standbys are added via the UI after they come up.

### Step 2 — Deploy Each Standby Node

For each standby, follow [Model B Step 2](#step-2--deploy-zone-b-standby) — configure `.env` with `NODE_ROLE=standby`, unique `NODE_NAME`, and `PRIMARY_DB_HOST` pointing to the primary, then run `bash setup-ha.sh`.

### Adding a Third (or More) Standby

1. Set up PostgreSQL streaming replication from primary DB to new standby DB (same as Zone B setup above)
2. Start the new standby with `NODE_ROLE=standby` and the same `INTERNAL_SYNC_TOKEN`
3. On the primary UI → **High Availability → Peers → Add Peer** (enter a name and the new standby's internal URL)
4. Config syncs to the new node within 10 seconds (auto mode) or on next manual push — no restart needed

> **No env var changes required.** Peer management is done entirely via the UI. `PEER_NODES` / `PEER_BACKEND_URL` env vars are still supported as a fallback and are automatically imported into the DB on first startup.

### HA Configuration via UI

All HA settings except `NODE_ROLE` and `INTERNAL_SYNC_TOKEN` are now editable via the **High Availability → HA Settings** panel on the primary node — no restart needed:

| Setting | Description |
|---------|-------------|
| Node name | Human-readable label (e.g. "DC1-Primary") |
| Sync mode | `auto` or `manual` |
| Scheduler enabled | Enable/disable alert evaluation, ML scoring, audit purge |
| Stats interval | AAA stats collection interval in minutes (0 = disable) |

### Multi-Node Status

`GET /api/v1/sync/ha-info` returns a `peers` array with per-node status:

```json
{
  "node_role": "primary",
  "node_name": "DC1-Primary",
  "sync_mode": "auto",
  "peers": [
    {"id": "...", "name": "DC2-Standby", "url": "http://dc2:8000", "available": true, "last_push_at": "2026-06-26T14:00:00Z"},
    {"id": "...", "name": "DC3-Standby", "url": "http://dc3:8000", "available": true, "last_push_at": "2026-06-26T14:00:00Z"}
  ]
}
```

### Peer Management API (superuser only)

```bash
# List peers
curl -H "Authorization: Bearer <token>" https://api-a.yourdomain.com/api/v1/sync/peers

# Add a peer
curl -X POST -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"name": "DC3-Standby", "url": "http://dc3:8000", "enabled": true}' \
  https://api-a.yourdomain.com/api/v1/sync/peers

# Disable a peer (temporarily exclude from sync)
curl -X PATCH -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"enabled": false}' \
  https://api-a.yourdomain.com/api/v1/sync/peers/<peer-id>

# Remove a peer
curl -X DELETE -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/sync/peers/<peer-id>
```

---

## Failover Procedure (Zone A dies)

**Promote a standby to primary (via UI — recommended):**

On the standby UI → **High Availability → Promote to Primary**. The UI runs `pg_promote()`, sets `scheduler_enabled=true` in the DB, and shows the remaining manual steps.

**Promote via CLI:**

```bash
# On the standby server
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER -c "SELECT pg_promote();"

# Update .env — only NODE_ROLE needs changing (scheduler_enabled is DB-driven now):
#   NODE_ROLE=primary

docker compose up -d backend
```

Zone B now accepts all writes. Network devices were already pointed at Zone B, so TACACS authentication continues without change.

**After promotion — clean up peers:**

1. Open the promoted node's HA dashboard
2. Remove the old primary from the Peers table (it's now unreachable)
3. For each remaining standby: repoint PostgreSQL replication to the new primary (`pg_rewind` or `pg_basebackup`)

**When the old primary recovers:**

Re-join as a new standby:

```bash
# On the old primary server
# Update .env:
#   NODE_ROLE=standby
#   PRIMARY_DB_HOST=<NEW_PRIMARY_IP>

bash setup-ha.sh
```

Then add it back as a peer via the new primary's HA UI.

---

## Environment Variable Reference

All HA variables are optional. Defaults run as a standard single-node deployment.

> **Note:** `NODE_NAME`, `SCHEDULER_ENABLED`, `SYNC_MODE`, `PEER_BACKEND_URL`, `PEER_NODES`, and `STATS_INTERVAL_MINUTES` are seeded into the database on first primary startup and can then be changed via the HA UI without a restart. `NODE_ROLE` and `INTERNAL_SYNC_TOKEN` always require a restart to change.

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ROLE` | `primary` | **Env-only.** `primary` or `standby`. Controls write access and `require_primary_node()` guard. Requires restart. |
| `INTERNAL_SYNC_TOKEN` | _(empty)_ | **Env-only.** Shared secret for inter-node calls. Must match on all nodes. Generate with `openssl rand -hex 32`. Requires restart. |
| `NODE_NAME` | `primary` | Seeded into DB on first startup. Human-readable node label (e.g. `dc1-primary`). Edit via HA UI after first start. |
| `SCHEDULER_ENABLED` | `true` | Seeded into DB on first startup. Set `false` on standby to disable alerts/ML/audit loops. Edit via HA UI after promotion. |
| `SYNC_MODE` | `auto` | Seeded into DB on first startup. `auto` = standby polls DB every 10 s. `manual` = admin-triggered. Edit via HA UI. |
| `PEER_BACKEND_URL` | _(empty)_ | Seeded as first peer entry on first primary startup. Use HA UI to manage peers after that. |
| `PEER_NODES` | _(empty)_ | Seeded as multiple peer entries on first primary startup (comma-separated URLs). Use HA UI to manage after that. |
| `STATS_INTERVAL_MINUTES` | `30` | Seeded into DB on first startup. Minutes between primary AAA stats collection cycles. `0` = nightly cron only. Edit via HA UI. |
| `PRIMARY_DB_HOST` | _(empty)_ | Zone A's DB host IP. Only needed on standby during `setup-standby.sh`. |
| `REPLICATION_PASSWORD` | _(empty)_ | Password for the `replicator` PostgreSQL role. Only needed on standby. |
| `MAVIS_OVERRIDE_<KEY>` | _(empty)_ | Override any MAVIS key per zone (e.g. `MAVIS_OVERRIDE_LDAP_HOSTS`). |
| `SYNC_WATCHER_INTERVAL` | `10` | Seconds between config change polls (auto-sync watcher, standby only). |

---

## HA Status API

**Check node role and peer health:**

```bash
curl -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/sync/ha-info
```

Response:

```json
{
  "node_role": "primary",
  "node_name": "DC1-Primary",
  "sync_mode": "manual",
  "scheduler_enabled": true,
  "stats_interval_minutes": 30,
  "peers": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "name": "DC2-Standby",
      "url": "https://api-b.yourdomain.com",
      "enabled": true,
      "available": true,
      "last_push_at": "2026-06-25T08:12:34.567890+00:00"
    }
  ],
  "peer_backend_url": "https://api-b.yourdomain.com",
  "peer_available": true,
  "last_sync_at": "2026-06-25T08:12:34.567890+00:00"
}
```

> `peer_backend_url` and `peer_available` are kept for backward compatibility. Prefer the `peers` array for multi-node deployments.

**Manually push config to all standbys (manual sync mode):**

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/sync/push-config
```

Response shows per-peer result:

```json
{
  "results": [
    {"peer": "DC2-Standby", "url": "https://api-b.yourdomain.com", "status": "ok"},
    {"peer": "DC3-Standby", "url": "https://api-c.yourdomain.com", "status": "error"}
  ]
}
```

---

## Verify End-to-End

After both zones are up:

1. **DB replication:** Create a user on Zone A dashboard → immediately visible on Zone B dashboard
2. **Config sync (auto):** Generate and activate config on Zone A → Zone B reloads within 10 seconds
3. **Config sync (manual):** Generate and activate config on Zone A → click "Sync to Zone B" → Zone B reloads
4. **TACACS failover:** Stop Zone A backend → network device auth succeeds via Zone B within 5 seconds
5. **Alert deduplication:** Trigger an alert condition → only one notification received (scheduler disabled on Zone B)
6. **LDAP override:** Zone B auth uses `MAVIS_OVERRIDE_LDAP_HOSTS` — verify with `docker compose exec backend cat /app/tacacs_config/etc/tac_plus-ng.cfg | grep LDAP_HOSTS`
