# Hướng Dẫn Triển Khai

> ### ⚠️ Đang nâng cấp từ phiên bản cũ hơn?
>
> **0.6.0 thay đổi toàn bộ URL.** Dashboard, API, Swagger và MCP giờ dùng chung
> một host; `dashboard.` và `api.` không còn route nữa. Passkey đã đăng ký sẽ hỏng
> nếu bạn đổi host, và redirect URI của OAuth phải được đăng ký lại với nhà cung
> cấp. Đọc [Nâng cấp lên 0.6.0](#nâng-cấp-lên-060) **trước khi** pull.

## Yêu Cầu

- Server từ xa với [Docker Engine](https://docs.docker.com/engine/install/) (không phải Docker Desktop) và Docker Compose v2
- Tên miền với DNS A record trỏ đến IP server — chính host này phục vụ UI, API, Swagger và MCP
- Một DNS record thứ hai (hoặc wildcard) cho các công cụ vận hành: `traefik.` và `adminer.`
- Cổng `80` và `443` mở trên firewall server — HTTP/HTTPS cho ứng dụng
- Cổng `49/tcp` cho các thiết bị mạng truy cập được — đây chính là TACACS+, do container `backend` publish. Nó không đi qua Traefik, và nếu không mở thì không switch hay router nào xác thực được.

> **Lưu ý về wildcard.** Chứng chỉ `*.yourdomain.com` chỉ khớp một nhãn, nên nếu
> đặt `DOMAIN=tacacs.yourdomain.com` thì các công cụ sẽ nằm ở
> `adminer.tacacs.yourdomain.com` và không được wildcard bao phủ. Đặt
> `TOOLS_DOMAIN=yourdomain.com` để giữ chúng ở `adminer.yourdomain.com`.

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
export DOMAIN=tacacs.yourdomain.com
export TOOLS_DOMAIN=yourdomain.com   # host cho traefik dashboard: traefik.yourdomain.com
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
# URL duy nhất mà ứng dụng được phục vụ.
DOMAIN=tacacs.yourdomain.com
# Phải khớp chính xác với URL trên trình duyệt, kể cả scheme: nó quyết định CORS,
# origin của WebAuthn/passkey, redirect OAuth và link trong email gửi đi.
FRONTEND_HOST=https://tacacs.yourdomain.com
# Giữ adminer./traefik. ở tên miền gốc (xem lưu ý ở trên).
TOOLS_DOMAIN=yourdomain.com

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

Ứng dụng được phục vụ từ **một URL duy nhất**. Nginx của frontend proxy
`/api`, `/mcp`, `/docs` và `/redoc` sang backend, nên không còn host API riêng
cần nhớ hay cấu hình trong MCP client.

Thay `yourdomain.com` bằng tên miền của bạn:

| Service | URL |
|---------|-----|
| Dashboard | `https://tacacs.yourdomain.com` |
| API | `https://tacacs.yourdomain.com/api/v1` |
| Swagger | `https://tacacs.yourdomain.com/docs` |
| MCP endpoint | `https://tacacs.yourdomain.com/mcp/` |
| Adminer (DB UI) | `https://adminer.yourdomain.com` |
| Traefik dashboard | `https://traefik.yourdomain.com` |

Hai mục cuối theo `TOOLS_DOMAIN` khi được đặt, ngược lại nằm dưới `DOMAIN`.

### Giới Hạn Tốc Độ (Rate Limiting)

Traefik giới hạn tốc độ cho URL ứng dụng ngay từ đầu — không cần cài đặt thêm.
Middleware được khai báo trên service `frontend` trong `docker-compose.yml`, nên
nó đi kèm ứng dụng: không phải sửa `docker-compose.traefik.yml`, cũng không phải
copy lại lên server mỗi khi bạn chỉnh thông số.

Vì mọi thứ được phục vụ từ một URL duy nhất, một hạn mức duy nhất áp dụng cho cả
SPA, API, Swagger và MCP:

| Biến | Mặc định | Ý nghĩa |
|------|----------|---------|
| `RATE_LIMIT_AVERAGE` | `100` | Số request cho phép mỗi period, tính theo từng IP nguồn |
| `RATE_LIMIT_PERIOD` | `1s` | Khoảng thời gian dùng để tính mức trung bình |
| `RATE_LIMIT_BURST` | `200` | Số request được phép dồn trong một đợt |

Đổi giá trị trong `.env` rồi chạy lại `docker compose -f docker-compose.yml up -d`;
chỉ container frontend được tạo lại. Request vượt hạn mức nhận `429 Too Many
Requests`.

**Đếm theo từng IP nguồn.** Mọi người sau cùng một NAT văn phòng dùng chung một
hạn mức, nên một đội đông đi ra bằng một địa chỉ duy nhất cần `AVERAGE` cao hơn
con số nhìn qua tưởng là đủ.

**Nếu người dùng thật gặp `429`, hãy tăng `RATE_LIMIT_BURST` trước.** Bản build
frontend chia thành vài trăm chunk và Nginx không đặt `Cache-Control`, nên tải
nguội hoặc hard reload sẽ đến như một đợt dồn ngắn nhưng lớn. Đó là vấn đề burst,
không phải vấn đề rate.

**Cái này chặn được gì và không chặn được gì.** Nó chặn flood và các script quét
dồn dập từ một IP, giữ cho backend, database và đường gửi mail không bị bão hòa.
Nó **không** thực sự chặn được credential stuffing chậm rãi vào
`/api/v1/login/access-token` hay dò key vào `/mcp` — ở mức 100 request mỗi giây,
kẻ tấn công vẫn có nhiều lượt thử hơn bất kỳ người dùng thật nào cần. Nếu muốn
chống brute-force, thêm một router Traefik thứ hai với `priority` cao hơn khớp
`PathPrefix(/api/v1/login)` và đặt hạn mức chặt hơn nhiều (ví dụ
`average=5, period=1m`).

### Tắt Đăng Ký Mở

Đăng ký mở **được bật sẵn** (`USERS_OPEN_REGISTRATION=True`): bất kỳ ai vào được
URL đều có thể tự tạo tài khoản tại `/signup`. Điều này tiện cho môi trường lab
hoặc nội bộ, nơi ai vào được host thì đã là người tin cậy.

Để chỉ cho admin tạo tài khoản, đặt giá trị trong `.env` rồi tạo lại container
backend:

```bash
# .env
USERS_OPEN_REGISTRATION=False
```

```bash
docker compose -f docker-compose.yml up -d backend
```

Restart thường là không đủ — giá trị được truyền qua khối `environment:` trong
`docker-compose.yml`, nên container phải được tạo lại mới nhận. Lệnh `up -d` lo
việc đó.

**Thay đổi gì:** `POST /api/v1/users/signup` bắt đầu trả về `400` kèm
`"Open user registration is forbidden on this server"`.

> **Trang đăng nhập vẫn hiện link "Sign up".** Frontend không đọc cấu hình này,
> nên form vẫn vào được và chỉ báo lỗi sau khi người dùng điền và bấm gửi.
> Không có gì được tạo ra, nhưng nên biết trước để khỏi bị báo nhầm là bug.

**Tạo user sau khi đã tắt:** đăng nhập bằng superuser từ `FIRST_SUPERUSER` rồi
dùng **Admin → Users Management** trên UI, hoặc gọi `POST /api/v1/users/` với
token superuser.

Muốn bật lại thì đặt giá trị `True` và chạy đúng lệnh `up -d` ở trên.

---

## Bước 4 — Database Migrations (cập nhật)

**Không có bước migration thủ công.** Container `prestart` tự chạy
`alembic upgrade head`, và `backend` chỉ khởi động sau khi `prestart` kết thúc
thành công — `depends_on: prestart: condition: service_completed_successfully`
trong `docker-compose.yml`. Vì vậy một lần deploy bình thường đã áp dụng đúng
thứ tự mọi revision mới:

```bash
git pull origin main

# Image được build tại chỗ: DOCKER_IMAGE_BACKEND/FRONTEND mặc định chỉ là tag
# `backend`/`frontend`, không có registry phía sau. Chỉ dùng
# `docker compose pull` nếu bạn đã trỏ hai biến đó tới một registry.
docker compose -f docker-compose.yml build backend frontend

docker compose -f docker-compose.yml up -d
```

Hãy build lại cả `frontend`, không chỉ `backend` — SPA được biên dịch vào
image, nên nếu chỉ build backend thì assets cũ vẫn được phục vụ.

> **Đừng chạy `alembic upgrade head` thủ công trên container đang chạy.** Lệnh
> đó chạy bên trong image *cũ*, nơi chưa có file revision mới, nên nó báo thành
> công mà thực tế không áp dụng gì cả.

Xem [Nâng Cấp Lên Phiên Bản Mới](#nâng-cấp-lên-phiên-bản-mới) để biết quy trình
đầy đủ, gồm cả bước backup phải làm trước.

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
| `DOMAIN_PRODUCTION` | Host duy nhất phục vụ ứng dụng (ví dụ `tacacs.yourdomain.com`). Workflow suy ra `FRONTEND_HOST` từ nó |
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
| `DOMAIN` | `localhost` | Host duy nhất phục vụ UI, API, Swagger và MCP |
| `TOOLS_DOMAIN` | *(trống)* | Domain gốc cho `adminer.` và `traefik.`; mặc định lấy theo `DOMAIN` |
| `FRONTEND_HOST` | `http://localhost:5173` | URL đầy đủ của ứng dụng — quyết định CORS, origin WebAuthn, redirect OAuth, link email |
| `VITE_API_URL` | `""` | Để trống để bundle gọi chính origin của nó; chỉ đặt khi backend nằm ở origin khác |
| `RATE_LIMIT_AVERAGE` | `100` | Số request mỗi `RATE_LIMIT_PERIOD` cho mỗi IP nguồn, tại lớp Traefik |
| `RATE_LIMIT_PERIOD` | `1s` | Khoảng thời gian dùng để tính mức trung bình |
| `RATE_LIMIT_BURST` | `200` | Sức chứa cho các đợt dồn ngắn (tải trang lần đầu) |
| `ENVIRONMENT` | `local` | `local`, `staging`, hoặc `production` |
| `PROJECT_NAME` | `TACACS+ NG UI` | Tên hiển thị trong UI và email |
| `STACK_NAME` | `tacacs-ng-ui` | Tên Docker Compose project |
| `TZ` | `Asia/Ho_Chi_Minh` | Timezone cho cron jobs và log rotation |
| `SECRET_KEY` | *(bắt buộc)* | JWT signing key — tạo bằng `openssl rand -hex 32` |
| `FIRST_SUPERUSER` | *(bắt buộc)* | Email admin ban đầu |
| `FIRST_SUPERUSER_PASSWORD` | *(bắt buộc)* | Mật khẩu admin ban đầu |
| `BACKEND_CORS_ORIGINS` | `""` | Origin CORS bổ sung; hiếm khi cần vì UI đã cùng origin với API |
| `USERS_OPEN_REGISTRATION` | `True` | Bất kỳ ai vào được URL đều tự tạo tài khoản được. Đặt `False` để chỉ admin mới tạo được tài khoản — xem [Tắt Đăng Ký Mở](#tắt-đăng-ký-mở) |
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

## Nâng cấp lên 0.6.0

0.6.0 gộp bốn subdomain thành một URL duy nhất. Database không thay đổi gì —
toàn bộ công việc nằm ở DNS, `.env`, và một lần build lại image bắt buộc. Hãy
backup theo [Bước 1](#bước-1--backup-luôn-làm-trước) bên dưới trước.

### Chọn host nào làm URL duy nhất

Đây là quyết định quan trọng nhất, vì **`WEBAUTHN_RP_ID` được suy ra từ hostname
của `FRONTEND_HOST`**, và passkey đăng ký dưới host này không dùng được ở host khác.

| | Giữ được passkey cũ | Ghi chú |
|---|---|---|
| `DOMAIN=dashboard.example.com` | ✅ có | Người dùng vẫn thấy URL quen thuộc; API và MCP chuyển về đó |
| `DOMAIN=example.com` (hoặc host mới) | ❌ không | URL gọn hơn, nhưng mọi passkey đã đăng ký phải đăng ký lại |

Đăng nhập bằng mật khẩu và OAuth không bị ảnh hưởng trong cả hai trường hợp. Nếu
bạn có người dùng passkey và không có lý do đặc biệt, hãy giữ host dashboard hiện tại.

### 1. DNS

URL duy nhất cần A record riêng trỏ về Traefik. Trước đây chỉ `dashboard.` và
`api.` có — nếu bạn dựa vào wildcard, hãy kiểm tra nó thực sự bao phủ host bạn
chọn. `api.<domain>` có thể gỡ bỏ khi không còn client nào dùng.

### 2. `.env`

```dotenv
# Trước là tên miền gốc; giờ chính là host của ứng dụng.
DOMAIN=tacacs.example.com

# Mới trong 0.6.0. Để trống thì adminer./traefik. nằm dưới DOMAIN; đặt bằng tên
# miền gốc để giữ chúng trong wildcard *.example.com sẵn có.
TOOLS_DOMAIN=example.com

# Trước đây không được nhắc tới trong tài liệu, nên rất dễ còn nguyên giá trị
# localhost mặc định — làm hỏng CORS, passkey, OAuth và link trong email gửi đi.
FRONTEND_HOST=https://tacacs.example.com

# BẮT BUỘC để trống. Bundle giờ gọi chính origin của nó.
VITE_API_URL=

# Chuyển về URL duy nhất.
GOOGLE_REDIRECT_URI=https://tacacs.example.com/api/v1/oauth/google/callback
KEYCLOAK_REDIRECT_URI=https://tacacs.example.com/api/v1/oauth/keycloak/callback
```

`BACKEND_CORS_ORIGINS` có thể rút gọn: UI giờ cùng origin với API, và request
cùng origin không bao giờ bị preflight.

### 3. Build lại frontend — không được bỏ qua

`VITE_API_URL` được biên dịch vào bundle lúc build. Chỉ restart thôi thì host API
cũ vẫn nằm trong bundle, và mọi request sẽ đi tới hostname không còn phân giải được.

```bash
git pull origin main
docker compose -f docker-compose.yml build backend frontend
docker compose -f docker-compose.yml up -d
```

### 4. Đăng ký lại redirect URI của OAuth

Cập nhật authorised redirect URI trong **Google Cloud Console** và trong
**Keycloak client** cho khớp các giá trị ở trên. Redirect URI cũ sẽ lỗi ngay tại
nhà cung cấp, nên thông báo lỗi hiện trên màn hình của họ chứ không phải ứng dụng này.

### 5. Trỏ lại các MCP client

Đổi `https://api.<domain>/mcp/` thành `https://<domain>/mcp/` trong cấu hình của
từng client. **API key hiện có vẫn dùng được** — chỉ URL thay đổi. Hướng dẫn
trong ứng dụng tại **User Settings → API Keys** luôn hiển thị URL đúng với
deployment bạn đang xem.

### 6. HA peers

Mọi peer URL có dạng `api.<domain>` phải được cập nhật — sang URL duy nhất của
peer đó, hoặc sang `http://<ip>:8000` để đi thẳng tới backend, bỏ qua proxy. Kiểm
tra cả `PEER_BACKEND_URL`/`PEER_NODES` trong `.env` lẫn các bản ghi `HaPeerNode`
đã có trong database (`GET /api/v1/sync/peers`).

### 7. Kiểm tra

```bash
curl -sf https://tacacs.example.com/api/v1/utils/health-check/   # API qua proxy
curl -sI https://tacacs.example.com/docs                         # Swagger
curl -si -X POST https://tacacs.example.com/mcp/                 # 401 khi không có key
```

Sau đó đăng nhập, và — nếu bạn dùng — xác nhận passkey và OAuth vẫn hoạt động
trước khi coi như đã nâng cấp xong.

### Nếu có sự cố

Không có thay đổi nào chạm tới database, nên rollback chỉ là `git checkout <tag
cũ>`, khôi phục `.env` cũ và build lại. Không có migration nào phải hoàn tác.

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
# Xác nhận prestart đã chạy migration và thoát sạch
docker compose logs prestart | tail -20

# Xác nhận backend khởi động sạch
docker compose logs --tail=20 backend

# Xác nhận revision đang được áp dụng
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER $POSTGRES_DB -c \
  "SELECT version_num FROM alembic_version;"

# Xác nhận API healthy. Cổng 8000 cố ý không được publish ở production (chỉ có
# 49/tcp cho TACACS+), nên hãy hỏi thẳng container.
# Endpoint trả về đúng giá trị JSON `true`.
docker compose exec backend \
  curl -sf http://localhost:8000/api/v1/utils/health-check/

# Từ bên ngoài thì đi qua URL công khai:
curl -sf https://tacacs.yourdomain.com/api/v1/utils/health-check/
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
