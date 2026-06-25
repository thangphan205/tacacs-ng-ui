# Hướng Dẫn Triển Khai High Availability (HA)

Hướng dẫn này giải thích cách chạy hai phiên bản tacacs-ng-ui ở hai vùng khác nhau để thiết bị mạng luôn có TACACS+ server có thể kết nối được.

---

## Chọn Mô Hình Triển Khai

| | **Mô hình A — Độc lập** | **Mô hình B — Primary–Standby** |
|-|------------------------|----------------------------------|
| Database | Mỗi vùng có DB riêng | Zone B sao chép từ Zone A |
| Đồng bộ cấu hình | Thủ công (admin quản lý cả hai) | Tự động hoặc một thao tác |
| Độ phức tạp | Thấp | Trung bình |
| Failover | Thiết bị tự chuyển sang server kia | Nâng cấp standby bằng một lệnh |
| Phù hợp | Hai vùng phục vụ nhóm thiết bị khác nhau, hoặc cần cô lập hoàn toàn | Một nhóm admin, cấu hình đồng nhất giữa hai vùng |

Cả hai mô hình đều không cần thay đổi các triển khai hiện có — Mô hình A không cần thay đổi code.

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
PEER_BACKEND_URL=https://api-b.yourdomain.com   # URL API nội bộ của Zone B
INTERNAL_SYNC_TOKEN=<tạo bằng: openssl rand -hex 32>
```

Triển khai bình thường:

```bash
docker compose -f docker-compose.yml -f docker-compose.traefik.yml up -d
```

Bật PostgreSQL replication (chạy một lần sau khi Zone A hoạt động ổn định):

```bash
# Tạo replication role (load các biến môi trường từ .env trước để resolve $POSTGRES_USER)
export $(grep -v '^#' .env | xargs)
docker compose exec db psql -U $POSTGRES_USER -c \
  "CREATE ROLE replicator WITH REPLICATION LOGIN PASSWORD 'your-replication-password';"

# Cho phép IP Zone B kết nối để replication
docker compose exec db bash -c \
  "echo 'host replication replicator <ZONE_B_IP>/32 md5' >> \$PGDATA/pg_hba.conf"

# Reload cấu hình PostgreSQL (không cần restart)
docker compose kill -s HUP db
```

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
PEER_BACKEND_URL=https://api-a.yourdomain.com   # URL Zone A
INTERNAL_SYNC_TOKEN=<cùng giá trị với zone-a>
PRIMARY_DB_HOST=<ZONE_A_IP>
REPLICATION_PASSWORD=your-replication-password

# Trỏ Zone B đến LDAP server cục bộ (xem phần MAVIS bên dưới)
MAVIS_OVERRIDE_LDAP_HOSTS=ldaps://ldap-zone-b.yourdomain.com:636
```

Chạy script bootstrap standby (thực hiện pg_basebackup + khởi động tất cả service):

```bash
bash backend/scripts/setup-standby.sh
```

Script thực hiện:
1. Pull Docker images
2. Chạy `pg_basebackup` từ Zone A qua cổng PostgreSQL 5432 (không cần SSH)
3. Ghi cấu hình streaming replication (`standby.signal`, `primary_conninfo`)
4. Khởi động `docker compose up -d`
5. Xác minh replication đang hoạt động

**Kiểm tra replication:**

```bash
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

## Quy Trình Failover (Zone A gặp sự cố)

**Nâng cấp Zone B thành primary:**

```bash
# Trên server Zone B
docker compose exec db psql -U $POSTGRES_USER -c "SELECT pg_promote();"

# Cập nhật .env Zone B:
#   NODE_ROLE=primary
#   SCHEDULER_ENABLED=true

docker compose up -d backend
```

Zone B giờ nhận toàn bộ ghi. Thiết bị mạng đã trỏ sẵn đến Zone B nên xác thực TACACS tiếp tục không gián đoạn.

**Khi Zone A phục hồi:**

Gia nhập lại Zone A như standby mới:

```bash
# Trên server Zone A
# Cập nhật .env:
#   NODE_ROLE=standby
#   SCHEDULER_ENABLED=false
#   PRIMARY_DB_HOST=<ZONE_B_IP>

bash backend/scripts/setup-standby.sh
```

---

## Tham Chiếu Biến Môi Trường

Tất cả biến HA đều tùy chọn. Mặc định chạy như triển khai single-node bình thường.

| Biến | Mặc định | Mô tả |
|------|----------|-------|
| `NODE_ROLE` | `primary` | `primary` hoặc `standby`. Kiểm soát quyền ghi và scheduler. |
| `SCHEDULER_ENABLED` | `true` | Đặt `false` trên standby — tắt vòng lặp đánh giá alert, ML scoring, audit purge. |
| `SYNC_MODE` | `auto` | `auto` = daemon standby theo dõi DB và tự reload. `manual` = admin chủ động push. |
| `PEER_BACKEND_URL` | _(trống)_ | URL API nội bộ của vùng còn lại (ví dụ `https://api-b.yourdomain.com`). |
| `INTERNAL_SYNC_TOKEN` | _(trống)_ | Shared secret cho các lệnh gọi reload giữa node. Phải khớp trên cả hai vùng. Tạo bằng `openssl rand -hex 32`. |
| `PRIMARY_DB_HOST` | _(trống)_ | IP DB host của Zone A. Chỉ cần trên Zone B khi chạy `setup-standby.sh`. |
| `REPLICATION_PASSWORD` | _(trống)_ | Mật khẩu cho PostgreSQL role `replicator`. Chỉ cần trên Zone B. |
| `MAVIS_OVERRIDE_<KEY>` | _(trống)_ | Override bất kỳ MAVIS key nào theo vùng (ví dụ `MAVIS_OVERRIDE_LDAP_HOSTS`). |
| `SYNC_WATCHER_INTERVAL` | `10` | Giây giữa các lần kiểm tra thay đổi cấu hình (auto-sync watcher, chỉ Zone B). |

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
  "sync_mode": "manual",
  "scheduler_enabled": true,
  "peer_backend_url": "https://api-b.yourdomain.com",
  "peer_available": true
}
```

**Đẩy cấu hình thủ công đến standby (manual sync mode):**

```bash
curl -X POST -H "Authorization: Bearer <token>" \
  https://api-a.yourdomain.com/api/v1/sync/push-config
```

---

## Xác Minh End-to-End

Sau khi cả hai vùng hoạt động:

1. **DB replication:** Tạo user trên dashboard Zone A → ngay lập tức hiển thị trên dashboard Zone B
2. **Config sync (auto):** Tạo và kích hoạt cấu hình trên Zone A → Zone B reload trong vòng 10 giây
3. **Config sync (manual):** Tạo và kích hoạt cấu hình trên Zone A → nhấn "Sync to Zone B" → Zone B reload
4. **TACACS failover:** Dừng backend Zone A → thiết bị mạng xác thực thành công qua Zone B trong 5 giây
5. **Alert deduplication:** Kích hoạt điều kiện alert → chỉ nhận một thông báo (scheduler tắt trên Zone B)
6. **LDAP override:** Zone B dùng `MAVIS_OVERRIDE_LDAP_HOSTS` — kiểm tra bằng `docker compose exec backend cat /app/tacacs_config/etc/tac_plus-ng.cfg | grep LDAP_HOSTS`
