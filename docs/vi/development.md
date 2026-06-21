# Hướng Dẫn Phát Triển

## Yêu Cầu

- [Docker](https://docs.docker.com/engine/install/) + Docker Compose v2
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (Python package manager)
- [Node.js 20+](https://nodejs.org/) (chỉ cần khi làm việc với frontend)

---

## Khởi Động Nhanh (Full Stack)

```bash
git clone https://github.com/thangphan205/tacacs-ng-ui
cd tacacs-ng-ui
cp .env.example .env    # chỉnh .env — đặt SECRET_KEY, POSTGRES_PASSWORD, FIRST_SUPERUSER_PASSWORD
docker compose watch    # hot reload khi lưu file
```

Lần khởi động đầu mất ~1 phút để DB khởi tạo và migrations chạy.

### URL Cục Bộ

| Service | URL |
|---------|-----|
| Frontend (React) | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Adminer (DB UI) | http://localhost:8080 |
| Traefik dashboard | http://localhost:8090 |
| MailCatcher (SMTP) | http://localhost:1080 |

Đăng nhập mặc định: thông tin đặt trong `.env` (`FIRST_SUPERUSER` / `FIRST_SUPERUSER_PASSWORD`).

---

## Hot Reload

`docker compose watch` dùng quy tắc `develop.watch` trong `docker-compose.override.yml`:

- **Backend** (`./backend` → `/app`): bất kỳ thay đổi `.py` nào reload Uvicorn ngay lập tức. Thay đổi `pyproject.toml` kích hoạt rebuild container.
- **Frontend** (`./frontend`): Vite HMR reload trình duyệt ngay lập tức.
- **tac_plus-ng** và **cron** được quản lý bởi supervisord bên trong backend container — không reload khi thay đổi file Python.

---

## Phát Triển Backend

### Cài Đặt (cục bộ, không dùng Docker)

```bash
cd backend
uv sync                          # cài dependencies vào .venv
uv run pre-commit install        # cài git hooks
```

### Chạy backend cục bộ (ngoài Docker)

Cần có PostgreSQL đang chạy. Đặt `POSTGRES_SERVER=localhost` trong `.env`, sau đó:

```bash
cd backend
uv run bash scripts/prestart.sh  # chạy DB migrations + seed dữ liệu ban đầu
fastapi dev app/main.py          # dev server hot-reload trên :8000
```

### Chạy tests

```bash
cd backend
uv run pytest                                         # tất cả tests
uv run pytest tests/api/routes/test_hosts.py          # một file cụ thể
uv run pytest -k "test_create_host"                   # một test theo tên
```

### Lint và format

```bash
cd backend
uv run bash scripts/lint.sh      # ruff check
uv run bash scripts/format.sh    # ruff format + fix
```

### Database migrations

Migrations dùng Alembic. File migration nằm trong `backend/app/alembic/versions/`.

**Tạo migration mới** (chạy trong backend container — Alembic ghi vào `/app/`):

```bash
docker compose exec backend alembic revision --autogenerate -m "add_column_foo"
```

**Copy file đã tạo về host** (chỉ cần khi dùng `docker compose up -d`; với `docker compose watch` file đã tự đồng bộ):

```bash
docker compose cp backend:/app/app/alembic/versions/<rev>_add_column_foo.py \
  backend/app/alembic/versions/
```

**Áp dụng migrations:**

```bash
docker compose exec backend alembic upgrade head
```

> **Lưu ý:** Khi thêm cột `nullable=False` vào bảng đã có dữ liệu, luôn thêm `server_default` vào định nghĩa cột để tránh lỗi migration.

### Kiến Trúc (backend)

Mô hình ba lớp nghiêm ngặt — không trộn lẫn các lớp:

| Lớp | Đường dẫn | Quy tắc |
|-----|-----------|---------|
| Models / DTOs | `app/models.py` | Một file duy nhất. Tất cả DB models + `*Public` DTOs. Base class `TimestampModel` thêm UTC timestamps. |
| CRUD | `app/crud/` | Chỉ business logic. **Không** raise `HTTPException`. Trả về model instances hoặc `None`. |
| Routes | `app/api/routes/` | Chỉ HTTP layer. Chuyển đổi kết quả CRUD thành HTTP responses. |

Dependencies dùng chung: `SessionDep`, `CurrentUser`, `SuperUser`, `get_current_active_superuser` trong `app/api/deps.py`.

---

## Phát Triển Frontend

### Chạy frontend cục bộ (ngoài Docker)

```bash
cd frontend
npm install
npm run dev       # Vite dev server trên :5173
```

Đặt `VITE_API_URL=http://localhost:8000` trong `.env` hoặc export:

```bash
VITE_API_URL=http://localhost:8000 npm run dev
```

### Lint và format

```bash
cd frontend
npm run lint      # Biome format + lint (ghi trực tiếp)
```

### TypeScript type check + production build

```bash
cd frontend
npm run build
```

### Tạo lại API client

Sau bất kỳ thay đổi route hoặc model backend nào, tạo lại TypeScript client:

```bash
bash scripts/generate-client.sh   # từ thư mục gốc repo
```

Cần có backend venv cục bộ (`uv sync` trong `backend/`). Gọi `python -c "import app.main; ..."` cục bộ, rồi chạy `npm run generate-client` trong `frontend/`. File được tạo nằm trong `frontend/src/client/` — **không bao giờ chỉnh sửa thủ công**.

### Kiến Trúc (frontend)

| Đường dẫn | Mô tả |
|-----------|-------|
| `frontend/src/client/` | OpenAPI client tự động tạo. Không chỉnh sửa thủ công. |
| `frontend/src/routes/` | TanStack Router file-based routing. `_layout.tsx` bọc tất cả routes cần xác thực. |
| `frontend/src/components/` | Chakra UI v3 components. Ưu tiên reusable hơn per-entity duplicates. |
| `frontend/src/main.tsx` | Cấu hình OpenAPI base URL (`VITE_API_URL`) và JWT token từ `localStorage`. |

Server state: TanStack React Query v5. Dark mode: next-themes.

---

## Pre-commit Hooks

```bash
cd backend
uv run pre-commit install        # cài hooks (chạy một lần)
uv run pre-commit run --all-files  # chạy thủ công trên tất cả file
```

Hooks chạy: `ruff` (lint), `ruff-format` (format), `biome` (frontend lint/format), kiểm tra file lớn, kiểm tra YAML/TOML.

---

## Docker Compose Files

| File | Mục đích |
|------|----------|
| `docker-compose.yml` | Cấu hình production gốc — tất cả services |
| `docker-compose.override.yml` | Dev overrides: hot reload, exposed ports, MailCatcher, Playwright |
| `docker-compose.traefik.yml` | Traefik độc lập cho production (stack riêng) |

`docker compose` tự động merge `docker-compose.yml` + `docker-compose.override.yml`. Cho production, dùng `docker compose -f docker-compose.yml` để bỏ qua overrides.

### Lệnh hữu ích

```bash
docker compose watch                     # khởi động stack với hot reload (khuyến nghị cho dev)
docker compose up -d                     # khởi động detached (không hot reload)
docker compose logs -f backend           # theo dõi backend logs
docker compose exec backend bash         # shell vào backend container
docker compose exec db psql -U $POSTGRES_USER  # PostgreSQL shell
docker compose stop frontend             # dừng một service (giữ các service khác)
docker compose build backend             # rebuild một image
```

---

## Kiểm Tra Với Tên Miền Thật (tùy chọn)

Để kiểm tra subdomain routing cục bộ (giống hành vi Traefik production), đặt trong `.env`:

```dotenv
DOMAIN=localhost.tiangolo.com
```

`localhost.tiangolo.com` và tất cả subdomain của nó phân giải về `127.0.0.1`. Traefik sẽ route:

- `http://dashboard.localhost.tiangolo.com` → frontend
- `http://api.localhost.tiangolo.com` → backend

Restart sau khi thay đổi `DOMAIN`:

```bash
docker compose watch
```

---

## Quy Ước Code

### Python

- Python 3.12+ union syntax: `str | None`, `list[str]` — không dùng `Optional`, `List`
- Datetime có timezone: `datetime.now(timezone.utc)` — không dùng `datetime.utcnow()`
- Chỉ dùng module `logging` — không dùng `print()` trong code production
- Bắt buộc return type annotation trên tất cả hàm

### TypeScript / React

- Không dùng `any` — dùng kiểu chính xác hoặc `unknown`
- Hooks chỉ bên trong React components hoặc custom hooks
- Thụt đầu dòng: 2 spaces, double quotes — Biome enforced
