# Huawei Physical Switch (Campus S-Series / V200R022) TACACS+ Integration Guide

This guide details how to integrate a **physical Huawei campus switch** (e.g., S5700 / S5720 / S5735 / S6700 series running VRP V200R022) with the `tacacs-ng-ui` server.

> [!NOTE]
> Physical campus switches running VRP V200R022 use a different command syntax compared to virtual/data center CloudEngine switches (CE12800 / eNSP). See [Key Differences](#key-differences-physical-campus-vs-virtual-cloudengine) below for a breakdown.

---

## 1. Key Differences: Physical Campus vs. Virtual CloudEngine

| Parameter / Feature | Physical Campus Switch (S-Series / V200R022) | Virtual Switch (CloudEngine CE12800 / eNSP) |
|---|---|---|
| **CLI Keyword Syntax** | Hyphenated: `hwtacacs-server template <name>`, `hwtacacs-server authentication ...` | Space-separated: `hwtacacs server template <name>`, `hwtacacs server authentication ...` |
| **Domain Binding Command** | `hwtacacs-server <template_name>` under `aaa -> domain` | `hwtacacs server <template_name>` under `aaa -> domain` |
| **HWTACACS Enablement** | `hwtacacs enable` (often `undo hwtacacs enable` by default) | `hwtacacs enable` |
| **Domain Name Suffix** | `undo hwtacacs-server user-name domain-included` | `hwtacacs server user-name domain-excluded` |
| **Management Routing** | Usually in-band via VLAN interface (e.g., `Vlanif101`) in the global routing table | Usually out-of-band via `MEth0/0/0` inside a VRF (`vpn-instance __MGMT_VPN__`) |
| **Command Recording** | Requires `recording-scheme <name>` **plus** `cmd recording-scheme <name>` under `aaa` | Configured directly under `recording-scheme` in `aaa` |
| **Default Admin Domain** | `domain default_admin admin` in system-view ensures administrative SSH logins use `default_admin` | `domain default_admin` |
| **SSH Dynamic Auth** | **Mandatory**: `ssh authorization-type default aaa` allows TACACS+ SSH users without pre-existing `ssh user` entries | `ssh authorization-type default aaa` |
| **Accounting Resiliency** | `accounting start-fail online` prevents dropping users if accounting packet exchange encounters latency | Usually default |

---

## 2. Server-Side Configuration (tacacs-ng-ui)

Configure `tacacs-ng-ui` to support the physical Huawei switch:

### A. Host Registration
Navigate to **Hosts** -> **Add Host**:
- **Host Name**: `Huawei` (or your switch hostname)
- **IP Address**: `10.11.1.104` (The switch source IP, e.g., `Vlanif101`)
- **Shared Secret Key**: `<YOUR_TACACS_SECRET_KEY>` (e.g., `Netconsole123`)

### B. Pre-seeded Profiles, Groups & Users
The default pre-seeded objects in `tacacs-ng-ui` are ready for Huawei VRP:
1. **Profiles**:
   - `tacacs_super_user_profile`: Returns `priv-lvl = 15` for services `shell` and `h3c_shell`.
   - `tacacs_read_only_profile`: Returns `priv-lvl = 1` for services `shell` and `h3c_shell`.
2. **Groups**: `tacacs_super_user` (level 15) and `tacacs_read_only` (level 1).
3. **Users**: `user_admin` (member of `tacacs_super_user`) and `user_read_only` (member of `tacacs_read_only`).
4. **Ruleset**: `default_ruleset` permits both groups and attaches their respective profiles.

> [!IMPORTANT]
> Always navigate to **TACACS Configs** -> **Generate Config** -> **Activate** after modifying hosts or rules.

---

## 3. Device-Side Configuration (Physical Huawei Switch CLI)

Apply the following commands to your physical switch in **system-view**:

### Step 1: Enable HWTACACS Globally
```text
system-view
hwtacacs enable
```

### Step 2: Configure HWTACACS Server Template
Create the template using the hyphenated `hwtacacs-server` syntax:

```text
hwtacacs-server template tacacs_netadmin
 # TACACS+ Server IP address (Replace with your actual tacacs-ng-ui server IP)
 hwtacacs-server authentication <IP_TACACS_SERVER>
 hwtacacs-server authorization <IP_TACACS_SERVER>
 hwtacacs-server accounting <IP_TACACS_SERVER>
 
 # Source IP of the management VLAN interface (e.g., Vlanif101: 10.11.1.104)
 hwtacacs-server source-ip 10.11.1.104
 
 # Shared Secret Key matching tacacs-ng-ui host configuration
 hwtacacs-server shared-key simple <YOUR_TACACS_SECRET_KEY>
 
 # Strip domain suffix (@domain) when forwarding username to TACACS+
 undo hwtacacs-server user-name domain-included
quit
```

### Step 3: Configure AAA Schemes & Command Recording
Configure fallback to local accounts so administrators are never locked out if TACACS+ is unreachable:

```text
aaa
 # 1. Authentication Scheme (TACACS+ primary, Local fallback)
 authentication-scheme tac_auth
  authentication-mode hwtacacs local
 quit

 # 2. Authorization Scheme (TACACS+ primary, Local fallback)
 authorization-scheme tac_author
  authorization-mode hwtacacs local
 quit

 # 3. Accounting Scheme (Send session accounting to TACACS+)
 accounting-scheme tac_acct
  accounting-mode hwtacacs
  accounting start-fail online
 quit

 # 4. Command Recording Scheme (Audit CLI commands executed by users)
 recording-scheme tac_record
  recording-mode hwtacacs tacacs_netadmin
 quit
 cmd recording-scheme tac_record
quit
```

### Step 4: Bind Schemes to `default_admin` Domain
```text
aaa
 domain default_admin
  authentication-scheme tac_auth
  authorization-scheme tac_author
  accounting-scheme tac_acct
  hwtacacs-server tacacs_netadmin
 quit
quit

# Set default_admin as the default administrative domain for SSH / Console / Telnet logins
domain default_admin admin
```

### Step 5: Enable SSH Dynamic AAA Authorization
On physical Huawei switches, SSH by default only allows users configured with `ssh user <username>`. You must enable default AAA authorization:

```text
# Allow any valid TACACS+ authenticated user to log in via SSH
ssh authorization-type default aaa
```

### Step 6: Secure User Interfaces (VTY & Console)
```text
# Apply AAA to remote VTY lines
user-interface vty 0 4
 authentication-mode aaa
 idle-timeout 15 0
 protocol inbound ssh

# Verify Console keeps AAA with local fallback
user-interface con 0
 authentication-mode aaa
```

---

## 4. Complete Ready-to-Paste Configuration Snippet

```text
system-view
hwtacacs enable
#
hwtacacs-server template tacacs_netadmin
 hwtacacs-server authentication <IP_TACACS_SERVER>
 hwtacacs-server authorization <IP_TACACS_SERVER>
 hwtacacs-server accounting <IP_TACACS_SERVER>
 hwtacacs-server source-ip 10.11.1.104
 hwtacacs-server shared-key simple <YOUR_TACACS_SECRET_KEY>
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

## 5. Verification & Troubleshooting

### Test AAA Authentication Directly on CLI
Before logging out of your active session, test connectivity to TACACS+ from the user view (`<Huawei>`):

```text
test-aaa <username> <password> hwtacacs-template tacacs_netadmin
```
- **Success output**: `Info: Account test succeeded.`
- **Failure output**: Indicates an incorrect password, mismatched shared key, or network routing/firewall block between `10.11.1.104` and `<IP_TACACS_SERVER>:49`.

### Check HWTACACS Server Status & Statistics
```text
display hwtacacs-server template tacacs_netadmin
```
Verify that the server status shows `active` and packet counters (Request/Reply) increment.

### Inspect Active Authenticated Users
```text
display aaa online-user
```
Verify that logged-in users show `Domain: default_admin` and `Authen-Mode: HWTACACS`.

### Fallback Verification
If `tacacs-ng-ui` is stopped or unreachable, the switch immediately checks the local user database (`local-user admin`, `local-user pescoadmin`), ensuring emergency access is never lost.
