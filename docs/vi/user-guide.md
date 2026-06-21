# Hướng Dẫn Sử Dụng tacacs-ng-ui

---

> ### ⚠️ QUAN TRỌNG — ĐỌC TRƯỚC
>
> **Bất cứ khi nào bạn thay đổi cấu hình TACACS (người dùng, nhóm, thiết bị, profile, ruleset, cài đặt), bạn PHẢI vào TACACS Configs → Generate Config → đánh dấu config mới là Active.**
>
> Các thay đổi sẽ KHÔNG có hiệu lực trên TACACS+ server cho đến khi config được tạo lại và kích hoạt.

---

## Mục Lục

1. [Bắt Đầu](#bắt-đầu)
2. [Khái Niệm Cơ Bản](#khái-niệm-cơ-bản)
3. [Thiết Lập Lần Đầu](#thiết-lập-lần-đầu)
4. [Quản Lý Người Dùng & Nhóm TACACS+](#quản-lý-người-dùng--nhóm-tacacs)
5. [Cấu Hình Thiết Bị Mạng (Hosts)](#cấu-hình-thiết-bị-mạng-hosts)
6. [Kiểm Soát Truy Cập: Profiles & Rulesets](#kiểm-soát-truy-cập-profiles--rulesets)
7. [Cài Đặt Server](#cài-đặt-server)
8. [Tạo và Kích Hoạt File Config](#tạo-và-kích-hoạt-file-config)
9. [Tổng Quan Dashboard](#tổng-quan-dashboard)
10. [Xem Sự Kiện Log TACACS](#xem-sự-kiện-log-tacacs)
11. [Tích Hợp SIEM](#tích-hợp-siem)
12. [Giám Sát & Thống Kê](#giám-sát--thống-kê)
13. [Nhật Ký Kiểm Tra (Audit Logs)](#nhật-ký-kiểm-tra-audit-logs)
14. [Quản Lý Người Dùng Ứng Dụng](#quản-lý-người-dùng-ứng-dụng)
15. [Nâng Cao: MAVIS Backend](#nâng-cao-mavis-backend)
16. [Nâng Cao: Tùy Chọn Cấu Hình Tùy Chỉnh](#nâng-cao-tùy-chọn-cấu-hình-tùy-chỉnh)
17. [Xử Lý Sự Cố](#xử-lý-sự-cố)

---

## Bắt Đầu

### Đăng Nhập

Truy cập URL dashboard của bạn (ví dụ: `http://localhost:5173` hoặc domain đã cấu hình).

![Dashboard Login](../../img/login.png)

Các phương thức đăng nhập:
- **Email + Mật khẩu** — phương thức mặc định
- **Đăng nhập với Google** — yêu cầu cấu hình Google OAuth trong `.env`
- **Đăng nhập với Keycloak** — yêu cầu cấu hình Keycloak OIDC
- **Passkeys** — đăng nhập không mật khẩu qua WebAuthn (sinh trắc học/hardware key)

Thông tin đăng nhập admin mặc định được cấu hình qua `FIRST_SUPERUSER` và `FIRST_SUPERUSER_PASSWORD` trong file `.env`.

---

## Khái Niệm Cơ Bản

Hiểu cách tacacs-ng-ui ánh xạ tới cấu hình TACACS+:

| Khái niệm | Chức năng |
|-----------|-----------|
| **TACACS User** | Người dùng thiết bị mạng (người đăng nhập vào router/switch) |
| **TACACS Group** | Nhóm mà người dùng thuộc về; chính sách được áp dụng theo nhóm |
| **Host** | Thiết bị mạng (router, switch, firewall) xác thực với TACACS+ server |
| **Profile** | Định nghĩa các thuộc tính (service, privilege level) trả về trong phản hồi authorization |
| **Ruleset** | Quy tắc truy cập có điều kiện — cho phép hoặc từ chối dựa trên user/group/service/command |
| **TACACS Config** | File cấu hình được tạo ra và nạp vào daemon `tac_plus-ng` |
| **MAVIS** | Backend xác thực bên ngoài (ví dụ: LDAP/AD) thay cho mật khẩu cục bộ |

> **Nhắc nhở:** Sau khi chỉnh sửa bất kỳ mục nào ở trên, luôn phải tạo lại và kích hoạt config. Xem [Tạo và Kích Hoạt File Config](#tạo-và-kích-hoạt-file-config).

---

## Thiết Lập Lần Đầu

Thực hiện theo thứ tự này khi cấu hình từ đầu:

### 1. Cấu Hình Cài Đặt Server

Vào **TACACS-NG Settings** và thiết lập:
- Địa chỉ IPv4 và cổng (mặc định: `0.0.0.0`, cổng `49`)
- Đường dẫn file log cho authentication, authorization và accounting
- Backend xác thực (`local`, `mavis`, `pap`, v.v.)

### 2. Tạo Nhóm TACACS

Vào **TACACS Groups** → **Add Group**.
- Ví dụ nhóm: `network-admins`, `read-only-ops`

### 3. Tạo Người Dùng TACACS

Vào **TACACS Users** → **Add User**.
- Thiết lập `username`, `password`, `password_type` (`pap`), và gán vào nhóm.

### 4. Tạo Profiles (Thuộc Tính Authorization)

Vào **Profiles** → **Add Profile**.
- Đặt `action` là `permit` hoặc `deny`.
- Thêm **Profile Scripts** để trả về các cặp key-value cho thiết bị (ví dụ: `service=exec`, `priv-lvl=15`).

### 5. Tạo Rulesets (Kiểm Soát Truy Cập)

Vào **Rulesets** → **Add Ruleset**.
- Định nghĩa các quy tắc có điều kiện khớp với user/group/service và ánh xạ tới profiles.
- Thêm **Ruleset Scripts** với các điều kiện (ví dụ: `$user == "admin"`, `$nas == "192.168.1.1"`).

### 6. Thêm Thiết Bị Mạng (Hosts)

Vào **Hosts** → **Add Host**.
- Đặt địa chỉ IP thiết bị và `secret_key` (phải khớp với cấu hình trên thiết bị).

### 7. Tạo và Kích Hoạt Config

> **⚠️ Bước này bắt buộc sau MỖI lần thay đổi cấu hình.**

Vào **TACACS Configs** → **Generate Config** → đánh dấu config mới là **Active**.

![TACACS Config Generator](../../img/dashboard-tacacs-config.png)

### 8. Cấu Hình Thiết Bị Mạng

Trỏ các router/switch tới TACACS+ server. Xem [ví dụ cấu hình thiết bị](#cấu-hình-phía-thiết-bị).

---

## Quản Lý Người Dùng & Nhóm TACACS+

### Nhóm TACACS

**Đường dẫn:** Sidebar → TACACS Groups

![TACACS Groups](../../img/tacacs-groups.png)

| Trường | Mô tả |
|--------|-------|
| `group_name` | Tên duy nhất của nhóm (ví dụ: `network-admins`) |
| `description` | Mô tả tùy chọn |

Nhóm được tham chiếu trong TACACS Users và Rulesets để áp dụng chính sách cho nhiều người dùng cùng lúc.

### Người Dùng TACACS

**Đường dẫn:** Sidebar → TACACS Users

![TACACS Users](../../img/tacacs-users.png)

| Trường | Mô tả |
|--------|-------|
| `username` | Tên đăng nhập dùng trên thiết bị mạng |
| `password` | Mật khẩu người dùng (lưu dưới dạng hash) |
| `password_type` | Giao thức trao đổi mật khẩu — thường dùng `pap` |
| `member` | Nhóm mà người dùng này thuộc về |
| `description` | Mô tả tùy chọn |

**Lưu ý:**
- `password_type: pap` là phổ biến nhất. Dùng `login` cho ASCII auth.
- Người dùng kế thừa chính sách từ nhóm của họ qua Rulesets.

> **Sau khi thêm/sửa người dùng:** tạo lại và kích hoạt config.

---

## Cấu Hình Thiết Bị Mạng (Hosts)

**Đường dẫn:** Sidebar → Hosts

![Hosts](../../img/hosts.png)

| Trường | Mô tả |
|--------|-------|
| `name` | Định danh thiết bị (ví dụ: `core-switch-01`) |
| `ipv4_address` | Địa chỉ IP thiết bị (dùng để khớp với TACACS request) |
| `ipv6_address` | Địa chỉ IPv6 tùy chọn |
| `secret_key` | Khóa bí mật dùng chung — phải khớp với cấu hình TACACS key trên thiết bị |
| `parent` | Host cha tùy chọn để kế thừa cài đặt |
| `welcome_banner` | Thông báo gửi tới người dùng khi đăng nhập thành công |
| `reject_banner` | Thông báo gửi khi bị từ chối truy cập |
| `motd_banner` | Thông báo ngày (Message of the Day) hiển thị sau đăng nhập |
| `failed_authentication_banner` | Thông báo gửi khi xác thực thất bại |

> **Sau khi thêm/sửa host:** tạo lại và kích hoạt config.

### Cấu Hình Phía Thiết Bị

**Cisco IOS / IOS-XE:**
```bash
! 1. Bật AAA trước (phải đặt trước khối tacacs server)
aaa new-model

! 2. Định nghĩa TACACS+ server
tacacs server MY-TACACS
  address ipv4 <TACACS_SERVER_IP>
  key <secret_key>
  exit

! 3. Tạo nhóm server có tên (giúp dễ dàng thêm server dự phòng)
aaa group server tacacs+ TACACS-GROUP
  server name MY-TACACS
  exit

! 4. Xác thực, Phân quyền, Ghi nhật ký
aaa authentication login default group TACACS-GROUP local
aaa authorization exec default group TACACS-GROUP local
aaa accounting exec default start-stop group TACACS-GROUP
aaa accounting commands 15 default start-stop group TACACS-GROUP

! 5. Áp dụng cho VTY lines (SSH/Telnet) — bắt buộc, nếu không TACACS sẽ không được dùng
line vty 0 4
  login authentication default
  exit
```

**Juniper JunOS:**
```bash
# 1. Định nghĩa class người dùng cục bộ mà TACACS users sẽ được ánh xạ vào
set system login class tacacs-admin permissions all
set system login class tacacs-read permissions [ view view-configuration ]
set system login user user_demo uid 9999 class tacacs-admin

# 2. Cấu hình TACACS+ server (source-address = IP interface quản lý)
set system tacplus-server <TACACS_SERVER_IP> port 49 secret <secret_key>
set system tacplus-server <TACACS_SERVER_IP> source-address <DEVICE_MGMT_IP>

# 3. Thứ tự xác thực (TACACS trước, fallback về local password)
set system authentication-order tacplus
set system authentication-order password

# 4. Bật accounting
set system accounting events login
set system accounting events interactive-commands
set system accounting destination tacplus server <TACACS_SERVER_IP> secret <secret_key>
set system accounting destination tacplus server <TACACS_SERVER_IP> source-address <DEVICE_MGMT_IP>
```

**Arista EOS:**
```bash
# 1. Định nghĩa TACACS+ server (key 7 = mã hóa; key 0 = plaintext, tránh dùng trong production)
tacacs-server host <TACACS_SERVER_IP> key 7 <encrypted_secret_key>

# 2. Tạo nhóm server có tên
aaa group server tacacs+ TACACS-GROUP
   server <TACACS_SERVER_IP>
!

# 3. Xác thực, Phân quyền, Ghi nhật ký
aaa authentication login default group TACACS-GROUP local
aaa authorization exec default group TACACS-GROUP local
aaa authorization commands all default group TACACS-GROUP local
aaa accounting exec default start-stop group TACACS-GROUP

# 4. Nguồn traffic TACACS từ interface quản lý
ip tacacs source-interface Management0
```

---

## Kiểm Soát Truy Cập: Profiles & Rulesets

### Profiles

**Đường dẫn:** Sidebar → Profiles

![Profiles](../../img/profiles.png)

Profiles định nghĩa **phản hồi authorization** gửi lại cho thiết bị khi truy cập được cấp phép.

| Trường | Mô tả |
|--------|-------|
| `name` | Định danh profile |
| `action` | `permit` hoặc `deny` |
| `description` | Mô tả tùy chọn |

#### Profile Scripts

Thêm các cặp thuộc tính-giá trị trả về cho thiết bị trong phản hồi authorization.

**Đường dẫn:** Profiles → chọn profile → Profile Scripts

| Trường | Mô tả |
|--------|-------|
| `condition` | Biểu thức điều kiện tùy chọn (ví dụ: `$user == "admin"`) |
| `key` | Tên thuộc tính (ví dụ: `priv-lvl`, `service`) |
| `value` | Giá trị thuộc tính (ví dụ: `15`, `exec`) |
| `action` | `set`, `add`, hoặc `optional` |

**Ví dụ — Cấp quyền đầy đủ cho admin:**
```
key: service     value: exec
key: priv-lvl    value: 15
```

**Ví dụ — Quyền chỉ đọc:**
```
key: service     value: exec
key: priv-lvl    value: 1
```

### Rulesets

**Đường dẫn:** Sidebar → Rulesets

![Rulesets](../../img/rulesets.png)

Rulesets định nghĩa **người dùng nào được profile nào** dựa trên điều kiện.

| Trường | Mô tả |
|--------|-------|
| `name` | Định danh ruleset |
| `enabled` | `yes` hoặc `no` — bật/tắt mà không cần xóa |
| `action` | Hành động mặc định nếu không có script nào khớp: `permit` hoặc `deny` |
| `description` | Mô tả tùy chọn |

#### Ruleset Scripts

Thêm quy tắc có điều kiện trong ruleset.

**Biến điều kiện thường dùng:**
- `$user` — Tên người dùng TACACS
- `$group` — Nhóm của người dùng
- `$nas` — Địa chỉ IP của thiết bị mạng (NAS)
- `$service` — Dịch vụ yêu cầu (ví dụ: `shell`, `exec`)
- `$protocol` — Giao thức (ví dụ: `telnet`, `ssh`)

**Ví dụ logic ruleset:**
```
condition: $group == "network-admins"   action: permit   key: priv-lvl   value: 15
condition: $group == "read-only"        action: permit   key: priv-lvl   value: 1
default action: deny
```

> **Sau khi thêm/sửa profiles hoặc rulesets:** tạo lại và kích hoạt config.

---

## Cài Đặt Server

**Đường dẫn:** Sidebar → TACACS-NG Settings

![TACACS-NG Settings](../../img/tacacs-ng-settings.png)

| Trường | Mô tả |
|--------|-------|
| `ipv4_enabled` | Bật listener IPv4 |
| `ipv4_address` | Địa chỉ bind (dùng `0.0.0.0` để lắng nghe trên tất cả interface) |
| `ipv4_port` | Cổng TACACS+ (mặc định: `49`) |
| `ipv6_enabled` | Bật listener IPv6 |
| `instances_min` / `instances_max` | Số tiến trình server tối thiểu/tối đa |
| `background` | Chạy server ở nền (`yes`/`no`) |
| `*_logfile_destination` | Đường dẫn file log (hỗ trợ `%Y/%m/%d` để phân chia theo ngày) |
| `login_backend` | Backend xác thực đăng nhập (`local`, `mavis`) |
| `pap_backend` | Backend cho PAP auth |

> **Sau khi thay đổi cài đặt server:** tạo lại và kích hoạt config.

---

## Tạo và Kích Hoạt File Config

**Đường dẫn:** Sidebar → TACACS Configs

> ### ⚠️ BẮT BUỘC SAU MỖI THAY ĐỔI
>
> Các thay đổi đối với users, groups, hosts, profiles, rulesets, MAVIS, hoặc cài đặt server sẽ **không có hiệu lực** trên TACACS+ server cho đến khi bạn tạo lại và kích hoạt config.

### Quy trình: Generate → Preview → Activate

**Bước 1 — Generate Config**: Nhấn **Generate Config** để tạo config `tac_plus-ng` đầy đủ từ tất cả cài đặt hiện tại. Hộp thoại sẽ hỏi tên file và mô tả; mặc định điền sẵn theo thời gian hiện tại.

**Bước 2 — Preview Config**: Nhấn **Preview Config** để xem trước nội dung config mà không lưu lại. Hữu ích để kiểm tra thay đổi trước khi xác nhận.

**Bước 3 — Activate**: Trong bảng danh sách config, mở menu Actions của snapshot cần dùng và chọn **Activate**. Hàng đang active được tô nền xanh với badge **Active**.

**Nút Active Config**: Nhấn để xem file config đang chạy với syntax highlighting.

![TACACS Config](../../img/tacacs_config.png)

Sau khi kích hoạt, daemon `tac_plus-ng` nhận cấu hình mới. Trong triển khai Docker, file config được ghi vào volume `/app/tacacs_config/` dùng chung với container TACACS+ server.

---

## Tổng Quan Dashboard

**Đường dẫn:** Sidebar → Dashboard

Dashboard cung cấp thông tin tổng hợp về môi trường TACACS+ qua bốn phần.

**Tóm Tắt Log Hôm Nay**: Ba thẻ thống kê lấy trực tiếp từ file log TACACS+: Authentication (thành công/thất bại), Authorization (cho phép/từ chối), Accounting (bắt đầu/kết thúc). Nhấn vào thẻ để chuyển đến trang Log Events.

**Tổng Quan Config**: Năm thẻ hiển thị số lượng thực thể hiện tại — Hosts, TACACS Users, TACACS Groups, Profiles, Rulesets. Nhấn để điều hướng đến trang tương ứng.

**Hoạt Động Người Dùng Gần Đây**: Bảng 10 bản ghi audit log gần nhất. Nhấn **Xem tất cả →** để mở trang Audit Logs.

**Top 5 & Xu Hướng AAA**: Bốn biểu đồ tròn (Top 5 Source IPs, NAS IPs, Auth Users, Authz Users) và biểu đồ xu hướng đường thẳng 6 series. Bộ lọc: **7 Ngày Qua** / **30 Ngày Qua** / **Khoảng Thời Gian** (nhập ngày tùy chỉnh). Mặc định là 7 Ngày Qua.

---

## Xem Sự Kiện Log TACACS

**Đường dẫn:** Sidebar → TACACS Logs → tab Events

Duyệt và tìm kiếm các sự kiện TACACS+ được phân tích từ file log thô.

| Bộ lọc | Tùy chọn |
|--------|----------|
| Ngày | Chọn ngày cụ thể (mặc định: hôm nay) |
| Loại | All / Authentication / Authorization / Accounting |
| Kết quả | All / Success / Failed / Permit / Deny / Start / Stop |
| Tên người dùng | Tìm kiếm văn bản tự do |

Kết quả phân trang. Mỗi sự kiện hiển thị: Thời gian, Loại (badge màu), Kết quả (badge màu), Tên người dùng, NAS IP, Thông điệp.

---

## Tích Hợp SIEM

tacacs-ng-ui có thể chuyển tiếp sự kiện log TACACS+ theo thời gian thực đến các nền tảng bảo mật bên ngoài.

**Cấu hình trong `.env`:**

```bash
SIEM_FORWARD_TACACS_EVENTS=true

# HTTP Webhook (định dạng Splunk HEC)
SIEM_WEBHOOK_URL=https://splunk.example.com:8088/services/collector/event
SIEM_WEBHOOK_TOKEN=your-hec-token

# Syslog (UDP hoặc TCP)
SIEM_SYSLOG_HOST=syslog.example.com
SIEM_SYSLOG_PORT=514
SIEM_SYSLOG_PROTOCOL=udp
```

Sự kiện được gửi bất đồng bộ — xác thực TACACS+ không bị ảnh hưởng nếu endpoint SIEM không khả dụng.

---

## Giám Sát & Thống Kê

### Thống Kê AAA (Hôm nay)

**Đường dẫn:** Sidebar → AAA Statistics

![AAA Statistics](../../img/aaa-statistics.png)

Hiển thị tổng số ngày hôm nay:
- Số lần xác thực thành công/thất bại
- Số quyết định authorization cho phép/từ chối
- Sự kiện accounting start/stop
- Biểu đồ xu hướng 7 ngày

### Thống Kê Theo Khoảng Thời Gian

**Đường dẫn:** Sidebar → AAA Statistics Range — chọn khoảng thời gian tùy chỉnh.

### Thống Kê Xác Thực / Authorization / Accounting

- **Authentication Statistics** — Phân tích theo người dùng, thiết bị (thành công/thất bại)
- **Authorization Statistics** — Phân tích quyết định cho phép/từ chối theo người dùng
- **Accounting Statistics** — Thống kê phiên làm việc theo người dùng
- **TACACS Statistics** — Thống kê hiệu suất toàn server

---

## Nhật Ký Kiểm Tra (Audit Logs)

**Đường dẫn:** Sidebar → Audit Logs

![Audit Logs](../../img/audit-logs.png)

Mọi thay đổi cấu hình qua UI đều được ghi lại:

| Trường | Mô tả |
|--------|-------|
| `action` | `create`, `update`, `delete` |
| `entity_type` | Đối tượng bị thay đổi (ví dụ: `TacacsUser`, `Host`) |
| `user_email` | Người dùng dashboard thực hiện thay đổi |
| `ip_address` | Địa chỉ IP của trình duyệt người dùng |
| `old_values` / `new_values` | Snapshot trước/sau thay đổi |
| `timestamp` | Thời điểm thay đổi |

---

## Quản Lý Người Dùng Ứng Dụng

Đây là người dùng đăng nhập vào **dashboard** (không phải người dùng TACACS thiết bị).

**Đường dẫn:** Sidebar → Admin → Users Management (chỉ superuser)

![Users Management](../../img/users-management.png)

| Trường | Mô tả |
|--------|-------|
| `email` | Email đăng nhập |
| `is_active` | Kích hoạt/vô hiệu hóa tài khoản |
| `is_superuser` | Cấp quyền quản trị đầy đủ |
| `password_login_disabled` | Bắt buộc dùng OAuth/Passkey (vô hiệu hóa mật khẩu) |

### Auth Providers

**Đường dẫn:** Sidebar → Admin → Auth Providers

![Auth Providers](../../img/auth-providers.png)

| Provider | Cấu hình |
|----------|----------|
| `google` | Cần `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` trong `.env` |
| `keycloak` | Cần URL Keycloak server, client ID và client secret |
| `passkeys` | WebAuthn — không cần cấu hình thêm; người dùng đăng ký từ trang Settings |

---

## Nâng Cao: MAVIS Backend

**Đường dẫn:** Sidebar → Mavises

![Mavises](../../img/mavises.png)

MAVIS cho phép `tac_plus-ng` ủy quyền xác thực cho hệ thống bên ngoài (LDAP, Active Directory, v.v.).

Trường hợp sử dụng điển hình: xác thực người dùng TACACS với Active Directory qua module LDAP MAVIS thay vì mật khẩu cục bộ.

Dùng **Preview** để xem khối config MAVIS sẽ được tạo.

> **Sau khi thay đổi MAVIS:** tạo lại và kích hoạt config.

---

## Nâng Cao: Tùy Chọn Cấu Hình Tùy Chỉnh

**Đường dẫn:** Sidebar → Configuration Options

![Configuration Options](../../img/configuration-options.png)

Chèn các khối cấu hình `tac_plus-ng` thô không được UI hỗ trợ.

| Trường | Mô tả |
|--------|-------|
| `name` | Nhãn cho khối config này |
| `config_option` | Văn bản cấu hình thô (được nối vào cuối config được tạo) |
| `description` | Mô tả tùy chọn |

> **Sau khi thêm tùy chọn tùy chỉnh:** tạo lại và kích hoạt config.

---

## Xử Lý Sự Cố

| Triệu chứng | Kiểm tra |
|-------------|----------|
| Thiết bị không xác thực được | Kiểm tra `secret_key` khớp trên cả Host lẫn cấu hình thiết bị; xác nhận đã tạo lại và kích hoạt config |
| Thay đổi không có hiệu lực | **Tạo lại và kích hoạt config** — đây là nguyên nhân phổ biến nhất |
| Xác thực thành công nhưng không vào được shell | Đảm bảo profile trả về `service=exec` và thuộc tính `priv-lvl` |
| Người dùng không áp dụng được chính sách nhóm | Kiểm tra trường `member` của người dùng khớp chính xác tên nhóm |
| Không có log | Kiểm tra đường dẫn `accounting_logfile_destination` và quyền thư mục |
| Lỗi 401/403 trên dashboard | Token hết hạn — đăng xuất và đăng nhập lại |
| Lỗi cú pháp config | Xem TACACS Logs để biết thông báo lỗi từ `tac_plus-ng` |

---

## Quy Trình Nhanh

```
1. Server Settings        → đặt IP, cổng, đường dẫn log
2. TACACS Groups          → tạo nhóm (ví dụ: admins, read-only)
3. TACACS Users           → tạo người dùng, gán vào nhóm
4. Profiles               → định nghĩa phản hồi auth (priv-lvl, service)
5. Profile Scripts        → thêm cặp key-value vào profile
6. Rulesets               → ánh xạ user/group tới profile theo điều kiện
7. Hosts                  → thêm thiết bị với IP và secret key
8. ⚠️  TACACS Configs     → TẠO CONFIG → đánh dấu ACTIVE  ← BẮT BUỘC SAU MỖI THAY ĐỔI
9. Cấu hình thiết bị      → trỏ thiết bị tới TACACS+ server
10. Giám sát              → dùng Statistics và Logs để kiểm tra hoạt động
```

---

## Liên Kết Hữu Ích

- TACACS+ Server: [tac_plus-ng](https://github.com/MarcJHuber/event-driven-servers)
- Tài liệu API: `http://<your-host>:8000/docs`
- Hướng dẫn triển khai: [deployment.md](./deployment.md)
- Cộng đồng: [Telegram](https://t.me/+v1eAXg-BhotlODY1) | [Reddit](https://www.reddit.com/r/tacacs_ng_ui/)
