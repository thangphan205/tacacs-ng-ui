# Development Guide

## Prerequisites

- [Docker](https://docs.docker.com/engine/install/) + Docker Compose v2
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Node.js 20+](https://nodejs.org/) (for frontend-only work)

---

## Quick Start (Full Stack)

```bash
git clone https://github.com/thangphan205/tacacs-ng-ui
cd tacacs-ng-ui
cp .env.example .env    # edit .env — set SECRET_KEY, POSTGRES_PASSWORD, FIRST_SUPERUSER_PASSWORD
docker compose watch    # hot reload on file save
```

First startup takes ~1 minute while the DB initialises and migrations run.

### Local URLs

| Service | URL |
|---------|-----|
| Frontend (React) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Adminer (DB UI) | http://localhost:8080 |
| Traefik dashboard | http://localhost:8090 |
| MailCatcher (SMTP) | http://localhost:1080 |

Default login: credentials set in `.env` (`FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`).

---

## Hot Reload

`docker compose watch` uses `develop.watch` rules in `docker-compose.override.yml`:

- **Backend** (`./backend` → `/app`): any `.py` change reloads Uvicorn instantly. Changes to `pyproject.toml` trigger a container rebuild.
- **Frontend** (`./frontend`): Vite HMR reloads the browser instantly.
- **tac_plus-ng** and **cron** are managed by supervisord inside the backend container — they are not reloaded on Python file changes.

---

## Backend Development

### Setup (local, without Docker)

```bash
cd backend
uv sync                          # install dependencies into .venv
uv run pre-commit install        # install git hooks
```

### Run backend locally (outside Docker)

Requires a running PostgreSQL. Set `POSTGRES_SERVER=localhost` in `.env`, then:

```bash
cd backend
uv run bash scripts/prestart.sh  # run DB migrations + seed initial data
fastapi dev app/main.py          # hot-reload dev server on :8000
```

### Run tests

```bash
cd backend
uv run pytest                                         # all tests
uv run pytest tests/api/routes/test_hosts.py          # single file
uv run pytest -k "test_create_host"                   # single test by name
```

### Lint and format

```bash
cd backend
uv run bash scripts/lint.sh      # ruff check
uv run bash scripts/format.sh    # ruff format + fix
```

### Database migrations

Migrations use Alembic. The migration files live in `backend/app/alembic/versions/`.

**Generate a new migration** (run inside the backend container — Alembic writes to `/app/`):

```bash
docker compose exec backend alembic revision --autogenerate -m "add_column_foo"
```

**Copy the generated file to host** (only needed when using `docker compose up -d`; with `docker compose watch` the file is already synced):

```bash
docker compose cp backend:/app/app/alembic/versions/<rev>_add_column_foo.py \
  backend/app/alembic/versions/
```

**Apply migrations:**

```bash
docker compose exec backend alembic upgrade head
```

> **Note:** When adding `nullable=False` columns to existing tables, always include `server_default` in the column definition to avoid migration failures on existing rows.

### Architecture (backend)

Strict three-layer pattern — do not mix layers:

| Layer | Path | Rule |
|-------|------|------|
| Models / DTOs | `app/models.py` | Single file. All DB models + `*Public` DTOs. Base class `TimestampModel` adds UTC timestamps. |
| CRUD | `app/crud/` | Business logic only. Must **not** raise `HTTPException`. Returns model instances or `None`. |
| Routes | `app/api/routes/` | HTTP layer only. Translates CRUD results to HTTP responses. |

Shared deps: `SessionDep`, `CurrentUser`, `SuperUser`, `get_current_active_superuser` in `app/api/deps.py`.

---

## Frontend Development

### Run frontend locally (outside Docker)

```bash
cd frontend
npm install
npm run dev       # Vite dev server on :5173
```

Set `VITE_API_URL=http://localhost:8000` in `.env` or export it:

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```

### Lint and format

```bash
cd frontend
npm run lint      # Biome format + lint (writes in place)
```

### TypeScript type check + production build

```bash
cd frontend
npm run build
```

### Regenerate API client

After any backend route or model change, regenerate the TypeScript client:

```bash
bash scripts/generate-client.sh   # from repo root
```

Requires local backend venv (`uv sync` in `backend/`). Calls `python -c "import app.main; ..."` locally, then `npm run generate-client` in `frontend/`. The generated files live in `frontend/src/client/` — **never edit them manually**.

### Architecture (frontend)

| Path | Description |
|------|-------------|
| `frontend/src/client/` | Auto-generated OpenAPI client. Never edit manually. |
| `frontend/src/routes/` | TanStack Router file-based routing. `_layout.tsx` wraps all authenticated routes. |
| `frontend/src/components/` | Chakra UI v3 components. Prefer reusable over per-entity duplicates. |
| `frontend/src/main.tsx` | Configures OpenAPI base URL (`VITE_API_URL`) and JWT token from `localStorage`. |

Server state: TanStack React Query v5. Dark mode: next-themes.

---

## Pre-commit Hooks

```bash
cd backend
uv run pre-commit install        # install hooks (run once)
uv run pre-commit run --all-files  # run manually on all files
```

Hooks run: `ruff` (lint), `ruff-format` (format), `biome` (frontend lint/format), large-file check, YAML/TOML check.

---

## Docker Compose Files

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Base production config — all services |
| `docker-compose.override.yml` | Dev overrides: hot reload, exposed ports, MailCatcher, Playwright |
| `docker-compose.traefik.yml` | Standalone Traefik for production (separate stack) |

`docker compose` automatically merges `docker-compose.yml` + `docker-compose.override.yml`. For production, use `docker compose -f docker-compose.yml` to skip overrides.

### Useful commands

```bash
docker compose watch                     # start stack with hot reload (preferred for dev)
docker compose up -d                     # start detached (no hot reload)
docker compose logs -f backend           # tail backend logs
docker compose exec backend bash         # shell into backend container
docker compose exec db psql -U $POSTGRES_USER  # PostgreSQL shell
docker compose stop frontend             # stop one service (keep others running)
docker compose build backend             # rebuild one image
```

---

## Testing with a Real Domain (optional)

To test subdomain routing locally (mirrors production Traefik behaviour), set in `.env`:

```dotenv
DOMAIN=localhost.tiangolo.com
```

`localhost.tiangolo.com` and all its subdomains resolve to `127.0.0.1`. Traefik will then route:

- `http://dashboard.localhost.tiangolo.com` → frontend
- `http://api.localhost.tiangolo.com` → backend

Restart after changing `DOMAIN`:

```bash
docker compose watch
```

---

## Code Conventions

### Python

- Python 3.12+ union syntax: `str | None`, `list[str]` — never `Optional`, `List`
- Timezone-aware datetimes: `datetime.now(timezone.utc)` — never `datetime.utcnow()`
- `logging` module only — never `print()` in production code
- Return type annotations required on all functions

### TypeScript / React

- No `any` — use proper types or `unknown`
- Hooks only inside React components or custom hooks
- Indentation: 2 spaces, double quotes — Biome enforced
