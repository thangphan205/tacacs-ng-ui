# Hướng Dẫn Tích Hợp TACACS+ Cho Thiết Bị Arista EOS

Tài liệu này hướng dẫn chi tiết cách tích hợp switch Arista chạy EOS với `tacacs-ng-ui` server, bao gồm cấu hình phía server và các câu lệnh CLI trên thiết bị.

Đã kiểm thử trên vEOS chạy EOS 4.28F. Xem [Danh sách thiết bị tương thích](https://github.com/thangphan205/tacacs-ng-ui/discussions/185) để biết các thiết bị khác đã được kiểm thử.

---

## 1. Cấu Hình Phía TACACS+ Server (tacacs-ng-ui)

> [!NOTE]
> Các profile, group, user và ruleset dưới đây đã được tạo sẵn (pre-seeded) bởi `init_db` trong lần khởi chạy đầu tiên. Bạn không cần tạo thủ công trừ khi đã xóa chúng.

EOS gửi yêu cầu với **service `shell`**. Thuộc tính `priv-lvl` do server trả về quyết định quyền của phiên: `15` vào thẳng privileged exec, các level thấp hơn vào unprivileged exec.

### A. Host
Trong mục **Hosts**, thêm switch (hoặc subnet của nó) cùng shared secret mà switch sẽ dùng:

- **Name**: `arista-leaf-01`
- **IPv4 Address**: `172.20.20.20/32`, đúng IP nguồn mà switch thực sự gửi đi (xem mục 2.D)
- **Secret Key**: `change_this`

> [!TIP]
> tac_plus-ng bỏ qua (không ghi log) các yêu cầu từ client không xác định. Nếu đăng nhập thất bại mà không có dòng log nào, switch đang dùng IP nguồn khác với IP đã đăng ký.

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

## 2. Cấu Hình Phía Thiết Bị (Arista EOS)

> [!WARNING]
> Địa chỉ IP và secret trong cấu hình dưới đây chỉ là ví dụ. Bạn **PHẢI** thay bằng thông tin mạng của mình:
> - **IP TACACS+ Server (`192.168.139.3`)**: thay bằng IP thực của `tacacs-ng-ui` server.
> - **Shared Secret (`change_this`)**: thay bằng secret đã khai báo cho Host trong `tacacs-ng-ui`.
> - **Source interface (`Management1`)**: thay bằng interface có IP đã đăng ký làm Host.

> [!CAUTION]
> Giữ một phiên thứ hai đăng nhập bằng tài khoản local cho tới khi mọi bước kiểm tra bên dưới đều đạt, và không `write memory` trước đó. Authorization từng lệnh (mục C) áp dụng ngay cho chính phiên của bạn khi vừa nhập, nên sai key hoặc server không kết nối được có thể khóa bạn ở lệnh tiếp theo. Đảm bảo có sẵn một user local dự phòng:
> `username admin privilege 15 role network-admin secret <local-password>`
>
> Trên EOS bạn cũng có thể soạn toàn bộ trong một configuration session, áp dụng bằng `commit timer 00:10:00`, rồi `commit` lần nữa để xác nhận.

### A. TACACS+ Server

```text
tacacs-server host 192.168.139.3 key 0 change_this
tacacs-server timeout 5
```

Với server thứ hai (HA), thêm một dòng `tacacs-server host` nữa. Các server được thử theo thứ tự cấu hình.

### B. Server Group

```text
aaa group server tacacs+ TACACS_GROUP
   server 192.168.139.3
```

### C. Authentication, Authorization và Accounting

```text
! Đăng nhập qua TACACS+, chỉ dùng tài khoản local khi không server nào trả lời
aaa authentication login default group TACACS_GROUP local
! Lấy privilege level của phiên (priv-lvl) từ server
aaa authorization exec default group TACACS_GROUP local
! Hỏi server trước khi chạy mỗi lệnh
aaa authorization commands all default group TACACS_GROUP local
! Ghi nhận bắt đầu/kết thúc phiên và mọi lệnh
aaa accounting exec default start-stop group TACACS_GROUP
aaa accounting commands all default start-stop group TACACS_GROUP
```

Fallback `local` chỉ được dùng khi **không server nào trả lời**. User bị server từ chối sẽ không được thử lại với cơ sở dữ liệu local.

> [!WARNING]
> Với `aaa authorization commands all`, mỗi lệnh đến dưới dạng `service = shell`, với dòng lệnh nằm trong `cmd`. Các profile tạo sẵn trả lời `permit` cho **mọi** yêu cầu `service = shell`, nên server cho phép mọi lệnh. Khi đó user read-only chỉ bị giới hạn bởi phiên unprivileged exec. Để server cũng giới hạn lệnh, xem mục 2.E.

### D. Source Interface và VRF

Switch phải gửi TACACS+ từ đúng IP đã đăng ký làm Host:

```text
ip tacacs source-interface Management1
```

Nếu server được truy cập qua VRF quản lý (ví dụ `MGMT`), khai báo VRF trên server, group và source interface:

```text
tacacs-server host 192.168.139.3 vrf MGMT key 0 change_this
!
aaa group server tacacs+ TACACS_GROUP
   server 192.168.139.3 vrf MGMT
!
ip tacacs vrf MGMT source-interface Management1
```

### E. Giới Hạn Lệnh Trên Server (khuyến nghị)

Tạo một profile ở chế độ **Raw script** tách phần bắt đầu phiên (`cmd == ""`) khỏi các lệnh, rồi trỏ quy tắc read-only của ruleset sang profile đó:

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

1. `user_admin` đăng nhập vào privileged exec (dấu nhắc `#`) và vào được `configure`.
2. `user_read_only` đăng nhập ở unprivileged exec (dấu nhắc `>`): `show version` chạy được, `configure` thì không.
3. Tài khoản local bị từ chối khi TACACS+ server vẫn kết nối được.
4. `show tacacs` hiển thị server với bộ đếm message tăng dần.
5. Trong tacacs-ng-ui, các lần đăng nhập và lệnh xuất hiện ở **Log Events** với đúng IP nguồn.

---

## 4. Cấu Hình Tham Chiếu Đầy Đủ

```text
username admin privilege 15 role network-admin secret <local-password>
!
tacacs-server timeout 5
tacacs-server host 192.168.139.3 key 0 change_this
!
aaa group server tacacs+ TACACS_GROUP
   server 192.168.139.3
!
aaa authentication login default group TACACS_GROUP local
aaa authorization exec default group TACACS_GROUP local
aaa authorization commands all default group TACACS_GROUP local
aaa accounting exec default start-stop group TACACS_GROUP
aaa accounting commands all default start-stop group TACACS_GROUP
!
ip tacacs source-interface Management1
```

Sau khi kiểm tra đạt: `write memory`.
