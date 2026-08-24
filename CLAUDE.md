# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**tacacs-ng-ui** is a full-stack web application providing a graphical interface for managing [tac_plus-ng](https://github.com/MarcJHuber/event-driven-servers) TACACS+ server configurations. It generates and validates TACACS+ config files, manages users/groups/policies, displays AAA statistics, and provides alerting, anomaly detection, and SIEM integration.

## Commands

### Backend (run from `backend/`)

```bash
uv sync                          # install/sync Python dependencies
fastapi dev app/main.py          # local dev server with hot reload
uv run pytest                    # run all tests
uv run pytest tests/api/routes/test_hosts.py  # run a single test file
uv run pytest -k "test_name"     # run a single test by name
uv run bash scripts/lint.sh      # ruff lint
uv run bash scripts/format.sh    # ruff format + fix
uv run bash scripts/prestart.sh  # run DB migrations + seed initial data
```

### Frontend (run from `frontend/`)

```bash
npm run dev              # Vite dev server (port 5173)
npm run build            # TypeScript check + production build
npm run lint             # Biome format + lint (writes in place)
npm run generate-client  # regenerate TypeScript API client from OpenAPI schema
```

### Docker Compose (run from root)

```bash
docker compose watch     # full dev stack with hot reload — preferred for dev
docker compose up -d     # start all services detached (no hot reload)
docker compose logs -f backend  # tail backend logs
docker compose exec backend bash  # shell into backend container
```

**Hot reload:** `docker compose watch` uses `develop.watch` in `docker-compose.override.yml` to sync `./backend` → `/app` and `./frontend` on every save. No rebuild needed for Python or TypeScript changes. Rebuild only triggers on `pyproject.toml` changes.

### API Client Generation

After changing any backend route or model:

```bash
bash scripts/generate-client.sh  # from root — exports OpenAPI schema and regenerates frontend/src/client/
```

Requires local backend venv (`uv sync` in `backend/`). Calls `python -c "import app.main; ..."` locally, then runs `npm run generate-client` in `frontend/`.

### Database Migrations

```bash
# Generate (run inside backend container — alembic writes to /app/app/alembic/versions/)
docker compose exec backend alembic revision --autogenerate -m "description"

# Copy generated file from container to host (required — not bind-mounted in production mode)
docker compose cp backend:/app/app/alembic/versions/<rev>_<name>.py backend/app/alembic/versions/

# Apply
docker compose exec backend alembic upgrade head
```

When using `docker compose watch`, files synced to container are also on host — no `cp` step needed. The `cp` step is only needed when running `docker compose up -d` (production-style, no sync).

When running migrations with `nullable=False` columns, always add `server_default` to avoid failures on existing rows.

### Pre-commit

```bash
uv run pre-commit install        # install hooks
uv run pre-commit run --all-files
```

## Architecture

### Backend (`backend/app/`)

Follows a strict three-layer pattern:

- **`models.py`** — All SQLModel schemas in one file. Every entity has at least a DB model and a `*Public` DTO. Base class `TimestampModel` adds UTC `created_at`/`updated_at`.
- **`crud/`** — Business logic only. Must **not** raise `HTTPException`. Returns model instances or `None`.
- **`api/routes/`** — HTTP layer only. Translates CRUD results to HTTP responses/status codes. Uses shared deps from `api/deps.py`: `SessionDep`, `CurrentUser`, `get_current_active_superuser`.

Auth is JWT (HS256, 8-day expiry) via `core/security.py`. Settings (env vars) live in `core/config.py` as a Pydantic `Settings` class.

### Frontend (`frontend/src/`)

- **`client/`** — Auto-generated from backend OpenAPI spec. **Never edit manually.** Regenerate with `bash scripts/generate-client.sh`.
- **`routes/`** — TanStack Router file-based routing. `_layout.tsx` wraps all authenticated routes. Route tree is auto-generated into `routeTree.gen.ts`.
- **`components/`** — Chakra UI v3 components. Prefer generic/reusable components over per-entity duplicates.
- **`main.tsx`** — Configures OpenAPI client base URL (`VITE_API_URL` env var) and JWT token from `localStorage.access_token`. Auto-logouts on 401/403.

Server state: TanStack React Query v5. Dark mode: next-themes.

### Infrastructure

Docker Compose services: `db` (PostgreSQL 18), `backend` (FastAPI + supervisord + tac_plus-ng + cron), `frontend` (Vite/Nginx), `traefik` (reverse proxy), `adminer` (DB UI), `mailcatcher` (SMTP testing).

Local dev URLs:
- Frontend: http://localhost:5173
- Backend / Swagger: http://localhost:8000/docs
- Adminer: http://localhost:8080
- Traefik: http://localhost:8090
- MailCatcher: http://localhost:1080

### TACACS+ Config Generation

Core domain logic in `backend/app/crud/tacacs_configs.py`. Reads/writes config files to `/app/tacacs_config/` (Docker volume), validates syntax using `tac_plus-ng` binary, generates MAVIS LDAP config blocks from template strings.

### Background Tasks (`backend/app/main.py`)

Three asyncio loops run in FastAPI lifespan:

| Task | Interval | Description |
|---|---|---|
| `_alert_evaluation_loop()` | 5 min | Evaluates enabled alert rules; dispatches notifications |
| `_ml_scoring_loop()` | 24 h | IsolationForest anomaly scoring on 30-day auth stats |
| `_audit_purge_loop()` | 24 h | Purges old audit log entries per retention settings |

### Alert Rules & Events (`backend/app/crud/alert_evaluator.py`)

Rules evaluate live TACACS logs (auth/authz log files) and AuditLog table. Fields: `log_type` (auth/authz/config/all), `condition_field`, `condition_operator` (gt/lt/eq/new_value/any_change/created/updated/deleted/activated), `threshold`, `time_window_minutes`, `cooldown_minutes`, `severity`. Triggered alerts dispatch to all enabled `NotificationChannel` rows and write an `AlertEvent` record.

### Notification Channels (`backend/app/crud/notification_dispatcher.py`)

Supported: Telegram, Slack (Block Kit), Discord, Teams, Webhook, Google Chat, Email.

### Anomaly Detection (`backend/app/crud/ml_anomaly_scorer.py`)

IsolationForest (`contamination=0.05`) trained on 30-day rolling per-username features: avg_daily_fails, stddev_fails, unique_ip_count, deny_ratio. Scores map to risk levels: normal / low / medium / high / critical. Results stored in `AnomalyDetectionResult`.

### AAA Log Statistics & Cron Jobs

Three cron scripts parse yesterday's TACACS logs and aggregate stats into DB:

| Script | Table | Schedule |
|---|---|---|
| `scripts/tacacs_logs_authentication.py` | `AuthenticationStatistics` | 1:00 AM local |
| `scripts/tacacs_logs_authorization.py` | `AuthorizationStatistics` | 1:05 AM local |
| `scripts/tacacs_logs_accounting.py` | `AccountingStatistics` | 1:10 AM local |

Cron is run via `scripts/cron_runner.sh` which sources `/etc/cron_env.sh` (full container environment). Schedule defined in `backend/tacacs-cron-jobs`.

**Timezone:** `scripts/_log_stats_base.py` reads timezone from `TacacsNgSetting.timezone` (DB-stored, editable in UI under TACACS NG Settings). Falls back to `TZ` env var, then UTC. Set `TZ=Asia/Ho_Chi_Minh` in `.env` for initial seed. This controls which local "yesterday" is targeted when scanning log files.

Pass a date argument to run for a specific date: `python scripts/tacacs_logs_authentication.py 2026-05-13`

### SIEM Forwarding (`backend/app/crud/tacacs_siem.py`)

Forwards parsed events to external SIEM via HTTP webhook (Splunk HEC / Logstash) and/or syslog. Controlled by env vars: `SIEM_WEBHOOK_URL`, `SIEM_WEBHOOK_TOKEN`, `SIEM_FORWARD_TACACS_EVENTS`, `SIEM_SYSLOG_HOST`.

### Audit Logging (`backend/app/crud/audit_logs.py`)

Records CREATE/UPDATE/DELETE/ACTIVATE actions on entities with user_id, email, IP, user-agent, old/new values. Auto-purges via `AUDIT_LOG_RETENTION_DAYS` (default 90) and `AUDIT_LOG_MAX_ROWS`. Routes call `audit_logs_crud.log_entity_action()` after mutations.

### MCP Server (`backend/app/mcp_server/`)

Read-only Model Context Protocol endpoint letting an LLM client inspect TACACS+ entities, render config previews, and syntax-check config text. On by default (`MCP_ENABLED=true`); set to `false` to disable. See `docs/en/mcp-server.md`.

Mounted at `settings.MCP_PATH` (default `/mcp`) directly on `app` in `main.py` — **never** under `api_router`, since a `Mount` must stay invisible to `custom_generate_unique_id` and OpenAPI generation. Canonical URL has a trailing slash.

| File | Role |
|---|---|
| `server.py` | `build_mcp()` factory, `MCPMountApp` ASGI shim, `mcp_lifespan()` |
| `auth.py` | `ApiKeyAuthMiddleware` (401 before protocol handling), `principal_from(ctx)`, scope guards |
| `tools.py` | the 12 tool registrations |
| `service.py` | DB work — plain sync functions taking a `Session` |
| `redact.py` | two-pass secret masking |
| `resources.py` | tac_plus-ng syntax reference, entity schema, active config, authoring prompt |

Constraints that are load-bearing:

- **`stateless_http=True` is mandatory** — supervisord runs `uvicorn --workers 4`, four processes with no shared memory, so in-process session state would miss on most requests.
- **Tools must be `async def` + `run_in_threadpool`** — FastMCP calls sync tool functions inline on the event loop.
- **`transport_security` must be passed explicitly** — FastMCP auto-enables DNS-rebinding protection when `host` is loopback (its default), which rejects the `Host: api.<domain>` header behind Traefik.
- **`session_manager.run()` is once-per-instance** — hence a fresh `FastMCP` per lifespan and the `MCPMountApp` shim. This is also why `tests/conftest.py`'s `client` fixture is session-scoped.

### API Keys (`backend/app/crud/api_keys.py`)

Machine credentials for MCP. Hashed with HMAC-SHA256 keyed on `SECRET_KEY` (**not** a password hash — argon2 and bcrypt both embed a random salt, which makes indexed lookup impossible, and their deliberate 50-250ms of blocking CPU would land on every MCP tool call). Superuser-gated CRUD at `/api/v1/api_keys`, soft revoke, audit-logged. Plaintext is returned exactly once at creation. Scopes: `mcp:read`, `mcp:generate`, `mcp:validate`, `mcp:secrets`.

Managed in the UI under **User Settings → API Keys** (`frontend/src/components/UserSettings/{ApiKeys,AddApiKey,RevokeApiKey,McpGuideModal,McpClientGuide}.tsx`), a tab added to `settings.tsx` only when `currentUser.is_superuser`. The create form uses `noValidate` so react-hook-form owns validation — Chakra's `Field required` sets a native `required` that would otherwise block submit before RHF runs. The scope checkboxes deliberately sit outside a `Field`, whose context would point every nested input's `aria-labelledby` at the Field label.

### Password Hashing

Two independent schemes — do not confuse them:

| | Library | Format | Where |
|---|---|---|---|
| **Login passwords** | `pwdlib` — `PasswordHash((Argon2Hasher(), BcryptHasher()))` | `$argon2id$` | `core/security.py` |
| **TACACS+ device users** | `passlib` — `sha512_crypt` | `$6$rounds=...$` | `crud/tacacs_users.py` |

`verify_password()` returns **`tuple[bool, str | None]`**, not a bool — the second item is a rehash to persist. `crud.users.authenticate()` writes it back, upgrading pre-migration bcrypt hashes to argon2 on next login (skipped on `NODE_ROLE=standby`).

passlib survives only for the TACACS scheme because tac_plus-ng parses `$6$rounds=...$` directly. **Never add `"bcrypt"` to a passlib `CryptContext` here**: its bcrypt backend probes for an old OpenBSD bug by hashing a 255-byte secret, which bcrypt ≥ 5.0 rejects with `ValueError`, breaking every hash and verify. `tests/core/test_security.py::test_passlib_bcrypt_backend_is_never_loaded` guards this.

### Authentication Providers (`backend/app/api/routes/oauth.py`)

- **Google OAuth2** — `google_id` column on User; HMAC-state validation
- **Keycloak OIDC** — `keycloak_id` column on User; HMAC-state validation
- **WebAuthn / Passkeys** — `WebAuthnCredential` + `WebAuthnChallenge` tables; `passkeys.py` CRUD

### High Availability (`backend/app/api/routes/sync.py`)

Multi-node active-passive HA via PostgreSQL streaming replication + config fan-out. See `docs/en/high-availability.md` for full setup guide.

**Env-only settings** (require restart):
- `NODE_ROLE` — `primary` or `standby`; controls DB write access and `require_primary_node()` dep
- `INTERNAL_SYNC_TOKEN` — shared secret for inter-node API calls

**All other HA settings** are DB-driven (`HaConfig` table, id=1) and editable via the HA UI without restart: `node_name`, `sync_mode`, `scheduler_enabled`, `stats_interval_minutes`.

**Peer management:** `HaPeerNode` table (CRUD via `GET/POST/PATCH/DELETE /api/v1/sync/peers`). On first primary startup, `PEER_BACKEND_URL`/`PEER_NODES` env vars are seeded into `HaPeerNode` automatically. Config sync fans out to all enabled peers.

**Key files:**
- `backend/app/api/routes/sync.py` — all HA API routes
- `backend/app/crud/tacacs_configs.py` — `_notify_peer_reload()` (auto-sync fan-out)
- `backend/scripts/config_sync_watcher.py` — standby auto-sync watcher (polls DB every 10s)
- `backend/app/models.py` — `HaConfig`, `HaPeerNode`, `HaNodeState`, `HaState`

## Code Conventions

### Python

- Python 3.12+ union syntax: `str | None`, `list[str]` — never `Optional`, `List`
- Always timezone-aware datetimes: `datetime.now(timezone.utc)`, never `datetime.utcnow()`
- `logging` module only, never `print()` in production code
- Return type annotations required on all functions
- Error messages in `HTTPException` must match the actual entity (avoid copy-paste errors)

### TypeScript / React

- No `any` — use proper types or `unknown`
- Hooks only inside React components or custom hooks, never in plain functions
- Indentation: 2 spaces, double quotes, Biome enforced

### API Patterns

- Pagination: `skip`, `limit`, `sort_by`, `sort_order` query params
- UUIDs as primary keys throughout
- `operationId` format `{tag}-{name}` (controls generated client method names)
