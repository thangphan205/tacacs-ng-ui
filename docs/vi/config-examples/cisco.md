# Hướng Dẫn Tích Hợp TACACS+ Cho Thiết Bị Cisco IOS-XE

Tài liệu này hướng dẫn chi tiết cách tích hợp thiết bị Cisco chạy IOS-XE với `tacacs-ng-ui` server, bao gồm cấu hình phía server và các câu lệnh CLI trên thiết bị.

Đã kiểm thử trên Catalyst 9300 và ISR 4331 chạy IOS-XE 17.9.3. Xem [Danh sách thiết bị tương thích](https://github.com/thangphan205/tacacs-ng-ui/discussions/185) để biết các thiết bị khác đã được kiểm thử.

---

## 1. Cấu Hình Phía TACACS+ Server (tacacs-ng-ui)

> [!NOTE]
> Các profile, group, user và ruleset dưới đây đã được tạo sẵn (pre-seeded) bởi `init_db` trong lần khởi chạy đầu tiên. Bạn không cần tạo thủ công trừ khi đã xóa chúng.

IOS-XE gửi yêu cầu với **service `shell`**, và mức quyền (privilege level) của phiên lấy từ thuộc tính `priv-lvl` do server trả về.

### A. Host
Trong mục **Hosts**, thêm thiết bị (hoặc subnet của nó) cùng shared secret mà thiết bị sẽ dùng:

- **Name**: `cisco-c9300-01`
- **IPv4 Address**: `172.20.20.10/32`, đúng IP nguồn mà thiết bị thực sự gửi đi (xem mục 2.D)
- **Secret Key**: `change_this`

> [!TIP]
> tac_plus-ng bỏ qua (không ghi log) các yêu cầu từ client không xác định. Nếu đăng nhập thất bại mà không có dòng log nào, thiết bị đang dùng IP nguồn khác với IP đã đăng ký.

### B. Profiles
Các profile sau đã được tạo sẵn trong mục **Profiles**:

1. **`tacacs_super_user_profile` (Level 15 — full admin)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 15`

2. **`tacacs_read_only_profile` (Level 1 — chỉ đọc)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 1`

Với các profile này, giới hạn chỉ đọc do **thiết bị** thực thi: phiên level 1 chỉ chạy được lệnh level 1, còn `configure terminal` cần level 15. Hãy bảo vệ `enable` bằng một `enable secret` mạnh, vì ai biết secret này đều có thể nâng level. Server không kiểm tra từng lệnh. Để server cũng duyệt từng lệnh, xem mục 2.E.

### C. Groups, Users & Ruleset
Đã tạo sẵn:

- **Groups**: `tacacs_super_user` (level 15), `tacacs_read_only` (level 1)
- **Users**: `user_admin` → `tacacs_super_user`, `user_read_only` → `tacacs_read_only` (password type `crypt`, mật khẩu mặc định `change_this`)
- **Ruleset** `default_ruleset`: group `tacacs_super_user` → profile `tacacs_super_user_profile`; group `tacacs_read_only` → profile `tacacs_read_only_profile`

> [!WARNING]
> Thay đổi mật khẩu cho `user_admin` và `user_read_only` ngay sau lần đăng nhập đầu tiên.

> [!IMPORTANT]
> Nhớ truy cập mục **TACACS Configs** → **Generate Config** → **Activate** cấu hình để các thay đổi có hiệu lực trên daemon.

---

## 2. Cấu Hình Phía Thiết Bị (Cisco IOS-XE)

> [!WARNING]
> Địa chỉ IP và secret trong cấu hình dưới đây chỉ là ví dụ. Bạn **PHẢI** thay bằng thông tin mạng của mình:
> - **IP TACACS+ Server (`192.168.139.3`)**: thay bằng IP thực của `tacacs-ng-ui` server.
> - **Shared Secret (`change_this`)**: thay bằng secret đã khai báo cho Host trong `tacacs-ng-ui`.
> - **Source interface (`GigabitEthernet0/0`)**: thay bằng interface có IP đã đăng ký làm Host.

> [!CAUTION]
> Giữ một phiên thứ hai đăng nhập bằng tài khoản local cho tới khi mọi bước kiểm tra bên dưới đều đạt, và không `write memory` trước đó. Nếu bị khóa ngoài, `reload` sẽ trả lại cấu hình đã lưu. Đảm bảo có sẵn một user local dự phòng:
> `username admin privilege 15 secret <local-password>`

### A. Bật AAA

```text
aaa new-model
```

### B. TACACS+ Server và Server Group

```text
tacacs server TACACS-NG-1
 address ipv4 192.168.139.3
 key 0 change_this
 timeout 5
!
aaa group server tacacs+ TACACS-GROUP
 server name TACACS-NG-1
```

Với server thứ hai (HA), khai báo `tacacs server TACACS-NG-2` tương tự và thêm `server name TACACS-NG-2` vào group. Các server được thử theo thứ tự liệt kê.

### C. Authentication, Authorization và Accounting

```text
! Đăng nhập qua TACACS+, chỉ dùng tài khoản local khi không server nào trả lời
aaa authentication login default group TACACS-GROUP local
! Lấy privilege level của phiên (priv-lvl) từ server
aaa authorization exec default group TACACS-GROUP local
! Ghi nhận bắt đầu/kết thúc phiên và mọi lệnh ở level 1 và 15
aaa accounting exec default start-stop group TACACS-GROUP
aaa accounting commands 1 default start-stop group TACACS-GROUP
aaa accounting commands 15 default start-stop group TACACS-GROUP
!
line vty 0 4
 login authentication default
 authorization exec default
```

Fallback `local` chỉ được dùng khi **không server nào trả lời**. User bị server từ chối sẽ không được thử lại với cơ sở dữ liệu local.

### D. Source Interface và VRF

Thiết bị phải gửi TACACS+ từ đúng IP đã đăng ký làm Host. Khai báo trong server group:

```text
aaa group server tacacs+ TACACS-GROUP
 ip tacacs source-interface GigabitEthernet0/0
```

Trên switch Catalyst 9000, cổng quản lý `GigabitEthernet0/0` nằm trong `Mgmt-vrf`. Nếu server được truy cập qua cổng này, thêm VRF vào group:

```text
aaa group server tacacs+ TACACS-GROUP
 ip vrf forwarding Mgmt-vrf
 ip tacacs source-interface GigabitEthernet0/0
```

### E. Authorization Từng Lệnh (tùy chọn)

Để server duyệt mọi lệnh level 15:

```text
aaa authorization commands 15 default group TACACS-GROUP local
aaa authorization config-commands
!
line vty 0 4
 authorization commands 15 default
```

Mỗi yêu cầu đến dưới dạng `service = shell`, với dòng lệnh nằm trong `cmd`. Các profile tạo sẵn trả lời `permit` cho **mọi** yêu cầu `service = shell`, nên chúng cho phép mọi lệnh. Để giới hạn lệnh trên server, tạo một profile ở chế độ **Raw script** tách phần bắt đầu phiên (`cmd == ""`) khỏi các lệnh, rồi trỏ quy tắc read-only của ruleset sang profile đó:

```text
if (service == shell) {
    if (cmd == "") {
        set priv-lvl = 1
        permit
    }
    if (cmd =~ /^(show|ping|traceroute|terminal|exit|quit|logout)(\s|$)/) permit
    deny
}
deny
```

Thêm các nhánh cho những hãng khác dùng chung profile này (ví dụ `if (service == junos-exec) { set local-user-name = tacacs_read_only permit }`) trước dòng `deny` cuối cùng. Nhấn **Check with tac_plus-ng** trước khi lưu.

---

## 3. Kiểm Tra

Thực hiện từ một phiên thứ hai trong khi phiên đầu vẫn mở:

1. `user_admin` đăng nhập vào privileged exec (dấu nhắc `#`) và vào được `configure terminal`.
2. `user_read_only` đăng nhập ở level 1 (dấu nhắc `>`): `show version` chạy được, `configure terminal` bị từ chối.
3. Tài khoản local bị từ chối khi TACACS+ server vẫn kết nối được.
4. `show tacacs` hiển thị server với bộ đếm gói tin tăng dần.
5. Trong tacacs-ng-ui, các lần đăng nhập và lệnh xuất hiện ở **Log Events** với đúng IP nguồn.

Lệnh debug hữu ích: `debug tacacs`, `debug aaa authentication`, `debug aaa authorization`, `test aaa group TACACS-GROUP user_admin change_this new-code`.

---

## 4. Cấu Hình Tham Chiếu Đầy Đủ

```text
aaa new-model
!
username admin privilege 15 secret <local-password>
!
tacacs server TACACS-NG-1
 address ipv4 192.168.139.3
 key 0 change_this
 timeout 5
!
aaa group server tacacs+ TACACS-GROUP
 server name TACACS-NG-1
 ip tacacs source-interface GigabitEthernet0/0
!
aaa authentication login default group TACACS-GROUP local
aaa authorization exec default group TACACS-GROUP local
aaa accounting exec default start-stop group TACACS-GROUP
aaa accounting commands 1 default start-stop group TACACS-GROUP
aaa accounting commands 15 default start-stop group TACACS-GROUP
!
line vty 0 4
 login authentication default
 authorization exec default
!
end
```

Sau khi kiểm tra đạt: `write memory`.
