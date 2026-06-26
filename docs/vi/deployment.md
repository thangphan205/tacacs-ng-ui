# Hướng Dẫn Triển Khai

## Yêu Cầu

- Server từ xa với [Docker Engine](https://docs.docker.com/engine/install/) (không phải Docker Desktop) và Docker Compose v2
- Tên miền với DNS A record trỏ đến IP server
- Wildcard subdomain đã cấu hình (ví dụ `*.yourdomain.com`) — dùng cho `dashboard.`, `api.`, `traefik.`, `adminer.`
- Cổng `80` và `443` mở trên firewall server

---

## Bước 1 — Cài Đặt Traefik (một lần cho mỗi server)

Traefik xử lý HTTPS termination và tự động gia hạn chứng chỉ Let's Encrypt. Nó chạy như một Docker Compose stack riêng biệt và dùng chung cho tất cả stack trên server.

**Trên server từ xa:**

```bash
mkdir -p /root/code/traefik-public
```

**Copy file Traefik compose từ máy local:**

```bash
rsync -a docker-compose.traefik.yml root@your-server.example.com:/root/code/traefik-public/
```

**Tạo Docker network dùng chung:**

```bash
docker network create traefik-public
```

**Đặt biến môi trường và khởi động Traefik:**

```bash
export DOMAIN=yourdomain.com
export EMAIL=admin@yourdomain.com
export USERNAME=admin
export PASSWORD=changethis
export HASHED_PASSWORD=$(openssl passwd -apr1 "$PASSWORD")

cd /root/code/traefik-public
docker compose -f docker-compose.traefik.yml up -d
```

Kiểm tra Traefik đang chạy: `https://traefik.yourdomain.com` (HTTP Basic Auth với username/password ở trên).

---

## Bước 2 — Cấu Hình `.env`

Clone repo và cấu hình biến môi trường:

```bash
git clone https://github.com/thangphan205/tacacs-ng-ui
cd tacacs-ng-ui
cp .env.example .env
```

**Các thay đổi tối thiểu cần thiết trong `.env`:**

```bash
DOMAIN=yourdomain.com
ENVIRONMENT=production
PROJECT_NAME="TACACS+ NG UI"

SECRET_KEY=<tạo bằng: openssl rand -hex 32>
FIRST_SUPERUSER=admin@yourdomain.com
FIRST_SUPERUSER_PASSWORD=<mật-khẩu-mạnh>

POSTGRES_USER=postgres
POSTGRES_PASSWORD=<mật-khẩu-mạnh>
POSTGRES_DB=app

TZ=Asia/Ho_Chi_Minh   # hoặc timezone của bạn — ảnh hưởng đến log rotation và lịch cron TACACS+
```

**Tùy chọn (thông báo email):**

```bash
SMTP_HOST=smtp.youremailprovider.com
SMTP_USER=your-smtp-user
SMTP_PASSWORD=your-smtp-password
EMAILS_FROM_EMAIL=noreply@yourdomain.com
SMTP_PORT=587
SMTP_TLS=true
```

**Tùy chọn (theo dõi lỗi):**

```bash
SENTRY_DSN=https://your-dsn@sentry.io/project-id
```

### Tạo secret key

```bash
openssl rand -hex 32   # SECRET_KEY
openssl rand -hex 32   # POSTGRES_PASSWORD (dùng giá trị khác)
```

---

## Bước 3 — Triển Khai

```bash
docker compose -f docker-compose.yml up -d
```

Lệnh này bỏ qua `docker-compose.override.yml` (cấu hình dev) và chỉ dùng cài đặt production.

**Trình tự khởi động lần đầu:**

1. PostgreSQL khởi động và vượt qua health check
2. Container `prestart` chạy DB migrations và seed dữ liệu ban đầu
3. `backend` khởi động (FastAPI + tac_plus-ng + cron qua supervisord)
4. `frontend` (Nginx) khởi động
5. Traefik nhận routing labels — chứng chỉ HTTPS được cấp tự động

Kiểm tra logs để xác nhận mọi thứ hoạt động ổn:

```bash
docker compose -f docker-compose.yml logs -f backend
docker compose -f docker-compose.yml ps
```

### URL Production

Thay `yourdomain.com` bằng tên miền của bạn:

| Service | URL |
|---------|-----|
| Dashboard | `https://dashboard.yourdomain.com` |
| API / Swagger | `https://api.yourdomain.com/docs` |
| Adminer (DB UI) | `https://adminer.yourdomain.com` |
| Traefik dashboard | `https://traefik.yourdomain.com` |

---

## Bước 4 — Database Migrations (cập nhật)

Khi triển khai phiên bản mới có thay đổi schema:

```bash
# Pull image mới
docker compose -f docker-compose.yml pull backend

# Áp dụng migrations
docker compose -f docker-compose.yml exec backend alembic upgrade head

# Restart
docker compose -f docker-compose.yml up -d
```

---

## Triển Khai Liên Tục Với GitHub Actions

Repo đã có workflow deploy production tại `.github/workflows/deploy-production.yml`. Workflow kích hoạt mỗi khi publish GitHub Release và deploy lên self-hosted runner gắn nhãn `production`.

### Cài đặt GitHub Actions self-hosted runner

**Trên server từ xa:**

```bash
# Tạo user riêng
sudo adduser github
sudo usermod -aG docker github

# Chuyển sang user github
sudo su - github
cd ~

# Làm theo hướng dẫn cài runner của GitHub:
# Repository → Settings → Actions → Runners → New self-hosted runner
# Chạy các lệnh được cung cấp, sau đó thêm label: production
```

**Cài runner như systemd service (tự khởi động sau reboot):**

```bash
exit   # quay lại root
sudo su
cd /home/github/actions-runner
./svc.sh install github
./svc.sh start
./svc.sh status
```

Xem [GitHub docs: cấu hình runner như service](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners/configuring-the-self-hosted-runner-application-as-a-service).

### Đặt GitHub repository secrets

Vào **Repository → Settings → Secrets and variables → Actions** và thêm:

| Secret | Mô tả |
|--------|-------|
| `DOMAIN_PRODUCTION` | Tên miền production (ví dụ `yourdomain.com`) |
| `STACK_NAME_PRODUCTION` | Tên Docker Compose project (ví dụ `tacacs-ng-ui`) |
| `SECRET_KEY` | FastAPI JWT secret key |
| `FIRST_SUPERUSER` | Email admin ban đầu |
| `FIRST_SUPERUSER_PASSWORD` | Mật khẩu admin ban đầu |
| `POSTGRES_PASSWORD` | Mật khẩu PostgreSQL |
| `SMTP_HOST` | Hostname SMTP server (tùy chọn) |
| `SMTP_USER` | SMTP username (tùy chọn) |
| `SMTP_PASSWORD` | SMTP password (tùy chọn) |
| `EMAILS_FROM_EMAIL` | Địa chỉ email gửi (tùy chọn) |
| `SENTRY_DSN` | Sentry DSN (tùy chọn) |

**Kích hoạt deploy:** publish GitHub Release → workflow tự động build và deploy.

---

## Tham Chiếu Biến Môi Trường

Tất cả biến với giá trị mặc định (từ `.env.example`):

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `DOMAIN` | `localhost` | Domain gốc cho tất cả service |
| `ENVIRONMENT` | `local` | `local`, `staging`, hoặc `production` |
| `PROJECT_NAME` | `TACACS+ NG UI` | Tên hiển thị trong UI và email |
| `STACK_NAME` | `tacacs-ng-ui` | Tên Docker Compose project |
| `TZ` | `Asia/Ho_Chi_Minh` | Timezone cho cron jobs và log rotation |
| `SECRET_KEY` | *(bắt buộc)* | JWT signing key — tạo bằng `openssl rand -hex 32` |
| `FIRST_SUPERUSER` | *(bắt buộc)* | Email admin ban đầu |
| `FIRST_SUPERUSER_PASSWORD` | *(bắt buộc)* | Mật khẩu admin ban đầu |
| `BACKEND_CORS_ORIGINS` | `""` | Danh sách CORS origins cho phép, phân cách bằng dấu phẩy |
| `USERS_OPEN_REGISTRATION` | `true` | Cho phép đăng ký công khai |
| `POSTGRES_SERVER` | `localhost` | Hostname PostgreSQL (để là `db` cho Docker Compose) |
| `POSTGRES_PORT` | `5432` | Cổng PostgreSQL |
| `POSTGRES_USER` | `postgres` | User PostgreSQL |
| `POSTGRES_PASSWORD` | *(bắt buộc)* | Mật khẩu PostgreSQL |
| `POSTGRES_DB` | `app` | Tên database |
| `SMTP_HOST` | *(tùy chọn)* | SMTP server cho thông báo email |
| `SMTP_PORT` | `587` | Cổng SMTP |
| `SMTP_TLS` | `true` | Bật STARTTLS |
| `SMTP_SSL` | `false` | Bật SSL (cổng 465) |
| `SMTP_USER` | *(tùy chọn)* | SMTP username |
| `SMTP_PASSWORD` | *(tùy chọn)* | SMTP password |
| `EMAILS_FROM_EMAIL` | *(tùy chọn)* | Địa chỉ gửi |
| `TACACS_LOG_DIRECTORY` | `/var/log/tacacs/` | Nơi tac_plus-ng ghi log auth/authz/acct |
| `SENTRY_DSN` | *(tùy chọn)* | Sentry error tracking DSN |
| `GOOGLE_CLIENT_ID` | *(tùy chọn)* | Google OAuth client ID |
| `GOOGLE_CLIENT_SECRET` | *(tùy chọn)* | Google OAuth client secret |
| `GOOGLE_REDIRECT_URI` | *(tùy chọn)* | Google OAuth callback URL |
| `KEYCLOAK_SERVER_URL` | *(tùy chọn)* | Keycloak server URL |
| `KEYCLOAK_REALM` | *(tùy chọn)* | Keycloak realm name |
| `KEYCLOAK_CLIENT_ID` | *(tùy chọn)* | Keycloak client ID |
| `KEYCLOAK_CLIENT_SECRET` | *(tùy chọn)* | Keycloak client secret |
| `KEYCLOAK_REDIRECT_URI` | *(tùy chọn)* | Keycloak callback URL |
| `SIEM_WEBHOOK_URL` | *(tùy chọn)* | URL Splunk HEC hoặc Logstash HTTP input |
| `SIEM_WEBHOOK_TOKEN` | *(tùy chọn)* | Splunk HEC token hoặc bearer token |
| `SIEM_FORWARD_TACACS_EVENTS` | `false` | Chuyển tiếp sự kiện auth/authz/acct đến SIEM |
| `SIEM_SYSLOG_HOST` | *(tùy chọn)* | Host syslog đích |
| `SIEM_SYSLOG_PORT` | `514` | Cổng syslog |
| `SIEM_SYSLOG_PROTOCOL` | `udp` | `udp` hoặc `tcp` |
| `AUDIT_LOG_RETENTION_DAYS` | `90` | Xóa audit log cũ hơn N ngày (0 = giữ mãi) |
| `AUDIT_LOG_MAX_ROWS` | `0` | Chỉ giữ N dòng gần nhất (0 = không giới hạn) |

Các biến **High Availability** (`NODE_ROLE`, `SCHEDULER_ENABLED`, `SYNC_MODE`, v.v.) xem tại [high-availability.md](high-availability.md).

---

## Nâng Cấp Lên Phiên Bản Mới

> **Cơ chế migration:** Container `prestart` tự động chạy `alembic upgrade head` trước khi backend khởi động. **Không** chạy migration thủ công — để Docker Compose xử lý thứ tự.

### Bước 1 — Backup (luôn làm trước)

```bash
export $(grep -v '^#' .env | xargs)

# Database
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d_%H%M).sql

# File cấu hình TACACS+
tar -czf tacacs_config_backup_$(date +%Y%m%d_%H%M).tar.gz backend/tacacs_config/
```

### Bước 2 — Kiểm tra release notes

Đọc [release-notes.md](release-notes.md) cho phiên bản mục tiêu. Chú ý:
- **Breaking changes** — biến env đổi tên hoặc bị xóa
- **Biến env mới bắt buộc** — thêm vào `.env` trước khi restart
- **Bước migration thủ công** — hiếm gặp, được ghi rõ khi cần

### Bước 3 — Pull và rebuild

```bash
git pull origin main

docker compose -f docker-compose.yml build backend frontend
```

### Bước 4 — Restart

```bash
docker compose -f docker-compose.yml up -d
```

Docker Compose restart theo thứ tự phụ thuộc:
1. `db` — PostgreSQL (không thay đổi)
2. `prestart` — tự động chạy `alembic upgrade head`
3. `backend` — chỉ khởi động sau khi `prestart` thành công
4. `frontend` — phục vụ static assets mới

TACACS+ bị gián đoạn ~5–10 giây trong lúc backend restart.

### Bước 5 — Kiểm tra

```bash
# Xác nhận backend khởi động sạch
docker compose logs --tail=20 backend

# Xác nhận migration đã áp dụng
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER $POSTGRES_DB -c \
  "SELECT version_num FROM alembic_version;"

# Xác nhận API healthy
curl -s http://localhost:8000/api/v1/utils/health-check/ | grep '"status"'
```

### Rollback

Nếu phiên bản mới có lỗi nghiêm trọng:

```bash
# 1. Khôi phục DB backup (thay toàn bộ dữ liệu — đảm bảo backup còn mới)
cat backup_<YYYYMMDD_HHMM>.sql | \
  docker compose exec -T db psql -U $POSTGRES_USER $POSTGRES_DB

# 2. Checkout phiên bản cũ
git checkout <tag-hoặc-commit-cũ>

# 3. Rebuild và restart
docker compose -f docker-compose.yml build backend frontend
docker compose -f docker-compose.yml up -d
```

> **Triển khai HA:** Xem [high-availability.md — Nâng Cấp](high-availability.md#nâng-cấp-lên-phiên-bản-mới) để biết quy trình rolling upgrade không gián đoạn.

---

## Backup

**Database:**

```bash
docker compose exec db pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%Y%m%d).sql
```

**File cấu hình TACACS+:**

```bash
tar -czf tacacs_config_backup_$(date +%Y%m%d).tar.gz backend/tacacs_config/
```

**Khôi phục database:**

```bash
cat backup_20260101.sql | docker compose exec -T db psql -U $POSTGRES_USER $POSTGRES_DB
```
