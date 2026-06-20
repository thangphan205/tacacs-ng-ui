# Hướng Dẫn Tích Hợp TACACS+ Cho Thiết Bị Juniper Junos

Tài liệu này hướng dẫn chi tiết cách tích hợp thiết bị Juniper chạy hệ điều hành Junos OS với `tacacs-ng-ui` server, bao gồm cấu hình phía server và các câu lệnh CLI trên thiết bị.

---

## 1. Cấu Hình Phía TACACS+ Server (tacacs-ng-ui)

Để cấu hình `tacacs-ng-ui` khớp với cấu hình server thực tế của bạn, hãy định nghĩa các thành phần sau trong dashboard.

> [!NOTE]
> Các profile, group, user và ruleset dưới đây đã được tạo sẵn (pre-seeded) bởi `init_db` trong lần khởi chạy đầu tiên. Bạn không cần tạo thủ công trừ khi đã xóa chúng.

### A. Profiles
Các profile sau đã được tạo sẵn trong mục **Profiles**:

1. **`tacacs_super_user_profile` (Level 15 — full admin)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 15`

2. **`tacacs_read_only_profile` (Level 1 — chỉ đọc)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 1`

### B. Groups & Users
Nhóm và người dùng tạo sẵn:

#### Groups (**TACACS Groups**)
- **`tacacs_super_user`** — Quyền quản trị viên đầy đủ (level 15).
- **`tacacs_read_only`** Quyền người vận hành chỉ đọc (level 1).

#### Users (**TACACS Users**)
- **`user_admin`**
  - **Password Type**: `crypt`, mật khẩu mặc định: `change_this`
  - **Group**: `tacacs_super_user`
- **`user_read_only`**
  - **Password Type**: `crypt`, mật khẩu mặc định: `change_this`
  - **Group**: `tacacs_read_only`

> [!WARNING]
> Thay đổi mật khẩu cho `user_admin` và `user_read_only` ngay sau lần đăng nhập đầu tiên.

### C. Rulesets
Ruleset tạo sẵn trong mục **Rulesets**:

- **Ruleset Name**: `default_ruleset`
- **Ruleset Scripts**:
  - **Quy tắc Admin**: Condition: `if`, Key: `group`, Value: `tacacs_super_user` → Action: `permit`, Profile: `tacacs_super_user_profile`
  - **Quy tắc Chỉ đọc**: Condition: `if`, Key: `group`, Value: `tacacs_read_only` → Action: `permit`, Profile: `tacacs_read_only_profile`

> [!IMPORTANT]
> Nhớ truy cập mục **TACACS Configs** → **Generate Config** → **Activate** cấu hình để các thay đổi có hiệu lực trên daemon.

---

## 2. Cấu Hình Phía Thiết Bị (Juniper Junos)

Áp dụng các câu lệnh cấu hình sau trên thiết bị Juniper để hoàn tất tích hợp TACACS+.

> [!WARNING]
> Các địa chỉ IP và shared secret dưới đây chỉ là ví dụ. Bạn **BẮT BUỘC** phải thay thế chúng bằng thông tin mạng thực tế của bạn:
> - **TACACS+ Server IP (`192.168.139.3`)**: Thay thế bằng IP của `tacacs-ng-ui` server.
> - **Device Source IP (`172.20.20.3`)**: Thay thế bằng IP nguồn thực tế trên cổng quản trị của thiết bị Juniper.
> - **Shared Secret (`change_this`)**: Thay thế bằng shared key được định nghĩa cho Host trong `tacacs-ng-ui`.

### A. Login Classes & Local Templates
Cấu hình các login class cục bộ và liên kết người dùng template `tacacs_read_only` và `tacacs_super_user` để định nghĩa quyền hạn:

```text
# 1. Định nghĩa login class với các quyền hạn và thời gian idle timeout
set system login class read-only-local idle-timeout 15
set system login class read-only-local permissions view
set system login class read-only-local permissions view-configuration

set system login class super-user-local idle-timeout 15
set system login class super-user-local permissions all

# 2. Ánh xạ các tài khoản TACACS+ được xác thực từ xa với template người dùng cục bộ
set system login user tacacs_read_only uid 2001
set system login user tacacs_read_only class read-only-local

set system login user tacacs_super_user uid 2002
set system login user tacacs_super_user class super-user-local
```

### B. Thứ Tự Xác Thực (Authentication Order)
Đặt TACACS+ làm cơ chế xác thực chính, và tự động chuyển về cơ sở dữ liệu mật khẩu cục bộ (local database) nếu không kết nối được tới TACACS+ server:

```text
set system authentication-order tacplus
set system authentication-order password
```

### C. Cấu Hình TACACS+ Server
Định nghĩa các tham số kết nối đến TACACS+ server:

```text
# Định nghĩa IP, port, secret key và IP nguồn của TACACS+ server
set system tacplus-server 192.168.139.3 port 49
set system tacplus-server 192.168.139.3 secret change_this
set system tacplus-server 192.168.139.3 source-address 172.20.20.3
```

### D. Cấu Cấu Hình Accounting (Ghi nhật ký)
Cấu hình ghi log accounting cho các sự kiện login, thay đổi cấu hình (change-log), và các câu lệnh tương tác (interactive-commands) để theo dõi lịch sử hoạt động:

```text
# Cấu hình các sự kiện accounting cần ghi nhận
set system accounting events login
set system accounting events change-log
set system accounting events interactive-commands

# Cấu hình cài đặt server destination để gửi log accounting
set system accounting destination tacplus server 192.168.139.3 secret change_this
set system accounting destination tacplus server 192.168.139.3 source-address 172.20.20.3
```

---

## 3. Cấu Hình Tham Chiếu Đầy Đủ

Thông tin phiên bản phần mềm:

```text
root@juniper1> show version 
Hostname: juniper1
Model: cRPD
Family: junos
Junos: 25.2R1.9
cRPD package version : 25.2R1.9 built by builder on 2025-06-24 15:29:28 UTC
```

Dưới đây là tập hợp đầy đủ các câu lệnh CLI để copy-paste trực tiếp trong chế độ cấu hình (`configure`) của Juniper:

```text
set system login class read-only-local idle-timeout 15
set system login class read-only-local permissions view
set system login class read-only-local permissions view-configuration
set system login class super-user-local idle-timeout 15
set system login class super-user-local permissions all
set system login user tacacs_read_only uid 2001
set system login user tacacs_read_only class read-only-local
set system login user tacacs_super_user uid 2002
set system login user tacacs_super_user class super-user-local

set system authentication-order tacplus
set system authentication-order password

set system tacplus-server 192.168.139.3 port 49
set system tacplus-server 192.168.139.3 secret change_this
set system tacplus-server 192.168.139.3 source-address 172.20.20.3

set system accounting events login
set system accounting events change-log
set system accounting events interactive-commands
set system accounting destination tacplus server 192.168.139.3 secret change_this
set system accounting destination tacplus server 192.168.139.3 source-address 172.20.20.3
```
