# Deployment Guide

## Prerequisites

- Remote server with [Docker Engine](https://docs.docker.com/engine/install/) (not Docker Desktop) and Docker Compose v2
- A domain with DNS A record pointing to the server IP
- Wildcard subdomain configured (e.g. `*.yourdomain.com`) — used for `dashboard.`, `api.`, `traefik.`, `adminer.`
- Ports `80` and `443` open on the server firewall

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
export DOMAIN=yourdomain.com
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
DOMAIN=yourdomain.com
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

Replace `yourdomain.com` with your domain:

| Service | URL |
|---------|-----|
| Dashboard | `https://dashboard.yourdomain.com` |
| API / Swagger | `https://api.yourdomain.com/docs` |
| Adminer (DB UI) | `https://adminer.yourdomain.com` |
| Traefik dashboard | `https://traefik.yourdomain.com` |

---

## Step 4 — Database Migrations (updates)

When deploying a new version that includes schema changes:

```bash
# Pull new image
docker compose -f docker-compose.yml pull backend

# Apply migrations
docker compose -f docker-compose.yml exec backend alembic upgrade head

# Restart
docker compose -f docker-compose.yml up -d
```

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
| `DOMAIN_PRODUCTION` | Your production domain (e.g. `yourdomain.com`) |
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
| `DOMAIN` | `localhost` | Base domain for all services |
| `ENVIRONMENT` | `local` | `local`, `staging`, or `production` |
| `PROJECT_NAME` | `TACACS+ NG UI` | Display name in UI and emails |
| `STACK_NAME` | `tacacs-ng-ui` | Docker Compose project name |
| `TZ` | `Asia/Ho_Chi_Minh` | Timezone for cron jobs and log rotation |
| `SECRET_KEY` | *(required)* | JWT signing key — generate with `openssl rand -hex 32` |
| `FIRST_SUPERUSER` | *(required)* | Initial admin email |
| `FIRST_SUPERUSER_PASSWORD` | *(required)* | Initial admin password |
| `BACKEND_CORS_ORIGINS` | `""` | Comma-separated list of allowed CORS origins |
| `USERS_OPEN_REGISTRATION` | `true` | Allow public signup |
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

## Updating

```bash
# Pull latest code
git pull

# Rebuild images
docker compose -f docker-compose.yml build

# Apply migrations (if any)
docker compose -f docker-compose.yml exec backend alembic upgrade head

# Restart with new images
docker compose -f docker-compose.yml up -d
```

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
