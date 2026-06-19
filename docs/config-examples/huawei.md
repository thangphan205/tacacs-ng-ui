# Huawei VRP TACACS+ Integration Guide

This guide details how to integrate a Huawei device running VRP (Versatile Routing Platform) with the `tacacs-ng-ui` server, including the required server-side configurations and device CLI commands.

---

## 1. TACACS+ Server-Side Configuration (tacacs-ng-ui)

To configure `tacacs-ng-ui` to match your active server configuration, define the following components in the dashboard.

### A. Profiles
Configure the authorization profiles under **Profiles** → **Add Profile**:

1. **`tacacs_huawei1_profile` (Level 1)**
   - **Action**: `deny` (Default action, then permit via scripts)
   - **Profile Scripts**:
     - Condition: `$service == "nas_admin"` → Key: `priv-lvl`, Value: `1`, Action: `set` (Action: `permit`)
     - Condition: `$service == "shell"` → Key: `priv-lvl`, Value: `1`, Action: `set` (Action: `permit`)

2. **`tacacs_huawei15_profile` (Level 15)**
   - **Action**: `deny` (Default action, then permit via scripts)
   - **Profile Scripts**:
     - Condition: `$service == "nas_admin"` → Key: `priv-lvl`, Value: `15`, Action: `set` (Action: `permit`)
     - Condition: `$service == "shell"` → Key: `priv-lvl`, Value: `15`, Action: `set` (Action: `permit`)

### B. Groups & Users
Set up the groups and users in their respective sections:

#### Groups (**TACACS Groups** → **Add Group**)
- **`huawei_user_level1`** — For operator/view-only privilege.
- **`huawei_user_level15`** — For full administrator privilege.

#### Users (**TACACS Users** → **Add User**)
- **`huawei1`**
  - **Password Type**: `crypt` (or `pap`)
  - **Group**: `huawei_user_level1`
- **`huawei15`**
  - **Password Type**: `crypt` (or `pap`)
  - **Group**: `huawei_user_level15`

### C. Rulesets
Map groups to their profiles under **Rulesets** → **Add Ruleset**:

- **Ruleset Name**: `default_ruleset`
- **Ruleset Scripts**:
  - **Rule for Level 1**: Condition: `$group == "huawei_user_level1"` → Action: `permit` → Profile: `tacacs_huawei1_profile`
  - **Rule for Level 15**: Condition: `$group == "huawei_user_level15"` → Action: `permit` → Profile: `tacacs_huawei15_profile`

> [!IMPORTANT]
> Remember to go to **TACACS Configs** → **Generate Config** → **Activate** the configuration for these changes to take effect on the daemon.

---

## 2. Device-Side Configuration (Huawei VRP)

Apply the following configuration to the Huawei device (`sysname huawei1`) to configure TACACS+ integration.

> [!WARNING]
> The IP addresses used in the configuration below are examples. You **MUST** replace them with your own network details:
> - **TACACS+ Server IP (`103.67.185.64`)**: Replace this with your actual `tacacs-ng-ui` server IP address.
> - **Device Source IP (`10.0.0.15`)**: Replace this with the actual IP address of your Huawei device's management interface.

### A. Enable HWTACACS & Define Template
Create the HWTACACS server template pointing to the TACACS+ server:

```text
# Enable HWTACACS service globally
hwtacacs enable

# Create HWTACACS template and configure servers
hwtacacs server template tacacs_netadmin
  # Define TACACS+ server IP (Replace 103.67.185.64 with your tacacs-ng-ui server IP)
  hwtacacs server authentication 103.67.185.64 vpn-instance __MGMT_VPN__
  hwtacacs server authorization 103.67.185.64 vpn-instance __MGMT_VPN__
  hwtacacs server accounting 103.67.185.64 vpn-instance __MGMT_VPN__
  
  # Source IP of the device's management interface
  hwtacacs server source-ip 10.0.0.15
  
  # Shared key configured in tacacs-ng-ui for this Host
  hwtacacs server shared-key cipher Netconsole123
  
  # Exclude domain name when sending username to TACACS+ server
  hwtacacs server user-name domain-excluded
```

### B. AAA Scheme Configuration
Define the authentication, authorization, accounting, and command recording schemes:

```text
aaa
  # 1. Authentication Scheme (try TACACS first, fall back to Local)
  authentication-scheme tac_auth
    authentication-mode hwtacacs local
    
  # 2. Authorization Scheme (try TACACS first, fall back to Local)
  authorization-scheme tac_author
    authorization-mode hwtacacs local
    
  # 3. Accounting Scheme (send session accounting details to TACACS)
  accounting-scheme tac_acct
    accounting-mode hwtacacs
    
  # 4. Command Recording Scheme (logs CLI commands executed to TACACS+)
  recording-scheme tac_acct
    recording-mode hwtacacs tacacs_netadmin
```

### C. Domain Binding
Bind the TACACS schemes and server template to the `default_admin` domain:

```text
aaa
  # Bind schemes to default_admin domain
  domain default_admin
    authentication-scheme tac_auth
    authorization-scheme tac_author
    accounting-scheme tac_acct
    hwtacacs server tacacs_netadmin
```

### D. User Interface (VTY) Configuration
Apply AAA authentication and restrict access to SSH protocol on user lines:

```text
user-interface vty 0 4
  authentication-mode aaa
  idle-timeout 15 0
  protocol inbound ssh
```

---

## 3. Full Reference Configuration

Below is the complete running configuration dump from the integrated Huawei CE12800 switch (`huawei1`):

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
interface GE1/0/6
 shutdown
#
interface GE1/0/7
 shutdown
#
interface GE1/0/8
 shutdown
#
interface GE1/0/9
 shutdown
#
interface NULL0 
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