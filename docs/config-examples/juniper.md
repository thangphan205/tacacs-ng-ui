# Juniper Junos TACACS+ Integration Guide

This guide details how to integrate a Juniper device running Junos OS with the `tacacs-ng-ui` server, including the required server-side configurations and device CLI commands.

---

## 1. TACACS+ Server-Side Configuration (tacacs-ng-ui)

To configure `tacacs-ng-ui` to match your active server configuration, define the following components in the dashboard.

> [!NOTE]
> The profiles, groups, users, and ruleset below are pre-seeded by `init_db` on first startup. No manual creation is needed unless you removed them.

### A. Profiles
These profiles are pre-created under **Profiles**:

1. **`tacacs_super_user_profile` (Level 15 — full admin)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 15`

2. **`tacacs_read_only_profile` (Level 1 — read-only)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 1`

### B. Groups & Users
Pre-seeded groups and users:

#### Groups (**TACACS Groups**)
- **`tacacs_super_user`** — Full administrator privilege (level 15).
- **`tacacs_read_only`** — View-only operator privilege (level 1).

#### Users (**TACACS Users**)
- **`user_admin`**
  - **Password Type**: `crypt`, default password: `change_this`
  - **Group**: `tacacs_super_user`
- **`user_read_only`**
  - **Password Type**: `crypt`, default password: `change_this`
  - **Group**: `tacacs_read_only`

> [!WARNING]
> Change passwords for `user_admin` and `user_read_only` immediately after first login.

### C. Rulesets
Pre-seeded ruleset under **Rulesets**:

- **Ruleset Name**: `default_ruleset`
- **Ruleset Scripts**:
  - **Admin rule**: Condition: `if`, Key: `group`, Value: `tacacs_super_user` → Action: `permit`, Profile: `tacacs_super_user_profile`
  - **Read-only rule**: Condition: `if`, Key: `group`, Value: `tacacs_read_only` → Action: `permit`, Profile: `tacacs_read_only_profile`

> [!IMPORTANT]
> Remember to go to **TACACS Configs** → **Generate Config** → **Activate** the configuration for these changes to take effect on the daemon.

---

## 2. Device-Side Configuration (Juniper Junos)

Apply the following configuration commands to the Juniper device to configure TACACS+ integration.

> [!WARNING]
> The IP addresses and secrets used in the configuration below are examples. You **MUST** replace them with your own network details:
> - **TACACS+ Server IP (`192.168.139.3`)**: Replace this with your actual `tacacs-ng-ui` server IP address.
> - **Device Source IP (`172.20.20.3`)**: Replace this with the actual source IP address of your Juniper device's management interface.
> - **Shared Secret (`change_this`)**: Replace this with the secret defined for the Host in `tacacs-ng-ui`.

### A. Login Classes & Local Templates
Configure local classes and associate the local template users `tacacs_read_only` and `tacacs_super_user` to define permissions:

```text
# 1. Define login classes with permissions and idle timeout
set system login class read-only-local idle-timeout 15
set system login class read-only-local permissions view
set system login class read-only-local permissions view-configuration

set system login class super-user-local idle-timeout 15
set system login class super-user-local permissions all

# 2. Map authenticated remote TACACS+ usernames to local template users
set system login user tacacs_read_only uid 2001
set system login user tacacs_read_only class read-only-local

set system login user tacacs_super_user uid 2002
set system login user tacacs_super_user class super-user-local
```

### B. Authentication Order
Define TACACS+ as the primary authentication mechanism, falling back to local database passwords if TACACS+ servers are unreachable:

```text
set system authentication-order tacplus
set system authentication-order password
```

### C. TACACS+ Server Configuration
Define the connection parameters to reach the TACACS+ server:

```text
# Define TACACS+ server IP, port, secret key, and source IP
set system tacplus-server 192.168.139.3 port 49
set system tacplus-server 192.168.139.3 secret change_this
set system tacplus-server 192.168.139.3 source-address 172.20.20.3
```

### D. Accounting Configuration
Configure session, change, and interactive command accounting forwarding to track login activities and command execution history:

```text
# Configure accounting events to capture
set system accounting events login
set system accounting events change-log
set system accounting events interactive-commands

# Configure accounting destination server settings
set system accounting destination tacplus server 192.168.139.3 secret change_this
set system accounting destination tacplus server 192.168.139.3 source-address 172.20.20.3
```

---

## 3. Full Reference Configuration

Software version details:

```text
root@juniper1> show version 
Hostname: juniper1
Model: cRPD
Family: junos
Junos: 25.2R1.9
cRPD package version : 25.2R1.9 built by builder on 2025-06-24 15:29:28 UTC
```

Below is the complete CLI command set to copy and paste into your Juniper configuration mode (`configure`):

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
