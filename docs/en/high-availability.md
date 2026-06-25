# High Availability (HA) Deployment Guide

This guide explains how to run two tacacs-ng-ui instances across different zones so network devices always have a reachable TACACS+ server.

---

## Choose Your Deployment Model

| | **Model A — Independent** | **Model B — Primary–Standby** |
|-|--------------------------|-------------------------------|
| Database | Each zone has its own DB | Zone B replicates from Zone A |
| Config sync | Manual (admin manages both) | Automatic or one-click |
| Complexity | Low | Medium |
| Failover | Devices switch server automatically | Promote standby with one command |
| Best for | Zones serve different device populations, or full isolation needed | Single admin team, consistent config across zones |

Both models require no changes to existing deployments — Model A needs zero code changes.

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
PEER_BACKEND_URL=https://api-b.yourdomain.com   # Zone B internal API URL
INTERNAL_SYNC_TOKEN=<generate-with: openssl rand -hex 32>
```

Deploy normally:

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

Enable PostgreSQL replication (run once after Zone A is healthy):

```bash
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
PEER_BACKEND_URL=https://api-a.yourdomain.com   # Zone A URL
INTERNAL_SYNC_TOKEN=<same-value-as-zone-a>
PRIMARY_DB_HOST=<ZONE_A_IP>
REPLICATION_PASSWORD=your-replication-password

# Point Zone B to its own local LDAP server (see MAVIS section below)
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ldap-zone-b.yourdomain.com:636
```

Run the standby bootstrap script (does pg_basebackup + starts all services):

```bash
bash backend/scripts/setup-standby.sh
```

The script:
1. Pulls Docker images
2. Runs `pg_basebackup` from Zone A over PostgreSQL port 5432 (no SSH needed)
3. Writes streaming replication config (`standby.signal`, `primary_conninfo`)
4. Starts `docker compose up -d`
5. Verifies replication is active

**Verify replication is working:**

```bash
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

## Failover Procedure (Zone A dies)

**Promote Zone B to primary:**

```bash
# On Zone B server
docker compose exec db psql -U $POSTGRES_USER -c "SELECT pg_promote();"

# Update Zone B .env:
#   NODE_ROLE=primary
#   SCHEDULER_ENABLED=true

docker compose up -d backend
```

Zone B now accepts all writes. Network devices were already pointed at Zone B, so TACACS authentication continues without change.

**When Zone A recovers:**

Re-join Zone A as the new standby:

```bash
# On Zone A server
# Update .env:
#   NODE_ROLE=standby
#   SCHEDULER_ENABLED=false
#   PRIMARY_DB_HOST=<ZONE_B_IP>

bash backend/scripts/setup-standby.sh
```

---

## Environment Variable Reference

All HA variables are optional. Defaults run as a standard single-node deployment.

| Variable | Default | Description |
|----------|---------|-------------|
| `NODE_ROLE` | `primary` | `primary` or `standby`. Controls write access and scheduler. |
| `SCHEDULER_ENABLED` | `true` | Set `false` on standby — disables alert evaluation, ML scoring, audit purge loops. |
| `SYNC_MODE` | `auto` | `auto` = standby daemon watches DB and auto-reloads. `manual` = admin-triggered push. |
| `PEER_BACKEND_URL` | _(empty)_ | Internal API URL of the other zone (e.g. `https://api-b.yourdomain.com`). |
| `INTERNAL_SYNC_TOKEN` | _(empty)_ | Shared secret for inter-node reload calls. Must match on both zones. Generate with `openssl rand -hex 32`. |
| `PRIMARY_DB_HOST` | _(empty)_ | Zone A's DB host IP. Only needed on Zone B during `setup-standby.sh`. |
| `REPLICATION_PASSWORD` | _(empty)_ | Password for the `replicator` PostgreSQL role. Only needed on Zone B. |
| `MAVIS_OVERRIDE_<KEY>` | _(empty)_ | Override any MAVIS key per zone (e.g. `MAVIS_OVERRIDE_LDAP_HOSTS`). |
| `SYNC_WATCHER_INTERVAL` | `10` | Seconds between config change polls (auto-sync watcher, Zone B only). |

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
  "sync_mode": "manual",
  "scheduler_enabled": true,
  "peer_backend_url": "https://api-b.yourdomain.com",
  "peer_available": true
}
```

**Manually push config to standby (manual sync mode):**

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/sync/push-config
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
