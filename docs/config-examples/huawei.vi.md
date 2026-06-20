# Hướng Dẫn Tích Hợp TACACS+ Cho Thiết Bị Huawei VRP

Tài liệu này hướng dẫn chi tiết cách tích hợp thiết bị Huawei chạy hệ điều hành VRP (Versatile Routing Platform) với `tacacs-ng-ui` server, bao gồm cấu hình phía server và các câu lệnh CLI trên thiết bị.

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
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 15` *(Cisco/Arista/Huawei VRP)*
     - Condition: `if`, Key: `service`, Value: `h3c_shell` → Action: `permit`, Set: `priv-lvl = 15` *(Huawei H3C)*

2. **`tacacs_read_only_profile` (Level 1 — chỉ đọc)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 1` *(Cisco/Arista/Huawei VRP)*
     - Condition: `if`, Key: `service`, Value: `h3c_shell` → Action: `permit`, Set: `priv-lvl = 1` *(Huawei H3C)*

### B. Groups & Users
Nhóm và người dùng tạo sẵn:

#### Groups (**TACACS Groups**)
- **`tacacs_super_user`** — Quyền quản trị viên đầy đủ (level 15).
- **`tacacs_read_only`** — Quyền người vận hành chỉ đọc (level 1).

#### Users (**TACACS Users**)
- **`user_admin`**
  - **Password Type**: `crypt`, mật khẩu mặc định: `change_this`
  - **Group**: `tacacs_super_user`
- **`user_read_only`**
  - **Password Type**: `crypt`, mật khẩu mặc định: `change_this`
  - **Group**: `tacacs_read_only`

> [!WARNING]
> Thay đổi mật khẩu cho `user_admin` and `user_read_only` ngay sau lần đăng nhập đầu tiên.

### C. Rulesets
Ruleset tạo sẵn trong mục **Rulesets**:

- **Ruleset Name**: `default_ruleset`
- **Ruleset Scripts**:
  - **Quy tắc Admin**: Condition: `if`, Key: `group`, Value: `tacacs_super_user` → Action: `permit`, Profile: `tacacs_super_user_profile`
  - **Quy tắc Chỉ đọc**: Condition: `if`, Key: `group`, Value: `tacacs_read_only` → Action: `permit`, Profile: `tacacs_read_only_profile`

> [!IMPORTANT]
> Nhớ truy cập mục **TACACS Configs** → **Generate Config** → **Activate** cấu hình để các thay đổi có hiệu lực trên daemon.

---

## 2. Cấu Hinh Phía Thiết Bị (Huawei VRP)

Áp dụng các câu lệnh cấu hình sau trên thiết bị Huawei (`sysname huawei1`) để hoàn tất tích hợp TACACS+.

> [!WARNING]
> Các địa chỉ IP và shared secret dưới đây chỉ là ví dụ. Bạn **BẮT BUỘC** phải thay thế chúng bằng thông tin mạng thực tế của bạn:
> - **TACACS+ Server IP (`103.67.185.64`)**: Thay thế bằng IP của `tacacs-ng-ui` server.
> - **Device Source IP (`10.0.0.15`)**: Thay thế bằng IP nguồn thực tế trên cổng quản trị của thiết bị Huawei.

### A. Kích hoạt HWTACACS & Định nghĩa Template
Tạo template HWTACACS server trỏ tới TACACS+ server:

```text
# Bật dịch vụ HWTACACS trên toàn cục
hwtacacs enable

# Tạo template HWTACACS và cấu hình server
hwtacacs server template tacacs_netadmin
  # Định nghĩa IP TACACS+ server (Thay 103.67.185.64 bằng IP tacacs-ng-ui server của bạn)
  hwtacacs server authentication 103.67.185.64 vpn-instance __MGMT_VPN__
  hwtacacs server authorization 103.67.185.64 vpn-instance __MGMT_VPN__
  hwtacacs server accounting 103.67.185.64 vpn-instance __MGMT_VPN__
  
  # IP nguồn của cổng quản trị trên thiết bị
  hwtacacs server source-ip 10.0.0.15
  
  # Shared key được cấu hình trong tacacs-ng-ui cho Host này
  hwtacacs server shared-key cipher Netconsole123
  
  # Loại bỏ domain name khi gửi username đến TACACS+ server
  hwtacacs server user-name domain-excluded
```

### B. Cấu hình AAA Scheme
Định nghĩa các AAA scheme cho xác thực, phân quyền, kế toán và ghi lệnh:

```text
aaa
  # 1. Authentication Scheme (thử TACACS trước, fallback về Local)
  authentication-scheme tac_auth
    authentication-mode hwtacacs local
    
  # 2. Authorization Scheme (thử TACACS trước, fallback về Local)
  authorization-scheme tac_author
    authorization-mode hwtacacs local
    
  # 3. Accounting Scheme (gửi thông tin phiên làm việc accounting tới TACACS)
  accounting-scheme tac_acct
    accounting-mode hwtacacs
    
  # 4. Command Recording Scheme (ghi log các câu lệnh CLI đã thực thi tới TACACS+)
  recording-scheme tac_acct
    recording-mode hwtacacs tacacs_netadmin
```

### C. Liên Kết Domain (Domain Binding)
Liên kết các AAA scheme và template HWTACACS server vào domain `default_admin`:

```text
aaa
  # Liên kết scheme vào domain default_admin
  domain default_admin
    authentication-scheme tac_auth
    authorization-scheme tac_author
    accounting-scheme tac_acct
    hwtacacs server tacacs_netadmin
```

### D. Cấu hình User Interface (VTY)
Áp dụng xác thực AAA và giới hạn truy cập SSH trên các đường VTY:

```text
user-interface vty 0 4
  authentication-mode aaa
  idle-timeout 15 0
  protocol inbound ssh
```

---

## 3. Cấu Hình Tham Chiếu Đầy Đủ

Dưới đây là cấu hình chạy thực tế đầy đủ của switch Huawei CE12800 (`huawei1`):

```text
!Software Version V200R005C10SPC607B607
!Last configuration was updated at 2026-06-18 16:27:51+00:00 by admin
!Last configuration was saved at 2026-06-18 09:38:12+00:00
#
sysname huawei1
#
device board 17 board-type CE-MPUB
device board 1 board-type CE-LPUE
#
dot1x enable
domain default_admin
#
hwtacacs enable
#
ip vpn-instance __MGMT_VPN__
 ipv4-family
#
hwtacacs server template tacacs_netadmin
 hwtacacs server authentication 103.67.185.64 vpn-instance __MGMT_VPN__
 hwtacacs server authorization 103.67.185.64 vpn-instance __MGMT_VPN__
 hwtacacs server accounting 103.67.185.64 vpn-instance __MGMT_VPN__
 hwtacacs server source-ip 10.0.0.15
 hwtacacs server shared-key cipher %^%#I~:3HIRRQK71DPUV-,gFk8uD6N{,+BBv>i"\TzD,%^%#
 hwtacacs server user-name domain-excluded
#
aaa
 undo local-user policy security-enhance
  local-user admin password irreversible-cipher $1c$>O`i$===H)$4:WT'KV;S:D(Np1yR$2"&(oQG3rc2)%^~<I7@fZF$
 local-user admin service-type ssh
 local-user admin user-group manage-ug
 #
 authentication-scheme default
 #
 authentication-scheme tac_auth
  authentication-mode hwtacacs local
 #
 authorization-scheme default
 #
 authorization-scheme tac_author
  authorization-mode hwtacacs local
 #
 accounting-scheme default
 #
 accounting-scheme tac_acct
  accounting-mode hwtacacs
 #
 domain default 
 #
 domain default_admin
  authentication-scheme tac_auth
  authorization-scheme tac_author
  accounting-scheme tac_acct
  hwtacacs server tacacs_netadmin
 #
 recording-scheme tac_acct
  recording-mode hwtacacs tacacs_netadmin
#
interface MEth0/0/0
 undo shutdown
 ip binding vpn-instance __MGMT_VPN__
 ip address 10.0.0.15 255.255.255.0
#
interface GE1/0/0
 shutdown
#
interface GE1/0/1
 shutdown
#
interface GE1/0/2
 shutdown       
#
interface GE1/0/3
 shutdown
#
interface GE1/0/4
 shutdown
#
interface GE1/0/5
 shutdown
#
interface MEth0/0/0
 undo shutdown
 ip binding vpn-instance __MGMT_VPN__
 ip address 10.0.0.15 255.255.255.0
#
interface GE1/0/0
 shutdown
#
interface GE1/0/1
 shutdown
#
interface MEth0/0/0
 undo shutdown
 ip binding vpn-instance __MGMT_VPN__
 ip address 10.0.0.15 255.255.255.0
#
ip route-static vpn-instance __MGMT_VPN__ 0.0.0.0 0.0.0.0 10.0.0.2
#
stelnet server enable
snetconf server enable
ssh user admin
ssh user admin authentication-type password
ssh user admin service-type all
ssh user thang1
ssh user thang1 authentication-type password
ssh user thang1 service-type all
ssh authorization-type default aaa
#
ssh server cipher aes256_gcm aes128_gcm aes256_ctr aes192_ctr aes128_ctr aes256_cbc aes128_cbc 3des_cbc
#
ssh server dh-exchange min-len 1024
#
ssh client cipher aes256_gcm aes128_gcm aes256_ctr aes192_ctr aes128_ctr aes256_cbc aes128_cbc 3des_cbc
#
user-interface con 0
#
user-interface vty 0 4
 authentication-mode aaa
 idle-timeout 15 0
 protocol inbound ssh
#
netconf
 protocol inbound ssh port 830
#
vm-manager
#
return
```
