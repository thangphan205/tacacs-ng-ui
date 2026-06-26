# Hướng Dẫn Triển Khai High Availability (HA)

Hướng dẫn này giải thích cách chạy hai phiên bản tacacs-ng-ui ở hai vùng khác nhau để thiết bị mạng luôn có TACACS+ server có thể kết nối được.

---

## Chọn Mô Hình Triển Khai

| | **Mô hình A — Độc lập** | **Mô hình B — Primary–Standby** | **Mô hình C — Đa Node** |
|-|------------------------|----------------------------------|--------------------------|
| Database | Mỗi vùng có DB riêng | Zone B sao chép từ Zone A | N standby sao chép từ primary |
| Đồng bộ cấu hình | Thủ công (admin quản lý cả hai) | Tự động hoặc một thao tác | Fan-out đến tất cả standby |
| Độ phức tạp | Thấp | Trung bình | Trung bình |
| Failover | Thiết bị tự chuyển sang server kia | Nâng cấp standby bằng một lệnh | Nâng cấp bất kỳ standby nào |
| Phù hợp | Hai vùng phục vụ nhóm thiết bị khác nhau, hoặc cần cô lập hoàn toàn | Một nhóm admin, cấu hình đồng nhất giữa hai vùng | Đa datacenter, hơn 2 vùng |

Tất cả mô hình đều không cần thay đổi các triển khai hiện có — Mô hình A không cần thay đổi code.

---

## Mô Hình A — Độc Lập (Không Đồng Bộ)

<p align="center">
  <img src="../../img/high-availability-model-a.svg" alt="Mô hình A — Triển khai độc lập" width="800px" />
</p>

Hai stack hoàn toàn tách biệt. Không có kết nối giữa hai vùng.

### Triển khai Zone A

```bash
git clone <repo> && cd tacacs-ng-ui
cp .env.example .env
# Chỉnh .env cho Zone A (DOMAIN, SECRET_KEY, POSTGRES_*, v.v.)
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

### Triển khai Zone B

```bash
git clone <repo> && cd tacacs-ng-ui
cp .env.example .env
# Chỉnh .env cho Zone B — dùng DOMAIN, SECRET_KEY, POSTGRES_PASSWORD khác
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

Mỗi vùng có dashboard quản trị riêng. Thay đổi cấu hình phải áp dụng trên cả hai vùng.

---

## Mô Hình B — Primary–Standby (Có Đồng Bộ)

<p align="center">
  <img src="../../img/high-availability-model-b.svg" alt="Mô hình B — Triển khai Primary–Standby" width="800px" />
</p>

Zone A là primary (nhận toàn bộ ghi). Zone B là hot standby — PostgreSQL tự động sao chép từ Zone A. Khi cấu hình thay đổi trên Zone A, Zone B nhận qua [auto-sync hoặc manual sync](#chế-độ-đồng-bộ-cấu-hình).

### Yêu Cầu

**Cổng cần mở giữa hai vùng:**

| Cổng | Chiều | Mục đích |
|------|-------|----------|
| `5432` | Zone B → Zone A | PostgreSQL streaming replication |
| `8000` | Zone A → Zone B | Trigger reload cấu hình nội bộ (tùy chọn, chỉ auto-sync) |
| `49` | Thiết bị mạng → cả hai vùng | Xác thực TACACS+ |
| `443` | Trình duyệt admin → cả hai vùng | Dashboard HTTPS |

> **Bảo mật:** Chỉ mở cổng 5432 trên mạng nội bộ/VPN, không bao giờ expose ra internet.

---

### Bước 1 — Triển Khai Zone A (Primary)

Thêm các biến HA vào `.env` của Zone A:

```bash
# Bổ sung vào .env Zone A
NODE_ROLE=primary
SCHEDULER_ENABLED=true
SYNC_MODE=auto            # hoặc: manual
PEER_BACKEND_URL=https://api-b.yourdomain.com   # URL API nội bộ của Zone B — bắt buộc có http:// hoặc https://
INTERNAL_SYNC_TOKEN=<tạo bằng: openssl rand -hex 32>
```

> **`PEER_BACKEND_URL` bắt buộc phải có scheme.** Dùng `http://172.25.x.x:8000` cho kết nối IP trực tiếp hoặc `https://api-b.yourdomain.com` cho domain. Bỏ scheme (ví dụ `172.25.x.x:8000`) khiến httpx fail và peer health check luôn báo unreachable.

Chạy script setup một lệnh (tự động khởi động stack + cấu hình replication):

```bash
bash setup-ha.sh
```

Script thực hiện:
1. Khởi động `docker compose up -d`
2. Chờ PostgreSQL sẵn sàng
3. Tạo role `replicator` (idempotent — bỏ qua nếu đã tồn tại)
4. Tự resolve IP Zone B từ `PEER_BACKEND_URL` và thêm vào `pg_hba.conf`
5. Reload cấu hình PostgreSQL (không cần restart)

<details>
<summary>Thay thế thủ công (nếu muốn thực hiện từng bước)</summary>

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d

# Tạo replication role (load các biến môi trường từ .env trước để resolve $POSTGRES_USER)
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER -c \
  "CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'your-replication-password';"

# Cho phép IP Zone B kết nối để replication
# ↓ Thay bằng IP thật của Zone B
ZONE_B_IP=192.168.1.100

docker compose exec db bash -c \
  "echo 'host replication replicator ${ZONE_B_IP}/32 md5' >> \$PGDATA/pg_hba.conf"

# Reload cấu hình PostgreSQL (không cần restart)
docker compose kill -s HUP db
```

</details>

---

### Bước 2 — Triển Khai Zone B (Standby)

Clone repo trên Zone B và cấu hình `.env`:

```bash
git clone <repo> && cd tacacs-ng-ui
cp .env.example .env
```

`.env` của Zone B — giống Zone A, thêm các giá trị sau:

```bash
# Zone B — giống Zone A ngoại trừ các override sau:
NODE_ROLE=standby
SCHEDULER_ENABLED=false           # alert, ML scoring, cron chạy trên Zone A
SYNC_MODE=auto                    # hoặc: manual
PEER_BACKEND_URL=https://api-a.yourdomain.com   # URL Zone A — bắt buộc có http:// hoặc https://
INTERNAL_SYNC_TOKEN=<cùng giá trị với zone-a>
PRIMARY_DB_HOST=<ZONE_A_IP>       # Chỉ IP, không có port (ví dụ 172.25.245.214)
REPLICATION_PASSWORD=your-replication-password

# Trỏ Zone B đến LDAP server cục bộ (xem phần MAVIS bên dưới)
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ldap-zone-b.yourdomain.com:636
```

Chạy script setup một lệnh (thực hiện pg_basebackup + khởi động tất cả service):

```bash
bash setup-ha.sh
```

Script thực hiện:
1. Pull Docker images
2. Chạy `pg_basebackup` từ Zone A qua cổng PostgreSQL 5432 (không cần SSH)
3. Ghi cấu hình streaming replication (`standby.signal`, `primary_conninfo`)
4. Khởi động `docker compose up -d`
5. Xác minh replication đang hoạt động

<details>
<summary>Output mẫu</summary>

```
=== tacacs-ng-ui HA Setup ===
Node Role: standby
=============================
Starting standby node bootstrap...
=== tacacs-ng-ui HA Standby Setup ===
Primary DB host : 172.25.245.214:5432
Node role       : standby

[1/5] Building/pulling images...
[+] pull 7/7
 ✔ Image postgres:18            Pulled
 ✔ Image traefik:v3.7           Pulled
 ✔ Image adminer                Pulled
 ✔ Image schickling/mailcatcher Pulled
 ! Image backend:latest         pull access denied (sẽ build từ source)
 ! Image frontend:latest        pull access denied (sẽ build từ source)
[+] Building 4.3s (53/53) FINISHED
 ✔ Image backend:latest          Built
 ✔ Image frontend:latest         Built
[2/5] Running pg_basebackup from primary (172.25.245.214)...
waiting for checkpoint
21026/33541 kB (62%), 0/1 tablespace
33552/33552 kB (100%), 1/1 tablespace
[3/5] Writing standby replication config...
[4/5] Starting all services...
 ✔ Container tacacs-ng-ui-db-1          Healthy
 ✔ Container tacacs-ng-ui-backend-1     Started
 ✔ Container tacacs-ng-ui-frontend-1    Started
[5/5] Verifying replication...
 is_standby | replication_lag
------------+-----------------
 t          |
(1 row)

=== Setup complete ===
Zone B is now running as a hot standby replica of 172.25.245.214.

Dashboard : https://172.25.245.236
API       : http://172.25.245.236:8000
```

</details>

**Kiểm tra replication:**

```bash
# Load biến .env vào shell hiện tại trước
export $(grep -v '^#' .env | xargs)

# Trên Zone B — kết quả phải là: t (true = đang ở chế độ standby)
docker compose exec db psql -U $POSTGRES_USER -c "SELECT pg_is_in_recovery();"

# Trên Zone A — phải hiển thị Zone B đã kết nối
docker compose exec db psql -U $POSTGRES_USER -c "SELECT * FROM pg_stat_replication;"
```

---

### Chế Độ Đồng Bộ Cấu Hình

Đặt `SYNC_MODE` trong `.env` của Zone B để kiểm soát cách tac_plus-ng nhận thay đổi cấu hình từ Zone A.

#### `SYNC_MODE=auto` (mặc định)

Daemon `config_sync_watcher` của Zone B kiểm tra DB cục bộ (đã replicate) mỗi 10 giây. Khi phát hiện thay đổi cấu hình, nó tự động tạo lại `tac_plus-ng.cfg` và reload daemon — không cần thao tác của admin.

**Luồng hoạt động:**
1. Admin thay đổi policy trên dashboard Zone A → kích hoạt cấu hình
2. API Zone A reload daemon tac_plus-ng của mình
3. API Zone A gọi endpoint reload nội bộ của Zone B (fire-and-forget)
4. Zone B tạo lại cấu hình từ DB replicate cục bộ + reload daemon
5. Cả hai vùng đồng nhất trong ~10 giây

#### `SYNC_MODE=manual`

Zone B **không** tự động reload. DB vẫn replicate liên tục (users, policy luôn đồng bộ), nhưng tac_plus-ng chỉ nhận cấu hình mới khi admin chủ động đẩy.

**Cách đẩy cấu hình:**

- **Dashboard:** Nhấn nút **"Sync to Zone B"** trên trang TACACS+ Configuration (chỉ hiển thị trên primary node với manual sync mode)
- **API:**
  ```bash
  curl -X POST https://api-a.yourdomain.com/api/v1/sync/push-config \
    -H "Authorization: Bearer <your-token>"
  ```

Dùng manual mode khi muốn kiểm tra cấu hình trên Zone A trước khi áp dụng lên Zone B.

---

## Thống Kê AAA Theo Node

Trong triển khai multi-node, mỗi TACACS-NG node phục vụ traffic riêng và ghi log file cục bộ. Primary node thu thập thống kê từ tất cả peer và lưu vào DB với nhãn `NODE_NAME` của từng node, giúp dashboard hiển thị dữ liệu theo từng node và so sánh song song.

### Cơ Chế Hoạt Động

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
  upsert rows tagged với         │
  NODE_NAME của standby vào DB   │
```

1. **Primary** chạy cron script của mình (lưu stats với `NODE_NAME` của nó)
2. **Primary** gọi `POST /api/v1/sync/internal/collect-stats?date=YYYY-MM-DD` đến từng peer trong `PEER_NODES`
3. **Standby** parse log file cục bộ và trả về JSON thô — **không** ghi vào DB read-only
4. **Primary** upsert dữ liệu nhận được vào DB, gắn nhãn `NODE_NAME` của standby

Xác thực dùng header `X-Internal-Token` với `INTERNAL_SYNC_TOKEN` dùng chung.

### Cấu Hình

**Primary `.env`:**

```bash
NODE_NAME=dc1-primary          # định danh node này trong thống kê
PEER_NODES=http://dc2-standby:8000,http://dc3-standby:8000   # danh sách peer, phân cách bằng dấu phẩy
INTERNAL_SYNC_TOKEN=<secret-dùng-chung-với-standby>
STATS_INTERVAL_MINUTES=30      # thu thập thống kê hôm nay mỗi 30 phút (0 = tắt)
```

**Mỗi Standby `.env`:**

```bash
NODE_NAME=dc2-standby          # phải duy nhất trên mỗi node
INTERNAL_SYNC_TOKEN=<secret-dùng-chung-với-primary>
# PEER_NODES không cần trên standby (chỉ primary điều phối thu thập)
```

### Thu Thập Thống Kê Gần Thời Gian Thực

Primary backend chạy vòng lặp nền thu thập thống kê hôm nay theo chu kỳ cấu hình được. Giúp các trang Range và Node Comparison luôn cập nhật mà không cần đợi đến cron 1 giờ sáng.

| Cấu hình | Mặc định | Hiệu quả |
|----------|----------|----------|
| `STATS_INTERVAL_MINUTES=30` | 30 | Thu thập mỗi 30 phút |
| `STATS_INTERVAL_MINUTES=5` | — | Gần thời gian thực (tải CPU/DB cao hơn) |
| `STATS_INTERVAL_MINUTES=1` | — | Thời gian thực (chỉ nếu log file nhỏ) |
| `STATS_INTERVAL_MINUTES=0` | — | Tắt vòng lặp nền (chỉ dùng cron hàng đêm) |

Vòng lặp cũng gọi tất cả peer trong `PEER_NODES` cùng chu kỳ, giúp thống kê standby luôn cập nhật.

**Tự động làm mới dashboard:** Tất cả ba trang thống kê (Today, Range, Node Comparison) tự động tải lại dữ liệu từ backend mỗi 5 phút khi tab trình duyệt đang mở.

### Tính Năng Dashboard

| Trang | Đường dẫn | Mô tả |
|-------|-----------|-------|
| AAA Statistics (Today) | Sidebar → AAA Statistics | Dropdown lọc theo node — xem thống kê hôm nay theo từng node |
| AAA Statistics Range | Sidebar → AAA Range Stats | Dropdown lọc theo node — xem thống kê theo khoảng thời gian |
| Node Comparison | Sidebar → Node Comparison | Thẻ card song song: một card mỗi node, hiển thị tổng số liệu + biểu đồ xu hướng |

### Thu Thập Thủ Công

```bash
# Thu thập thống kê cho hôm nay trên tất cả node
curl -X POST -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/aaa_statistics/run/

# Thu thập cho ngày cụ thể
curl -X POST -H "Authorization: Bearer <token>" \
  "https://api-a.yourdomain.com/api/v1/aaa_statistics/run/?date=2026-06-25"
```

---

## Hành Vi Của Standby Node

Khi `NODE_ROLE=standby`, backend hoạt động khác để bảo vệ DB read-only replica:

| Tính năng | Primary | Standby |
|-----------|---------|---------|
| Ghi vào DB (users, configs, policies) | ✅ | ❌ HTTP 403 |
| Đọc từ DB (dashboard, logs, stats) | ✅ | ✅ |
| Ghi audit log | ✅ | ⏭ Bỏ qua (replicate từ primary) |
| Chạy DB migration khi khởi động | ✅ | ⏭ Bỏ qua (schema đến qua replication) |
| Alert evaluation / ML scoring / cron | ✅ | ❌ Tắt (`SCHEDULER_ENABLED=false`) |
| Xác thực TACACS+ (cổng 49) | ✅ | ✅ |
| Dashboard — xem | ✅ | ✅ |
| Dashboard — chỉnh sửa | ✅ | ❌ Chặn với thông báo "read-only mode" |

### Dashboard Trạng Thái HA

Sidebar có trang **High Availability** (dưới Monitoring) hiển thị trạng thái đồng bộ real-time của cả hai node. Tự refresh mỗi 30 giây, hiển thị:

- Node role (Primary / Standby)
- Trạng thái kết nối peer (Connected / Unreachable)
- Chế độ đồng bộ (Auto / Manual)
- Thời điểm sync cấu hình lần cuối
- Nút sync thủ công (chỉ hiện khi primary + manual mode)

---

## Cấu Hình MAVIS / LDAP Theo Vùng

Mỗi vùng có thể trỏ đến LDAP server khác nhau bằng biến `MAVIS_OVERRIDE_*`. Các biến này ghi đè giá trị MAVIS trong database tại thời điểm tạo cấu hình — không cần thay đổi schema.

```bash
# .env Zone A
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ldap-zone-a.yourdomain.com:636

# .env Zone B
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ldap-zone-b.yourdomain.com:636
```

Có thể override bất kỳ MAVIS key nào trong database:

```bash
MAVIS_OVERRIDE_LDAP_SERVER_TYPE=freeipa
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ipa-zone-b.example.com:636
MAVIS_OVERRIDE_LDAP_BASE=dc=example,dc=com
MAVIS_OVERRIDE_LDAP_USER=uid=svc_tacacs,cn=users,cn=accounts,dc=example,dc=com
MAVIS_OVERRIDE_LDAP_PASSWD=zone-b-service-account-password
```

Nếu không đặt override, giá trị trong database được dùng (giống nhau trên cả hai vùng).

---

## Cấu Hình Thiết Bị Mạng

Cấu hình tất cả thiết bị mạng với IP của cả hai vùng. Thiết bị thử Zone A trước, failover sang Zone B trong TACACS timeout (thường 5 giây).

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

## Nâng Cấp Lên Phiên Bản Mới

> **Cơ chế:** Migration DB chạy trên Zone A. PostgreSQL replication tự động đồng bộ schema sang Zone B trước khi Zone B restart — standby không chạy migration.

### Rolling upgrade (không gián đoạn TACACS)

```bash
# ── Trên CẢ HAI zone ───────────────────────────────────────────
git pull origin main

# ── Zone A trước ───────────────────────────────────────────────
# Thiết bị tự failover sang Zone B trong lúc Zone A restart (~5 giây)
docker compose up -d --build backend

# Chờ Zone A healthy và migration đã replicate sang Zone B
docker compose logs -f backend | grep "Application startup complete"

# ── Zone B sau ─────────────────────────────────────────────────
# Thiết bị tự failover về Zone A trong lúc Zone B restart (~5 giây)
docker compose up -d --build backend
```

Xác thực TACACS không bị gián đoạn — thiết bị luôn dùng zone còn lại trong lúc mỗi backend restart.

### Nếu migration thêm cột NOT NULL mới

Các migration trong project này luôn có `server_default` trên cột NOT NULL nên áp dụng online không cần lock. Không cần bước thêm.

### Kiểm tra sau nâng cấp

```bash
# Zone A — xác nhận version mới đang chạy
docker compose exec backend python -c "import app; print('ok')"

# Zone B — xác nhận replication lag thấp
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER -c \
  "SELECT now() - pg_last_xact_replay_timestamp() AS replication_lag;"
```

---

## Mô Hình C — Đa Node (N Standby)

Dành cho triển khai hơn hai vùng (ví dụ DC1 primary + DC2 + DC3 standby).

Kiến trúc giống Mô hình B, một primary và N standby. Đồng bộ cấu hình tự động fan-out đến tất cả peer node đang bật.

### Bước 1 — Triển Khai Node Primary

Làm theo [Mô hình B Bước 1](#bước-1--triển-khai-zone-a-primary) — cấu hình `.env` với `NODE_ROLE=primary` và chạy `bash setup-ha.sh` trên server primary. Không cần bước thêm cho multi-node; các standby peer được thêm qua UI sau khi chúng khởi động.

### Bước 2 — Triển Khai Từng Node Standby

Với mỗi standby, làm theo [Mô hình B Bước 2](#bước-2--triển-khai-zone-b-standby) — cấu hình `.env` với `NODE_ROLE=standby`, `NODE_NAME` duy nhất, và `PRIMARY_DB_HOST` trỏ về primary, rồi chạy `bash setup-ha.sh`.

### Thêm Standby Thứ Ba (hoặc Nhiều Hơn)

1. Thiết lập PostgreSQL streaming replication từ DB primary đến DB standby mới (giống thiết lập Zone B)
2. Khởi động standby mới với `NODE_ROLE=standby` và cùng `INTERNAL_SYNC_TOKEN`
3. Trên UI primary → **High Availability → Peers → Add Peer** (nhập tên và URL nội bộ của standby mới)
4. Cấu hình đồng bộ đến node mới trong 10 giây (chế độ auto) hoặc lần push thủ công tiếp theo — không cần restart

> **Không cần thay đổi biến môi trường.** Quản lý peer hoàn toàn qua UI. Biến `PEER_NODES` / `PEER_BACKEND_URL` vẫn được hỗ trợ như fallback và tự động import vào DB khi khởi động lần đầu.

### Cấu Hình HA Qua UI

Tất cả cài đặt HA trừ `NODE_ROLE` và `INTERNAL_SYNC_TOKEN` có thể chỉnh sửa qua panel **High Availability → HA Settings** trên primary — không cần restart:

| Cài đặt | Mô tả |
|---------|-------|
| Node name | Nhãn dễ đọc (ví dụ "DC1-Primary") |
| Sync mode | `auto` hoặc `manual` |
| Scheduler enabled | Bật/tắt đánh giá alert, ML scoring, audit purge |
| Stats interval | Chu kỳ thu thập thống kê AAA (phút), 0 = tắt |

### Trạng Thái Đa Node

`GET /api/v1/sync/ha-info` trả về mảng `peers` với trạng thái từng node:

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

### API Quản Lý Peer (chỉ superuser)

```bash
# Liệt kê peer
curl -H "Authorization: Bearer <token>" https://api-a.yourdomain.com/api/v1/sync/peers

# Thêm peer
curl -X POST -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"name": "DC3-Standby", "url": "http://dc3:8000", "enabled": true}' \
  https://api-a.yourdomain.com/api/v1/sync/peers

# Tắt tạm thời một peer
curl -X PATCH -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"enabled": false}' \
  https://api-a.yourdomain.com/api/v1/sync/peers/<peer-id>

# Xóa peer
curl -X DELETE -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/sync/peers/<peer-id>
```

---

## Quy Trình Failover (Zone A gặp sự cố)

**Nâng cấp standby thành primary qua UI (khuyến nghị):**

Trên UI standby → **High Availability → Promote to Primary**. UI chạy `pg_promote()`, tự đặt `scheduler_enabled=true` trong DB, và hiển thị các bước thủ công còn lại.

**Nâng cấp qua CLI:**

```bash
# Trên server standby
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER -c "SELECT pg_promote();"

# Chỉ cần thay đổi NODE_ROLE (scheduler_enabled đã được DB quản lý):
#   NODE_ROLE=primary

docker compose up -d backend
```

Zone B giờ nhận toàn bộ ghi. Thiết bị mạng đã trỏ sẵn đến Zone B nên xác thực TACACS tiếp tục không gián đoạn.

**Sau khi nâng cấp — dọn dẹp peer:**

1. Mở dashboard HA của node vừa được nâng cấp
2. Xóa primary cũ khỏi bảng Peers (đã không hoạt động)
3. Với mỗi standby còn lại: trỏ lại PostgreSQL replication về primary mới (`pg_rewind` hoặc `pg_basebackup`)

**Khi Zone A phục hồi:**

Gia nhập lại Zone A như standby mới:

```bash
# Trên server Zone A
# Cập nhật .env:
#   NODE_ROLE=standby
#   PRIMARY_DB_HOST=<ZONE_B_IP>

bash setup-ha.sh
```

Sau đó thêm lại Zone A như peer qua UI HA của primary mới.

---

## Tham Chiếu Biến Môi Trường

Tất cả biến HA đều tùy chọn. Mặc định chạy như triển khai single-node bình thường.

> **Lưu ý:** `NODE_NAME`, `SCHEDULER_ENABLED`, `SYNC_MODE`, `PEER_BACKEND_URL`, `PEER_NODES`, và `STATS_INTERVAL_MINUTES` được seed vào database khi primary khởi động lần đầu và có thể thay đổi qua HA UI mà không cần restart. `NODE_ROLE` và `INTERNAL_SYNC_TOKEN` luôn cần restart khi thay đổi.

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `NODE_ROLE` | `primary` | **Chỉ env.** `primary` hoặc `standby`. Kiểm soát quyền ghi DB. Cần restart khi thay đổi. |
| `INTERNAL_SYNC_TOKEN` | _(trống)_ | **Chỉ env.** Shared secret cho các lệnh gọi giữa node. Phải khớp trên tất cả node. Tạo bằng `openssl rand -hex 32`. Cần restart. |
| `NODE_NAME` | `primary` | Seed vào DB khi khởi động lần đầu. Nhãn node dễ đọc (ví dụ `dc1-primary`). Chỉnh qua HA UI sau đó. |
| `SCHEDULER_ENABLED` | `true` | Seed vào DB khi khởi động lần đầu. Đặt `false` trên standby. Tự đặt `true` sau khi promote qua UI. |
| `SYNC_MODE` | `auto` | Seed vào DB khi khởi động lần đầu. `auto` = standby tự reload. `manual` = admin push. Chỉnh qua HA UI. |
| `PEER_BACKEND_URL` | _(trống)_ | Seed như peer đầu tiên khi primary khởi động lần đầu. Dùng HA UI để quản lý peer sau đó. |
| `PEER_NODES` | _(trống)_ | Seed như nhiều peer khi primary khởi động lần đầu (URL phân cách bằng dấu phẩy). Dùng HA UI để quản lý sau đó. |
| `STATS_INTERVAL_MINUTES` | `30` | Seed vào DB khi khởi động lần đầu. Chu kỳ (phút) thu thập thống kê AAA. `0` = chỉ dùng cron hàng đêm. Chỉnh qua HA UI. |
| `PRIMARY_DB_HOST` | _(trống)_ | IP DB host của Zone A. Chỉ cần trên standby khi chạy `setup-standby.sh`. |
| `REPLICATION_PASSWORD` | _(trống)_ | Mật khẩu cho PostgreSQL role `replicator`. Chỉ cần trên standby. |
| `MAVIS_OVERRIDE_<KEY>` | _(trống)_ | Override bất kỳ MAVIS key nào theo vùng (ví dụ `MAVIS_OVERRIDE_LDAP_HOSTS`). |
| `SYNC_WATCHER_INTERVAL` | `10` | Giây giữa các lần kiểm tra thay đổi cấu hình (auto-sync watcher, chỉ standby). |

---

## API Kiểm Tra Trạng Thái HA

**Kiểm tra role node và trạng thái peer:**

```bash
curl -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/sync/ha-info
```

Kết quả:

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

> `peer_backend_url` và `peer_available` giữ lại để tương thích ngược. Dùng mảng `peers` cho triển khai đa node.

**Đẩy cấu hình thủ công đến tất cả standby (manual sync mode):**

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/sync/push-config
```

Kết quả hiển thị từng peer:

```json
{
  "results": [
    {"peer": "DC2-Standby", "url": "https://api-b.yourdomain.com", "status": "ok"},
    {"peer": "DC3-Standby", "url": "https://api-c.yourdomain.com", "status": "error"}
  ]
}
```

---

## Xử Lý Sự Cố

### `pg_basebackup: FATAL: password authentication failed for user "replicator"`

Role `replicator` chưa tồn tại hoặc mật khẩu không khớp trên primary.

**Kiểm tra role có tồn tại không (chạy trên primary):**

```bash
export $(grep -v '^#' .env | grep -v '^$' | xargs)
docker compose exec db psql -U $POSTGRES_USER -c "\du replicator"
```

**Không có kết quả** — role chưa được tạo. Chạy `bash setup-ha.sh` trên primary (khuyến nghị), hoặc tạo thủ công:

```bash
docker compose exec db psql -U $POSTGRES_USER -c \
  "CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD '$REPLICATION_PASSWORD';"
```

**Role đã tồn tại** — `REPLICATION_PASSWORD` trong `.env` của primary và standby không khớp. Đặt lại mật khẩu trên primary cho trùng với standby:

```bash
docker compose exec db psql -U $POSTGRES_USER -c \
  "ALTER ROLE replicator WITH PASSWORD '$REPLICATION_PASSWORD';"
```

Sau đó chạy lại `bash setup-ha.sh` trên standby.

---

## Xác Minh End-to-End

Sau khi cả hai vùng hoạt động:

1. **DB replication:** Tạo user trên dashboard Zone A → ngay lập tức hiển thị trên dashboard Zone B
2. **Config sync (auto):** Tạo và kích hoạt cấu hình trên Zone A → Zone B reload trong vòng 10 giây
3. **Config sync (manual):** Tạo và kích hoạt cấu hình trên Zone A → nhấn "Sync to Zone B" → Zone B reload
4. **TACACS failover:** Dừng backend Zone A → thiết bị mạng xác thực thành công qua Zone B trong 5 giây
5. **Alert deduplication:** Kích hoạt điều kiện alert → chỉ nhận một thông báo (scheduler tắt trên Zone B)
6. **LDAP override:** Zone B dùng `MAVIS_OVERRIDE_LDAP_HOSTS` — kiểm tra bằng `docker compose exec backend cat /app/tacacs_config/etc/tac_plus-ng.cfg | grep LDAP_HOSTS`
