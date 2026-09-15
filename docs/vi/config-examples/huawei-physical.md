# Hướng Dẫn Tích Hợp TACACS+ Cho Switch Huawei Vật Lý (Campus S-Series / V200R022)

Tài liệu này hướng dẫn chi tiết cách tích hợp **switch Huawei vật lý** (dòng S5700 / S5720 / S5735 / S6700 chạy VRP V200R022) với hệ thống `tacacs-ng-ui`.

> [!NOTE]
> Switch Campus vật lý chạy VRP V200R022 có cú pháp lệnh khác so với switch ảo CloudEngine (CE12800 / eNSP). Xem phần [Điểm Khác Biệt Then Chốt](#1-diem-khac-biet-then-chot-switch-campus-vat-ly-vs-switch-ao-cloudengine) dưới đây để nắm rõ.

---

## 1. Điểm Khác Biệt Then Chốt: Switch Campus Vật Lý vs. Switch Ảo CloudEngine

| Tham số / Tính năng | Switch Campus Vật Lý (Dòng S / V200R022) | Switch Ảo (CloudEngine CE12800 / eNSP) |
|---|---|---|
| **Cú pháp lệnh HWTACACS** | Có dấu gạch nối: `hwtacacs-server template <tên>`, `hwtacacs-server authentication ...` | Dùng dấu cách: `hwtacacs server template <tên>`, `hwtacacs server authentication ...` |
| **Gán Template vào Domain** | `hwtacacs-server <tên_template>` dưới `aaa -> domain` | `hwtacacs server <tên_template>` dưới `aaa -> domain` |
| **Bật HWTACACS** | `hwtacacs enable` (trên switch vật lý mặc định thường là `undo hwtacacs enable`) | `hwtacacs enable` |
| **Bỏ Domain Suffix** | `undo hwtacacs-server user-name domain-included` | `hwtacacs server user-name domain-excluded` |
| **Routing Quản trị** | Thường chạy In-band qua VLAN (`Vlanif101`) trong bảng định tuyến Global | Chạy qua Out-of-band `MEth0/0/0` trong VRF (`vpn-instance __MGMT_VPN__`) |
| **Ghi log lệnh (Recording)** | Khai báo `recording-scheme <tên>` **và** kích hoạt bằng `cmd recording-scheme <tên>` | Khai báo trực tiếp `recording-scheme` trong `aaa` |
| **Domain Quản trị Mặc định** | Cần lệnh `domain default_admin admin` ở system-view để phiên SSH không kèm `@domain` tự vào `default_admin` | `domain default_admin` |
| **Ủy quyền SSH (BẮT BUỘC)** | `ssh authorization-type default aaa` để cho phép user TACACS+ đăng nhập SSH mà không cần tạo trước `ssh user` cục bộ | `ssh authorization-type default aaa` |
| **Đảm bảo phiên Accounting** | `accounting start-fail online` tránh ngắt kết nối user nếu gói tin accounting bị chậm | Thường để mặc định |

---

## 2. Cấu Hình Phía Server (tacacs-ng-ui)

### A. Thêm Host Thiết Bị
Truy cập **Hosts** -> **Add Host**:
- **Host Name**: `Huawei` (hoặc tên switch của bạn)
- **IP Address**: `192.168.1.2` (IP nguồn cổng quản trị của switch, ví dụ `Vlanif101`)
- **Shared Secret Key**: `<TACACS_SECRET_KEY>` (ví dụ `Netconsole123`)

### B. Profiles, Groups & Users Sẵn Có
Hệ thống `tacacs-ng-ui` đã có sẵn các cấu hình chuẩn cho Huawei VRP:
1. **Profiles**:
   - `tacacs_super_user_profile`: Trả về quyền `priv-lvl = 15` cho service `shell` và `h3c_shell`.
   - `tacacs_read_only_profile`: Trả về quyền `priv-lvl = 1` cho service `shell` và `h3c_shell`.
2. **Groups**: `tacacs_super_user` (quyền 15) và `tacacs_read_only` (quyền 1).
3. **Users**: `user_admin` (thuộc group `tacacs_super_user`) và `user_read_only` (thuộc group `tacacs_read_only`).
4. **Ruleset**: `default_ruleset` cho phép cả 2 group với profile tương ứng.

> [!IMPORTANT]
> Nhớ vào **TACACS Configs** -> **Generate Config** -> **Activate** sau khi lưu thay đổi để áp dụng cấu hình xuống daemon.

---

## 3. Cấu Hình Phía Thiết Bị (CLI Switch Huawei Vật Lý)

Thực hiện các lệnh sau trên switch ở chế độ **system-view**:

### Bước 1: Kích hoạt HWTACACS toàn cục
```text
system-view
hwtacacs enable
```

### Bước 2: Tạo Template HWTACACS Server
```text
hwtacacs-server template tacacs_netadmin
 # IP server TACACS+ (Thay bằng IP server tacacs-ng-ui của bạn)
 hwtacacs-server authentication <IP_TACACS_SERVER>
 hwtacacs-server authorization <IP_TACACS_SERVER>
 hwtacacs-server accounting <IP_TACACS_SERVER>
 
 # IP nguồn cổng quản trị (theo cấu hình hiện tại là Vlanif101: 192.168.1.2)
 hwtacacs-server source-ip 192.168.1.2
 
 # Shared key khớp với cấu hình Host trên tacacs-ng-ui
 hwtacacs-server shared-key simple <TACACS_SECRET_KEY>
 
 # Bỏ hậu tố @domain khi gửi username sang TACACS+
 undo hwtacacs-server user-name domain-included
quit
```

### Bước 3: Cấu hình AAA Scheme & Ghi nhận câu lệnh
Cấu hình cơ chế dự phòng `local` để không bao giờ bị khóa khỏi thiết bị nếu mất kết nối tới TACACS+:

```text
aaa
 # 1. Authentication Scheme (Ưu tiên TACACS+, fallback về Local)
 authentication-scheme tac_auth
  authentication-mode hwtacacs local
 quit

 # 2. Authorization Scheme (Ưu tiên TACACS+, fallback về Local)
 authorization-scheme tac_author
  authorization-mode hwtacacs local
 quit

 # 3. Accounting Scheme (Gửi thông tin phiên đăng nhập tới TACACS+)
 accounting-scheme tac_acct
  accounting-mode hwtacacs
  accounting start-fail online
 quit

 # 4. Command Recording Scheme (Ghi log câu lệnh thực thi lên TACACS+)
 recording-scheme tac_record
  recording-mode hwtacacs tacacs_netadmin
 quit
 cmd recording-scheme tac_record
quit
```

### Bước 4: Gán vào Domain `default_admin`
```text
aaa
 domain default_admin
  authentication-scheme tac_auth
  authorization-scheme tac_author
  accounting-scheme tac_acct
  hwtacacs-server tacacs_netadmin
 quit
quit

# Chỉ định default_admin là domain quản trị mặc định cho SSH / Console
domain default_admin admin
```

### Bước 5: Cho phép SSH xác thực động qua AAA
Lệnh này cực kỳ quan trọng trên switch Huawei vật lý để cho phép các user TACACS+ đăng nhập SSH mà không cần phải khai báo thủ công `ssh user`:

```text
ssh authorization-type default aaa
```

### Bước 6: Bảo vệ đường truyền VTY & Console
```text
# Cấu hình đường VTY sử dụng AAA và chỉ nhận SSH
user-interface vty 0 4
 authentication-mode aaa
 idle-timeout 15 0
 protocol inbound ssh

# Kiểm tra Console duy trì AAA (đã có fallback local)
user-interface con 0
 authentication-mode aaa
```

---

## 4. Toàn Bộ Đoạn Cấu Hình Sẵn Sàng Copy/Paste

```text
system-view
hwtacacs enable
#
hwtacacs-server template tacacs_netadmin
 hwtacacs-server authentication <IP_TACACS_SERVER>
 hwtacacs-server authorization <IP_TACACS_SERVER>
 hwtacacs-server accounting <IP_TACACS_SERVER>
 hwtacacs-server source-ip 192.168.1.2
 hwtacacs-server shared-key simple <TACACS_SECRET_KEY>
 undo hwtacacs-server user-name domain-included
#
aaa
 authentication-scheme tac_auth
  authentication-mode hwtacacs local
 #
 authorization-scheme tac_author
  authorization-mode hwtacacs local
 #
 accounting-scheme tac_acct
  accounting-mode hwtacacs
  accounting start-fail online
 #
 recording-scheme tac_record
  recording-mode hwtacacs tacacs_netadmin
 cmd recording-scheme tac_record
 #
 domain default_admin
  authentication-scheme tac_auth
  authorization-scheme tac_author
  accounting-scheme tac_acct
  hwtacacs-server tacacs_netadmin
#
domain default_admin admin
ssh authorization-type default aaa
#
user-interface vty 0 4
 authentication-mode aaa
 idle-timeout 15 0
 protocol inbound ssh
#
return
save
```

---

## 5. Kiểm Tra & Chẩn Đoán Sự Cố

### Kiểm tra xác thực AAA trực tiếp từ CLI
Từ user-view (`<Huawei>`), bạn có thể test tài khoản trước khi thoát session hiện tại:

```text
test-aaa <username> <password> hwtacacs-template tacacs_netadmin
```
- **Thành công**: `Info: Account test succeeded.`
- **Thất bại**: Báo sai mật khẩu, sai secret key hoặc kết nối port 49 TCP giữa `192.168.1.2` và `<IP_TACACS_SERVER>` bị chặn.

### Kiểm tra trạng thái kết nối HWTACACS
```text
display hwtacacs-server template tacacs_netadmin
```
Xem trạng thái server có ở mức `active` và các gói tin Request/Reply có tăng lên hay không.

### Xem các user đang đăng nhập trực tuyến
```text
display aaa online-user
```
User đăng nhập thành công qua TACACS+ sẽ hiển thị `Domain: default_admin` và `Authen-Mode: HWTACACS`.
