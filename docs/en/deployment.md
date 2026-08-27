# Deployment Guide

> ### ⚠️ Upgrading from an earlier version?
>
> **0.6.0 changes every URL.** The dashboard, the API, Swagger and MCP now share
> one host; `dashboard.` and `api.` no longer route. Existing passkeys break if
> you change the host, and OAuth redirect URIs must be re-registered with your
> provider. Read [Upgrading to 0.6.0](#upgrading-to-060) **before** pulling.

## Prerequisites

- Remote server with [Docker Engine](https://docs.docker.com/engine/install/) (not Docker Desktop) and Docker Compose v2
- A domain with DNS A record pointing to the server IP — this one host serves the UI, the API, Swagger and MCP
- A second DNS record (or a wildcard) for the operator tools, `traefik.` and `adminer.`
- Ports `80` and `443` open on the server firewall — HTTP/HTTPS for the application
- Port `49/tcp` reachable from your network devices — this is TACACS+ itself, published by the `backend` container. It does not go through Traefik, and without it no switch or router can authenticate.

> **Note on the wildcard.** A `*.yourdomain.com` certificate matches a single
> label, so if you set `DOMAIN=tacacs.yourdomain.com` the tools would land on
> `adminer.tacacs.yourdomain.com` and fall outside it. Set `TOOLS_DOMAIN=yourdomain.com`
> to keep them at `adminer.yourdomain.com` instead.

---

## Step 1 — Set Up Traefik (once per server)

Traefik handles HTTPS termination and Let's Encrypt certificate renewal. It runs as a separate Docker Compose stack and is shared across all stacks on the server.

**On the remote server:**

```bash
mkdir -p /root/code/traefik-public
```

**Copy the Traefik compose file from your local machine:**

```bash
rsync -a docker-compose.traefik.yml root@your-server.example.com:/root/code/traefik-public/
```

**Create the shared Docker network:**

```bash
docker network create traefik-public
```

**Set environment variables and start Traefik:**

```bash
export DOMAIN=tacacs.yourdomain.com
export TOOLS_DOMAIN=yourdomain.com   # host for the traefik dashboard: traefik.yourdomain.com
export EMAIL=admin@yourdomain.com
export USERNAME=admin
export PASSWORD=changethis
export HASHED_PASSWORD=$(openssl passwd -apr1 "$PASSWORD")

cd /root/code/traefik-public
docker compose -f docker-compose.traefik.yml up -d
```

Verify Traefik is running: `https://traefik.yourdomain.com` (HTTP Basic Auth with username/password above).

---

## Step 2 — Configure `.env`

Clone the repo and configure environment variables:

```bash
git clone https://github.com/thangphan205/tacacs-ng-ui
cd tacacs-ng-ui
cp .env.example .env
```

**Minimum required changes in `.env`:**

```bash
# The single URL the application is served on.
DOMAIN=tacacs.yourdomain.com
# Must match what the browser shows, scheme included: it drives CORS, the
# WebAuthn/passkey origin, the OAuth redirect and the links in outgoing emails.
FRONTEND_HOST=https://tacacs.yourdomain.com
# Keeps adminer./traefik. on the base domain (see the note above).
TOOLS_DOMAIN=yourdomain.com

ENVIRONMENT=production
PROJECT_NAME="TACACS+ NG UI"

SECRET_KEY=<generate: openssl rand -hex 32>
FIRST_SUPERUSER=admin@yourdomain.com
FIRST_SUPERUSER_PASSWORD=<strong-password>

POSTGRES_USER=postgres
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=app

TZ=Asia/Ho_Chi_Minh   # or your timezone — controls TACACS+ log rotation and cron schedule
```

**Optional (email notifications):**

```bash
SMTP_HOST=smtp.youremailprovider.com
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
EMAILS_FROM_EMAIL=noreply@yourdomain.com
SMTP_PORT=587
SMTP_TLS=true
```

**Optional (error tracking):**

```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
```

### Generate secret keys

```bash
openssl rand -hex 32   # SECRET_KEY
openssl rand -hex 32   # POSTGRES_PASSWORD (use a different value)
```

---

## Step 3 — Deploy

```bash
docker compose -f docker-compose.yml up -d
```

This skips `docker-compose.override.yml` (dev overrides) and uses production settings only.

**First startup sequence:**

1. PostgreSQL starts and passes health check
2. `prestart` container runs DB migrations and seeds initial data
3. `backend` starts (FastAPI + tac_plus-ng + cron via supervisord)
4. `frontend` (Nginx) starts
5. Traefik picks up routing labels — HTTPS certificates issued automatically

Check logs to confirm everything is healthy:

```bash
docker compose -f docker-compose.yml logs -f backend
docker compose -f docker-compose.yml ps
```

### Production URLs

The application is served from **one URL**. The frontend's nginx proxies
`/api`, `/mcp`, `/docs` and `/redoc` through to the backend, so there is no
separate API host to remember or to configure in an MCP client.

Replace `yourdomain.com` with your domain:

| Service | URL |
|---------|-----|
| Dashboard | `https://tacacs.yourdomain.com` |
| API | `https://tacacs.yourdomain.com/api/v1` |
| Swagger | `https://tacacs.yourdomain.com/docs` |
| MCP endpoint | `https://tacacs.yourdomain.com/mcp/` |
| Adminer (DB UI) | `https://adminer.yourdomain.com` |
| Traefik dashboard | `https://traefik.yourdomain.com` |

The last two follow `TOOLS_DOMAIN` when it is set, and nest under `DOMAIN`
otherwise.

### Rate Limiting

Traefik rate-limits the application URL out of the box — no extra setup. The
middleware is defined on the `frontend` service in `docker-compose.yml`, so it
travels with the app: nothing to change in `docker-compose.traefik.yml`, and
nothing to re-copy to the server when you tune it.

Because everything is served from one URL, one budget covers the SPA, the API,
Swagger and MCP alike:

| Variable | Default | Meaning |
|----------|---------|---------|
| `RATE_LIMIT_AVERAGE` | `100` | Requests allowed per period, per source IP |
| `RATE_LIMIT_PERIOD` | `1s` | The window the average is measured over |
| `RATE_LIMIT_BURST` | `200` | How many may arrive in one spike |

Change them in `.env` and re-run `docker compose -f docker-compose.yml up -d`;
only the frontend container is recreated. Over-limit requests get `429 Too Many
Requests`.

**Counting is per source IP.** Everyone behind a single office NAT shares one
bucket, so a large team on one egress address needs a higher `AVERAGE` than the
numbers suggest.

**If legitimate users see `429`, raise `RATE_LIMIT_BURST` first.** The frontend
build code-splits into a few hundred asset chunks and Nginx sets no
`Cache-Control`, so a cold load or a hard reload arrives as one large short
spike. That is a burst problem, not a rate problem.

**What this does and does not stop.** It caps floods and scripted hammering
from any one IP, which keeps the backend, the database and the outgoing mail
path from being saturated. It does **not** meaningfully stop slow credential
stuffing against `/api/v1/login/access-token` or key guessing against `/mcp` —
at 100 requests per second an attacker still gets far more attempts than any
real user needs. If you want brute-force resistance, add a second Traefik
router with a higher `priority` matching `PathPrefix(/api/v1/login)` and a much
stricter limit (for example `average=5, period=1m`).

### Disabling Open Registration

Open registration is **on by default** (`USERS_OPEN_REGISTRATION=True`): anyone
who can reach the URL may create their own account at `/signup`. That is
convenient for a lab or an internal deployment where everyone who can reach the
host is already trusted.

To restrict account creation to administrators, set it in `.env` and recreate
the backend:

```bash
# .env
USERS_OPEN_REGISTRATION=False
```

```bash
docker compose -f docker-compose.yml up -d backend
```

A plain restart is not enough — the value is passed through the `environment:`
block in `docker-compose.yml`, so the container has to be recreated to pick it
up. `up -d` does that for you.

**What changes:** the login page drops its "Sign up" link, `/signup` redirects
to the login page if anyone reaches it directly, and `POST /api/v1/users/signup`
returns `400` with `"Open user registration is forbidden on this server"`.

The first two are presentation, read from the public
`GET /api/v1/auth-providers/status` endpoint. The endpoint is what actually
enforces the setting, so a stale page or a direct API call still gets refused.

**Creating users once it is off:** sign in as the superuser from
`FIRST_SUPERUSER` and use **Admin → Users Management** in the UI, or call
`POST /api/v1/users/` with a superuser token.

To turn it back on, set the value to `True` and run the same `up -d` command.

---

## Step 4 — Database Migrations (updates)

**There is no manual migration step.** The `prestart` container runs
`alembic upgrade head` on its own, and `backend` will not start until it has
exited successfully — `depends_on: prestart: condition: service_completed_successfully`
in `docker-compose.yml`. So a normal deploy applies any new revisions in the
right order:

```bash
git pull origin main

# Images are built locally: DOCKER_IMAGE_BACKEND/FRONTEND default to plain
# `backend`/`frontend` tags with no registry behind them. Only use
# `docker compose pull` if you have set those to a registry path.
docker compose -f docker-compose.yml build backend frontend

docker compose -f docker-compose.yml up -d
```

Rebuild `frontend` too, not just `backend` — the SPA is compiled into the
image, so a backend-only rebuild leaves the old assets being served.

> **Do not run `alembic upgrade head` by hand against a running container.** It
> executes inside the *old* image, which does not yet contain the new revision
> files, so it reports success while applying nothing.

See [Upgrading to a New Version](#upgrading-to-a-new-version) for the full
procedure, including the backup to take first.

---

## Continuous Deployment with GitHub Actions

The repo includes a production deploy workflow at `.github/workflows/deploy-production.yml`. It triggers on every published GitHub Release and deploys to a self-hosted runner with the `production` label.

### Install GitHub Actions self-hosted runner

**On the remote server:**

```bash
# Create dedicated user
sudo adduser github
sudo usermod -aG docker github

# Switch to github user
sudo su - github
cd ~

# Follow GitHub's runner install guide:
# Repository → Settings → Actions → Runners → New self-hosted runner
# Run the provided commands, then add label: production
```

**Install runner as a systemd service (so it survives reboots):**

```bash
exit   # back to root
sudo su
cd /home/github/actions-runner
./svc.sh install github
./svc.sh start
./svc.sh status
```

See [GitHub docs: configuring runner as a service](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/configuring-the-self-hosted-runner-application-as-a-service).

### Set GitHub repository secrets

Go to **Repository → Settings → Secrets and variables → Actions** and add:

| Secret | Description |
|--------|-------------|
| `DOMAIN_PRODUCTION` | The single host the app is served on (e.g. `tacacs.yourdomain.com`). The workflow derives `FRONTEND_HOST` from it |
| `STACK_NAME_PRODUCTION` | Docker Compose project name (e.g. `tacacs-ng-ui`) |
| `SECRET_KEY` | FastAPI JWT secret key |
| `FIRST_SUPERUSER` | Initial admin email |
| `FIRST_SUPERUSER_PASSWORD` | Initial admin password |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `SMTP_HOST` | SMTP server hostname (optional) |
| `SMTP_USER` | SMTP username (optional) |
| `SMTP_PASSWORD` | SMTP password (optional) |
| `EMAILS_FROM_EMAIL` | Sender email address (optional) |
| `SENTRY_DSN` | Sentry DSN (optional) |

**Deployment trigger:** publish a GitHub Release → workflow builds and deploys automatically.

---

## Environment Variables Reference

All variables with their defaults (from `.env.example`):

| Variable | Default | Description |
|----------|---------|-------------|
| `DOMAIN` | `localhost` | The single host serving the UI, API, Swagger and MCP |
| `TOOLS_DOMAIN` | *(unset)* | Base domain for `adminer.` and `traefik.`; falls back to `DOMAIN` |
| `FRONTEND_HOST` | `http://localhost:5173` | Full URL of the app — drives CORS, WebAuthn origin, OAuth redirect, email links |
| `VITE_API_URL` | `""` | Leave empty so the bundle calls its own origin; set only to target a backend elsewhere |
| `RATE_LIMIT_AVERAGE` | `100` | Requests per `RATE_LIMIT_PERIOD` per source IP, at the Traefik edge |
| `RATE_LIMIT_PERIOD` | `1s` | Window the average is measured over |
| `RATE_LIMIT_BURST` | `200` | Bucket depth for short spikes (cold page loads) |
| `ENVIRONMENT` | `local` | `local`, `staging`, or `production` |
| `PROJECT_NAME` | `TACACS+ NG UI` | Display name in UI and emails |
| `STACK_NAME` | `tacacs-ng-ui` | Docker Compose project name |
| `TZ` | `Asia/Ho_Chi_Minh` | Timezone for cron jobs and log rotation |
| `SECRET_KEY` | *(required)* | JWT signing key — generate with `openssl rand -hex 32` |
| `FIRST_SUPERUSER` | *(required)* | Initial admin email |
| `FIRST_SUPERUSER_PASSWORD` | *(required)* | Initial admin password |
| `BACKEND_CORS_ORIGINS` | `""` | Extra allowed CORS origins; rarely needed now the UI is same-origin |
| `USERS_OPEN_REGISTRATION` | `True` | Anyone reaching the URL may create their own account. Set to `False` to restrict account creation to administrators — see [Disabling Open Registration](#disabling-open-registration) |
| `POSTGRES_SERVER` | `localhost` | PostgreSQL hostname (leave as `db` for Docker Compose) |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `postgres` | PostgreSQL user |
| `POSTGRES_PASSWORD` | *(required)* | PostgreSQL password |
| `POSTGRES_DB` | `app` | Database name |
| `SMTP_HOST` | *(optional)* | SMTP server for email notifications |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_TLS` | `true` | Enable STARTTLS |
| `SMTP_SSL` | `false` | Enable SSL (port 465) |
| `SMTP_USER` | *(optional)* | SMTP username |
| `SMTP_PASSWORD` | *(optional)* | SMTP password |
| `EMAILS_FROM_EMAIL` | *(optional)* | Sender address |
| `TACACS_LOG_DIRECTORY` | `/var/log/tacacs/` | Where tac_plus-ng writes auth/authz/acct logs |
| `SENTRY_DSN` | *(optional)* | Sentry error tracking DSN |
| `GOOGLE_CLIENT_ID` | *(optional)* | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | *(optional)* | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | *(optional)* | Google OAuth callback URL |
| `KEYCLOAK_SERVER_URL` | *(optional)* | Keycloak server URL |
| `KEYCLOAK_REALM` | *(optional)* | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | *(optional)* | Keycloak client ID |
| `KEYCLOAK_CLIENT_SECRET` | *(optional)* | Keycloak client secret |
| `KEYCLOAK_REDIRECT_URI` | *(optional)* | Keycloak callback URL |
| `SIEM_WEBHOOK_URL` | *(optional)* | Splunk HEC or Logstash HTTP input URL |
| `SIEM_WEBHOOK_TOKEN` | *(optional)* | Splunk HEC token or bearer token |
| `SIEM_FORWARD_TACACS_EVENTS` | `false` | Forward auth/authz/acct events to SIEM |
| `SIEM_SYSLOG_HOST` | *(optional)* | Syslog target host |
| `SIEM_SYSLOG_PORT` | `514` | Syslog port |
| `SIEM_SYSLOG_PROTOCOL` | `udp` | `udp` or `tcp` |
| `AUDIT_LOG_RETENTION_DAYS` | `90` | Delete audit logs older than N days (0 = keep forever) |
| `AUDIT_LOG_MAX_ROWS` | `0` | Keep only N most recent rows (0 = no limit) |

For **High Availability** variables (`NODE_ROLE`, `SCHEDULER_ENABLED`, `SYNC_MODE`, etc.) see [high-availability.md](high-availability.md).

---

## Upgrading to 0.6.0

0.6.0 collapses the four subdomains into one URL. Nothing in the database
changes — this is entirely DNS, `.env`, and one mandatory image rebuild. Take
the backup in [Step 1](#step-1--backup-always-do-this-first) below first.

### Decide which host becomes the single URL

This is the one decision that matters, because **`WEBAUTHN_RP_ID` is derived
from `FRONTEND_HOST`'s hostname**, and a passkey registered under one host
cannot be used under another.

| | Keeps existing passkeys | Notes |
|---|---|---|
| `DOMAIN=dashboard.example.com` | ✅ yes | Users see the URL they already had; the API and MCP move onto it |
| `DOMAIN=example.com` (or any new host) | ❌ no | Cleaner URL, but every enrolled passkey must be re-registered |

Password and OAuth logins are unaffected either way. If you have passkey users
and no strong preference, keep the existing dashboard host.

### 1. DNS

The single URL needs its own A record pointing at Traefik. Previously only
`dashboard.` and `api.` did — if you relied on a wildcard, confirm it actually
covers the host you chose. `api.<domain>` can be retired once no client uses it.

### 2. `.env`

```dotenv
# Was your base domain; now it IS the application's host.
DOMAIN=tacacs.example.com

# New in 0.6.0. Leave blank to nest adminer./traefik. under DOMAIN; set it to
# the base domain to keep them under an existing *.example.com wildcard.
TOOLS_DOMAIN=example.com

# Previously undocumented, and easy to have left at its localhost default —
# which silently broke CORS, passkeys, OAuth and the links in outgoing emails.
FRONTEND_HOST=https://tacacs.example.com

# MUST be empty. The bundle now calls its own origin.
VITE_API_URL=

# Move onto the single URL.
GOOGLE_REDIRECT_URI=https://tacacs.example.com/api/v1/oauth/google/callback
KEYCLOAK_REDIRECT_URI=https://tacacs.example.com/api/v1/oauth/keycloak/callback
```

`BACKEND_CORS_ORIGINS` can be trimmed: the UI is now same-origin with the API,
and same-origin requests are never preflighted.

### 3. Rebuild the frontend — not optional

`VITE_API_URL` is compiled into the bundle at build time. A restart alone leaves
the old API host baked in, and every request goes to a hostname that no longer
resolves.

```bash
git pull origin main
docker compose -f docker-compose.yml build backend frontend
docker compose -f docker-compose.yml up -d
```

### 4. Re-register the OAuth redirect URIs

Update the authorised redirect URI in the **Google Cloud Console** and in your
**Keycloak client** to match the values above. A stale redirect URI fails at the
provider, so the error appears on their consent screen, not in this application.

### 5. Re-point MCP clients

Change `https://api.<domain>/mcp/` to `https://<domain>/mcp/` in each client's
configuration. **Existing API keys stay valid** — only the URL changes. The
in-app guide under **User Settings → API Keys** always shows the correct URL for
the deployment you are looking at.

### 6. HA peers

Any peer URL naming `api.<domain>` must be updated — to the peer's single URL,
or to `http://<ip>:8000`, which reaches the backend directly and skips the proxy
hop. Check both `PEER_BACKEND_URL`/`PEER_NODES` in `.env` and the `HaPeerNode`
rows already in the database (`GET /api/v1/sync/peers`).

### 7. Verify

```bash
curl -sf https://tacacs.example.com/api/v1/utils/health-check/   # API through the proxy
curl -sI https://tacacs.example.com/docs                         # Swagger
curl -si -X POST https://tacacs.example.com/mcp/                 # 401 without a key
```

Then log in, and — if you use them — confirm a passkey and an OAuth login still
work before you consider the upgrade done.

### If it goes wrong

Nothing here touches the database, so a rollback is `git checkout <previous
tag>`, restore the old `.env`, and rebuild. No migration to reverse.

---

## Upgrading to a New Version

> **How migrations work:** The `prestart` container runs `alembic upgrade head` automatically before the backend starts. Do **not** run migrations manually — let Docker Compose handle the sequence.

### Step 1 — Backup (always do this first)

```bash
export $(grep -v '^#' .env | xargs)

# Database
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d_%H%M).sql

# TACACS+ config files
tar -czf tacacs_config_backup_$(date +%Y%m%d_%H%M).tar.gz backend/tacacs_config/
```

### Step 2 — Check release notes

Read [release-notes.md](release-notes.md) for the target version. Look for:
- **Breaking changes** — env vars renamed or removed
- **New required env vars** — add them to `.env` before restarting
- **Manual migration notes** — rare, but called out explicitly when needed

### Step 3 — Pull and rebuild

```bash
git pull origin main

docker compose -f docker-compose.yml build backend frontend
```

### Step 4 — Restart

```bash
docker compose -f docker-compose.yml up -d
```

Docker Compose restarts services in dependency order:
1. `db` — PostgreSQL (no change)
2. `prestart` — runs `alembic upgrade head` automatically
3. `backend` — starts only after `prestart` exits successfully
4. `frontend` — serves new static assets

TACACS+ authentication is interrupted for ~5–10 seconds during backend restart.

### Step 5 — Verify

```bash
# Confirm prestart ran the migrations and exited cleanly
docker compose logs prestart | tail -20

# Confirm backend started cleanly
docker compose logs --tail=20 backend

# Confirm which revision is applied
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER $POSTGRES_DB -c \
  "SELECT version_num FROM alembic_version;"

# Confirm the API is healthy. Port 8000 is deliberately not published in
# production (only 49/tcp for TACACS+ is), so ask the container itself.
# The endpoint returns the bare JSON value `true`.
docker compose exec backend \
  curl -sf http://localhost:8000/api/v1/utils/health-check/

# From outside, go through the public URL instead:
curl -sf https://tacacs.yourdomain.com/api/v1/utils/health-check/
```

### Rollback

If the new version has a critical issue:

```bash
# 1. Restore DB backup (replaces all data — ensure backup is current)
cat backup_<YYYYMMDD_HHMM>.sql | \
  docker compose exec -T db psql -U $POSTGRES_USER $POSTGRES_DB

# 2. Check out previous version
git checkout <previous-tag-or-commit>

# 3. Rebuild and restart
docker compose -f docker-compose.yml build backend frontend
docker compose -f docker-compose.yml up -d
```

> **For HA deployments:** See [high-availability.md — Upgrading](high-availability.md#upgrading-to-a-new-version) for the zero-downtime rolling upgrade procedure.

---

## Backup

**Database:**

```bash
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d).sql
```

**TACACS+ config files:**

```bash
tar -czf tacacs_config_backup_$(date +%Y%m%d).tar.gz backend/tacacs_config/
```

**Restore database:**

```bash
cat backup_20260101.sql | docker compose exec -T db psql -U $POSTGRES_USER $POSTGRES_DB
```
