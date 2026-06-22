# TACACS-NG-UI

<div align="center">

🌐 **Language / Ngôn ngữ:** [🇬🇧 English](./README.md) | [🇻🇳 Tiếng Việt](./README.vi.md)

</div>

---

**tacacs-ng-ui** là ứng dụng web full-stack hiện đại, cung cấp giao diện đồ họa thân thiện để quản lý cấu hình TACACS+ server. Ứng dụng giúp đơn giản hóa việc quản trị xác thực, phân quyền và kế toán (AAA) cho thiết bị mạng thông qua dashboard web trực quan.

Được xây dựng trên nền tảng công nghệ hiện đại với backend FastAPI và frontend React, đảm bảo hiệu suất cao, khả năng mở rộng và dễ bảo trì cho quản trị viên mạng.

## Mục Lục

- [Tính Năng Nổi Bật](#tính-năng-nổi-bật)
- [Demo Trực Tuyến](#demo-trực-tuyến)
- [Cấu Hình Thiết Bị](#cấu-hình-thiết-bị)
  - [Thiết bị đã kiểm thử (GitHub Discussions)](https://github.com/thangphan205/tacacs-ng-ui/discussions/185)
  - [Cấu hình Juniper (Junos)](docs/vi/config-examples/juniper.md)
  - [Cấu hình Cisco (IOS/XE)](docs/vi/config-examples/cisco.md)
  - [Cấu hình Arista (EOS)](docs/vi/config-examples/arista.md)
  - [Cấu hình Huawei (VRP)](docs/vi/config-examples/huawei.md)
- [Công Nghệ Sử Dụng](#công-nghệ-sử-dụng)
- [Hướng Dẫn Sử Dụng](#hướng-dẫn-sử-dụng)
- [Triển Khai](#triển-khai-trên-localhost)
  - [Localhost](#triển-khai-trên-localhost)
  - [Remote server](#triển-khai-trên-remote-server)
  - [Tên miền](#triển-khai-với-tên-miền)
  - [High Availability (HA)](#triển-khai-high-availability-ha)
- [Tài Liệu Phát Triển](#phát-triển-backend)
- [Ảnh Chụp Màn Hình](#dashboard-1)
- [Lộ Trình Phát Triển](#lộ-trình-phát-triển)
- [Release Notes](#release-notes)
- [Giấy Phép](#giấy-phép)

---

## Tính Năng Nổi Bật

- **Giao Diện Web Trực Quan**: Quản lý người dùng, nhóm và chính sách TACACS+ qua giao diện responsive được xây dựng bằng React và Chakra UI.
- **TACACS+ Server**: Sử dụng [tac_plus-ng](https://github.com/MarcJHuber/event-driven-servers) làm TACACS+ server — bản triển khai hiện đại, được duy trì tích cực.
- **Quản Lý Cấu Hình Có Phiên Bản**: Tạo, xem trước và kích hoạt các snapshot cấu hình TACACS+ — mỗi phiên bản được lưu trữ, có thể khôi phục và so sánh với trình xem diff tích hợp.
- **Dashboard Quan Sát**: Tóm tắt log hôm nay (số lượng auth/authz/acct), thẻ tổng quan thực thể, hoạt động người dùng gần đây và biểu đồ Top 5 & xu hướng với bộ lọc 7 ngày / 30 ngày / khoảng thời gian tùy chọn.
- **Trình Xem Sự Kiện Log**: Duyệt sự kiện log TACACS+ với bộ chọn ngày, bộ lọc loại/kết quả/tên người dùng, drill-down theo tên người dùng, cột lệnh, cột port/TTY và ngăn kéo chi tiết với timeline phiên để kiểm tra chuỗi lệnh.
- **Tích Hợp SIEM**: Chuyển tiếp sự kiện log TACACS+ theo thời gian thực qua HTTP webhook (định dạng Splunk HEC) và/hoặc syslog (UDP/TCP).
- **Tìm Kiếm Toàn Cục**: Mọi bảng quản lý (Hosts, Users, Groups, Profiles, Rulesets,...) đều có ô tìm kiếm trực tiếp với lọc phía server, không phân biệt hoa thường, có debounce.
- **Audit Logging Toàn Diện**: Mọi hành động trên UI được ghi lại với thông tin actor, IP, snapshot thực thể (trước/sau) và timestamp. Bảng chỉ dành cho superuser với tìm kiếm, bộ lọc ngày và xuất CSV.
- **Alert Rules Thời Gian Thực**: Định nghĩa quy tắc (đột biến lỗi xác thực, tên người dùng/IP mới, thay đổi cấu hình, kích hoạt) với cửa sổ thời gian, ngưỡng, cooldown và mức độ nghiêm trọng có thể cấu hình. Thông báo qua Telegram, Slack, Discord, Teams hoặc webhook — đánh giá mỗi 5 phút từ file log trực tiếp.
- **Phát Hiện Bất Thường ML**: Mô hình IsolationForest chấm điểm mỗi người dùng hàng ngày theo 4 đặc trưng hành vi (trung bình/độ lệch chuẩn lỗi xác thực, số IP duy nhất, tỷ lệ từ chối). Kết quả phân loại normal/low/medium/high/critical và hiển thị trên trang UI riêng.
- **Xác Thực Đa Yếu Tố**: Google OAuth, Keycloak OIDC và Passkeys (WebAuthn) ngoài email/mật khẩu.
- **Bảo Mật Theo Thiết Kế**: Chính sách mật khẩu tuân thủ PCI DSS, xác thực JWT và khôi phục mật khẩu qua email.
- **Công Cụ Tích Hợp**: Traefik reverse proxy, tài liệu API tự động qua Swagger UI và kiểm thử end-to-end với Playwright.

## Demo Trực Tuyến

Video Demo (English): [English - Demo tacacs-ng-ui - Setup for Juniper Devices](https://youtu.be/MUGusXOFJBI)

Video Tiếng Việt: [tacacs-ng-ui - Demo - Cấu hình chứng thực tập trung với thiết bị Juniper](https://youtu.be/vnuZMcHxpH4)

Nhóm Telegram: <https://t.me/+v1eAXg-BhotlODY1>

Cộng đồng Reddit: <https://www.reddit.com/r/tacacs_ng_ui/>

Bạn có thể đăng ký tài khoản và sử dụng TACACS server này để test với lab mô phỏng.

- **Dashboard:** <https://dashboard.tacacs.9ping.cloud>
- **IP TACACS Server:** Ping dashboard.tacacs.9ping.cloud để lấy IP TACACS Server.

```bash
ping dashboard.tacacs.9ping.cloud
```

- **TACACS key:** `change_this`

**Thông Tin Đăng Nhập Demo:**

- **Tài khoản Admin**
  - **Username:** `user_admin`
  - **Password:** `change_this`
- **Tài khoản Chỉ Đọc**
  - **Username:** `user_read_only`
  - **Password:** `change_this`

## Cấu Hình Thiết Bị

> [!TIP]
> **Thiết bị đã kiểm thử**: Bạn đang tìm kiếm danh sách các thiết bị tương thích đã được cộng đồng kiểm thử hoặc muốn báo cáo thiết bị bạn đã thử nghiệm? Hãy truy cập [Danh sách thiết bị tương thích trên GitHub Discussions](https://github.com/thangphan205/tacacs-ng-ui/discussions/185).

Dưới đây là các ví dụ cấu hình nhanh cho các nhà sản xuất thiết bị mạng phổ biến. Để xem hướng dẫn tích hợp chi tiết từng bước bao gồm ánh xạ user/group, AAA scheme và bản dump cấu hình tham chiếu đầy đủ, vui lòng xem:

* **Juniper Junos**: [docs/vi/config-examples/juniper.md](docs/vi/config-examples/juniper.md)
* **Cisco IOS/XE**: [docs/vi/config-examples/cisco.md](docs/vi/config-examples/cisco.md)
* **Arista EOS**: [docs/vi/config-examples/arista.md](docs/vi/config-examples/arista.md)
* **Huawei VRP**: [docs/vi/config-examples/huawei.md](docs/vi/config-examples/huawei.md)

---

### Cấu Hình Juniper

<details>
<summary>Hiển thị câu lệnh cấu hình</summary>

```bash
# Ví dụ cấu hình Juniper cho TACACS+

# 1. Định nghĩa class người dùng cục bộ cho TACACS+
set system login class read-only-local idle-timeout 15
set system login class read-only-local permissions view
set system login class read-only-local permissions view-configuration
set system login class super-user-local idle-timeout 15
set system login class super-user-local permissions all
set system login user tacacs_read_only uid 2001
set system login user tacacs_read_only class read-only-local
set system login user tacacs_super_user uid 2002
set system login user tacacs_super_user class super-user-local

# 2. Đặt thứ tự xác thực: TACACS+ trước, sau đó mật khẩu cục bộ
set system authentication-order tacplus
set system authentication-order password

# 3. Cấu hình thông tin TACACS+ server
set system tacplus-server <IP_TACACS_SERVER> port 49
set system tacplus-server <IP_TACACS_SERVER> secret <TACACS_SECRET_KEY>
set system tacplus-server <IP_TACACS_SERVER> source-address <DEVICE_SOURCE_IP>

# 4. Cấu hình accounting để gửi log đến TACACS+ server
set system accounting events login
set system accounting events change-log
set system accounting events interactive-commands
set system accounting destination tacplus server <IP_TACACS_SERVER> secret <TACACS_SECRET_KEY>
set system accounting destination tacplus server <IP_TACACS_SERVER> source-address <DEVICE_SOURCE_IP>
```
</details>

### Cấu Hình Cisco

<details>
<summary>Hiển thị câu lệnh cấu hình</summary>

```bash
# 1. Kích hoạt AAA
aaa new-model

# 2. Định nghĩa TACACS+ server
tacacs server TACACS-9PING
  address ipv4 <IP_TACACS_SERVER>
  key <TACACS_SECRET_KEY>
  exit

# 3. Tạo server group
aaa group server tacacs+ TACACS-GROUP
  server name TACACS-9PING
  exit

# 4. Cấu hình Authentication, Authorization, Accounting
aaa authentication login default group TACACS-GROUP local
aaa authorization exec default group TACACS-GROUP local
aaa accounting exec default start-stop group TACACS-GROUP
aaa accounting commands 15 default start-stop group TACACS-GROUP

# 5. Áp dụng cho VTY lines
line vty 0 4
  login authentication default
exit
```
</details>

### Cấu Hình Arista

<details>
<summary>Hiển thị câu lệnh cấu hình</summary>

```bash
# 1. Định nghĩa TACACS+ server và shared key
tacacs-server host <IP_TACACS_SERVER> key 0 <TACACS_SECRET_KEY>
!
# 2. Tạo server group
aaa group server tacacs+ TACACS_GROUP
  server <IP_TACACS_SERVER>
!
# 3. Cấu hình AAA
aaa authentication login default group TACACS_GROUP local
aaa authorization exec default group TACACS_GROUP local
aaa authorization commands all default group TACACS_GROUP local
aaa accounting exec default start-stop group TACACS_GROUP

# 4. (Tùy chọn) Chỉ định interface nguồn cho TACACS+
ip tacacs source-interface Management0
```
</details>

## Công Nghệ Sử Dụng

- ⚡ [**FastAPI**](https://fastapi.tiangolo.com) cho Python backend API.
  - 🧰 [SQLModel](https://sqlmodel.tiangolo.com) cho tương tác SQL database (ORM).
  - 🔍 [Pydantic](https://docs.pydantic.dev) cho validation dữ liệu và quản lý settings.
  - 💾 [PostgreSQL](https://www.postgresql.org) làm SQL database.
- 🚀 [React](https://react.dev) cho frontend.
  - 💃 TypeScript, hooks, Vite và các thành phần của modern frontend stack.
  - 🎨 [Chakra UI](https://chakra-ui.com) cho frontend components.
  - 🤖 Frontend client tự động generate từ OpenAPI schema.
  - 🧪 [Playwright](https://playwright.dev) cho kiểm thử End-to-End.
  - 🦇 Hỗ trợ Dark mode.
- 🐋 [Docker Compose](https://www.docker.com) cho development và production.
- 🔒 Băm mật khẩu bảo mật theo mặc định.
- 🔑 Xác thực JWT (JSON Web Token).
- 📫 Khôi phục mật khẩu qua email.
- ✅ Kiểm thử với [Pytest](https://pytest.org).
- 📞 [Traefik](https://traefik.io) làm reverse proxy / load balancer.
- 🚢 Hướng dẫn triển khai bằng Docker Compose, bao gồm cách thiết lập HTTPS tự động với Traefik.
- 🏭 CI/CD dựa trên GitHub Actions.

## Hướng Dẫn Sử Dụng

Xem hướng dẫn đầy đủ tại **[User Guide](docs/vi/user-guide.md)** (song ngữ English / Tiếng Việt).

## Triển Khai Trên Localhost

```bash
git clone https://github.com/thangphan205/tacacs-ng-ui
cd tacacs-ng-ui
cp .env.example .env   # chỉnh sửa .env và đặt secrets của bạn
docker compose up -d
```

Truy cập: <http://localhost:5173> với thông tin đăng nhập đã cấu hình trong `.env`:

```bash
Username: admin@example.com   # FIRST_SUPERUSER trong .env
Password: <FIRST_SUPERUSER_PASSWORD trong .env>
```

URL phát triển cục bộ:

| Dịch vụ | URL |
|---|---|
| Frontend | <http://localhost:5173> |
| Backend | <http://localhost:8000> |
| Swagger UI | <http://localhost:8000/docs> |
| ReDoc | <http://localhost:8000/redoc> |
| Adminer | <http://localhost:8080> |
| Traefik UI | <http://localhost:8090> |
| MailCatcher | <http://localhost:1080> |

## Triển Khai Trên Remote Server

Ví dụ, triển khai tacacs-ng-ui trên server: 192.168.8.8

```bash
git clone https://github.com/thangphan205/tacacs-ng-ui
cd tacacs-ng-ui
cp .env.example .env   # chỉnh sửa .env với IP, secrets và mật khẩu của bạn
```

Thay đổi IP API Server:
```vi docker-compose.override.yml```

```bash
  frontend:
    restart: "no"
    ports:
      - "5173:80"
    build:
      context: ./frontend
      args:
        - VITE_API_URL=http://192.168.8.8:8000
        - NODE_ENV=development
```

Thêm server vào BACKEND_CORS_ORIGINS:

```vi .env```

```BACKEND_CORS_ORIGINS="http://192.168.8.8:5173,..."```

Khởi động server:

```docker compose up -d```

Truy cập: <http://192.168.8.8:5173> với thông tin đăng nhập trong `.env`.

Lưu ý: chạy `docker compose build` khi thay đổi cấu hình/code.

```bash
docker compose build
docker compose up -d
```

## Triển Khai Với Tên Miền

Xem [deployment.vi.md](docs/vi/deployment.md).

## Triển Khai High Availability (HA)

tacacs-ng-ui hỗ trợ hai mô hình triển khai HA để chạy hai TACACS+ server ở các vùng khác nhau:

| Mô hình | Mô tả |
|---------|-------|
| **Độc lập** | Hai stack hoàn toàn tách biệt — không đồng bộ, mỗi vùng quản lý độc lập |
| **Primary–Standby** | Zone B sao chép từ Zone A qua PostgreSQL streaming replication; cấu hình đồng bộ tự động hoặc theo yêu cầu |

<p align="center">
  <img src="img/high-availability-model-a.svg" alt="Mô hình A — Độc lập" width="49%" />
  <img src="img/high-availability-model-b.svg" alt="Mô hình B — Primary–Standby" width="49%" />
</p>

Cả hai mô hình đều hỗ trợ cấu hình LDAP riêng theo vùng qua biến `MAVIS_OVERRIDE_*`.

**Hướng dẫn đầy đủ:** [docs/vi/high-availability.md](docs/vi/high-availability.md)

### Cấu Hình

Cập nhật các giá trị trong file `.env` trước khi triển khai. Tối thiểu phải thay đổi:

- `SECRET_KEY`
- `FIRST_SUPERUSER_PASSWORD`
- `POSTGRES_PASSWORD`

Xem [deployment.vi.md](docs/vi/deployment.md) để biết thêm chi tiết.

### Google OAuth (tùy chọn)

Để bật "Đăng nhập bằng Google", tạo OAuth credentials tại [Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → OAuth 2.0 Client ID, sau đó thêm vào `.env`:

```bash
GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-client-secret
GOOGLE_REDIRECT_URI=http://<your-host>:8000/api/v1/oauth/google/callback
```

### Tạo Secret Keys

Một số biến môi trường có giá trị mặc định là `changethis`. Tạo secret key bằng lệnh:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Phát Triển Backend

Tài liệu backend: [backend/README.md](./backend/README.md).

## Phát Triển Frontend

Tài liệu frontend: [frontend/README.md](./frontend/README.md).

## Tài Liệu Triển Khai

Xem [deployment.vi.md](docs/vi/deployment.md).

## Tài Liệu Phát Triển

Xem [development.vi.md](docs/vi/development.md).

Bao gồm Docker Compose, custom local domains, cấu hình `.env`, v.v.

## Dashboard

[![Dashboard](img/dashboard.png)](https://github.com/thangphan205/tacacs-ng-ui)

## Docs API

[![API docs](img/api.png)](https://github.com/thangphan205/tacacs-ng-ui)

## Tacacs Config File Generator

[![Tacacs Config](img/dashboard-tacacs-config.png)](https://github.com/thangphan205/tacacs-ng-ui)

## Traefik

[![Traefik](img/traefik.png)](https://github.com/thangphan205/tacacs-ng-ui)

## Adminer

[![Adminer](img/adminer.png)](https://github.com/thangphan205/tacacs-ng-ui)

## Audit Logs

[![Audit Logs](img/audit-logs.png)](https://github.com/thangphan205/tacacs-ng-ui)

## Auth Providers

[![Auth Providers](img/auth-providers.png)](https://github.com/thangphan205/tacacs-ng-ui)

## Lộ Trình Phát Triển

1. **Framework Xác Thực Hiện Đại**: ✅ Google OAuth (Authorization Code flow), ✅ Keycloak OIDC và ✅ Passkeys (WebAuthn) cho đăng nhập không mật khẩu — hỗ trợ từ v0.2.0.
2. **Audit Logging Frontend Toàn Diện**: ✅ Mọi hành động UI đều được ghi lại với actor, IP, snapshot thực thể và timestamp từ v0.2.1. Bao gồm xuất CSV, tìm kiếm và bộ lọc ngày.
3. **Dashboard Quan Sát Nâng Cao**: ✅ Tóm tắt log hôm nay, thẻ tổng quan, hoạt động người dùng gần đây, biểu đồ Top 5 với bộ lọc 7/30 ngày — ra mắt trong v0.3.0. Cải tiến trong v0.3.2 với drill-down tên người dùng, cột lệnh/port, ngăn kéo chi tiết và timeline phiên.
4. **Tích Hợp SIEM**: ✅ Chuyển tiếp thời gian thực qua HTTP webhook (Splunk HEC) và syslog (UDP/TCP) từ v0.3.0.
5. **Phát Hiện Bất Thường & Cảnh Báo**: ✅ Alert rules thời gian thực với thông báo đa kênh (Telegram, Slack, Discord, Teams, Google Chat, Email/SMTP, webhook) và phát hiện bất thường ML (IsolationForest) từ v0.3.5–v0.3.6.

## Release Notes

Xem file [release-notes.md](docs/en/release-notes.md).

## Giấy Phép

Dự án được cấp phép theo giấy phép MIT.

Source code: <https://github.com/thangphan205/tacacs-ng-ui>
