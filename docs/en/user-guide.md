# tacacs-ng-ui User Guide


---

> ### ⚠️ IMPORTANT — READ FIRST
>
> **Whenever you change any TACACS configuration (users, groups, hosts, profiles, rulesets, settings), you MUST go to TACACS Configs → Generate Config → mark the new config as Active.**
>
> Changes do NOT take effect on the TACACS+ server until the config is regenerated and activated.

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Initial Data (Seed)](#initial-data-seed)
3. [Core Concepts](#core-concepts)
4. [Step-by-Step: First-Time Setup](#step-by-step-first-time-setup)
4. [Managing TACACS+ Users & Groups](#managing-tacacs-users--groups)
5. [Configuring Network Devices (Hosts)](#configuring-network-devices-hosts)
6. [Access Control: Profiles & Rulesets](#access-control-profiles--rulesets)
7. [Server Settings](#server-settings)
8. [Generating and Applying Config Files](#generating-and-applying-config-files)
9. [Dashboard Overview](#dashboard-overview)
10. [TACACS Log Events Viewer](#tacacs-log-events-viewer)
11. [SIEM Integration](#siem-integration)
12. [Monitoring & Statistics](#monitoring--statistics)
13. [Audit Logs](#audit-logs)
14. [Application User Management](#application-user-management)
15. [Advanced: MAVIS Backends](#advanced-mavis-backends)
16. [Advanced: Custom Configuration Options](#advanced-custom-configuration-options)
17. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Login

Navigate to your dashboard URL (e.g., `http://localhost:5173` or your configured domain).

![Dashboard Login](../../img/login.png)

Login options:
- **Email + Password** — default method
- **Sign in with Google** — requires Google OAuth configured in `.env`
- **Sign in with Keycloak** — requires Keycloak OIDC configured
- **Passkeys** — passwordless login via WebAuthn (biometrics/hardware key)

Default admin credentials are set via `FIRST_SUPERUSER` and `FIRST_SUPERUSER_PASSWORD` in your `.env` file.

After login you land on the main dashboard:

![Dashboard](../../img/dashboard.png)

---

## Initial Data (Seed)

On first startup, tacacs-ng-ui automatically creates the following data. This gives you a working TACACS+ configuration out of the box for Cisco, Arista, Huawei, Juniper, Palo Alto, and Fortinet devices.

### Services

| Name | Used by |
|------|---------|
| `shell` | Cisco, Arista, Huawei VRP |
| `junos-exec` | Juniper |
| `h3c_shell` | Huawei H3C / Comware |
| `PaloAlto` | Palo Alto Networks |
| `fortigate` | Fortinet FortiGate |

### Groups

| Group | Purpose |
|-------|---------|
| `tacacs_super_user` | Full admin access — privilege level 15 |
| `tacacs_read_only` | Read-only access — privilege level 1 |

### TACACS+ Users

| Username | Password | Group | Purpose |
|----------|----------|-------|---------|
| `user_admin` | `change_this` | `tacacs_super_user` | Admin — full access on all devices |
| `user_read_only` | `change_this` | `tacacs_read_only` | Read-only on all devices |

> **Action required:** Change these passwords immediately after first login via **TACACS Users → Edit**.

### Profiles & Authorization Attributes

**`tacacs_super_user_profile`** — returned for `tacacs_super_user` group members:

| Service | Attribute returned | Value |
|---------|--------------------|-------|
| `shell` | `priv-lvl` | `15` |
| `junos-exec` | `local-user-name` | `tacacs_super_user` |
| `h3c_shell` | `priv-lvl` | `15` |
| `PaloAlto` | `PaloAlto-Admin-Role` | `superuser` |
| `fortigate` | `admin_prof` | `super_admin` |

**`tacacs_read_only_profile`** — returned for `tacacs_read_only` group members:

| Service | Attribute returned | Value |
|---------|--------------------|-------|
| `shell` | `priv-lvl` | `1` |
| `junos-exec` | `local-user-name` | `tacacs_read_only` |
| `h3c_shell` | `priv-lvl` | `1` |
| `PaloAlto` | `PaloAlto-Admin-Role` | `devicereader` |
| `fortigate` | `admin_prof` | `read_only` |

### Ruleset

`default_ruleset` maps each group to its profile:

| If group is | → Apply profile |
|-------------|-----------------|
| `tacacs_super_user` | `tacacs_super_user_profile` |
| `tacacs_read_only` | `tacacs_read_only_profile` |
| *(no match)* | deny |

### Authorization Flow

```
Network device → user_admin authenticates
  ↓
tac_plus-ng: member = tacacs_super_user
  ↓
default_ruleset: group == tacacs_super_user → tacacs_super_user_profile
  ↓
service == shell → return priv-lvl=15
  ↓
Device grants full admin access
```

### Next Steps After First Login

1. Change `user_admin` and `user_read_only` passwords (**TACACS Users → Edit**)
2. Add your network devices (**Hosts → Add Host**)
3. Generate and activate the config (**TACACS Configs → Generate → Activate**)
4. Configure your devices to point at this TACACS+ server

---

## Core Concepts

Understanding how tacacs-ng-ui maps to a TACACS+ config:

| Concept | What it does |
|---------|-------------|
| **TACACS User** | A network device user (the person logging into a router/switch) |
| **TACACS Group** | A group that users belong to; policies are applied to the group |
| **Host** | A network device (router, switch, firewall) that authenticates against the TACACS+ server |
| **Profile** | Defines what attributes (service, privilege level) are returned in an authorization response |
| **Ruleset** | Conditional access rules — permits or denies based on user/group/service/command |
| **TACACS Config** | The generated configuration file loaded by the `tac_plus-ng` daemon |
| **MAVIS** | An external authentication backend (e.g., LDAP/AD) used instead of local passwords |

> **Reminder:** After modifying any of the above, always regenerate and activate the config. See [Generating and Applying Config Files](#generating-and-applying-config-files).

---

## Step-by-Step: First-Time Setup

Follow this order when configuring from scratch:

### 1. Configure Server Settings

Go to **TACACS-NG Settings** and set:
- IPv4 address and port (default: `0.0.0.0`, port `49`)
- Log file paths for authentication, authorization, and accounting
- Authentication/user backends (`local`, `mavis`, `pap`, etc.)

### 2. Create TACACS Groups

Go to **TACACS Groups** → **Add Group**.
- Example groups: `network-admins`, `read-only-ops`

### 3. Create TACACS Users

Go to **TACACS Users** → **Add User**.
- Set `username`, `password`, `password_type` (`pap`), and assign to a group.

### 4. Create Profiles (Authorization Attributes)

Go to **Profiles** → **Add Profile**.
- Set `action` to `permit` or `deny`.
- Add **Profile Scripts** to return key-value pairs to devices (e.g., `service=exec`, `priv-lvl=15`).

### 5. Create Rulesets (Access Control)

Go to **Rulesets** → **Add Ruleset**.
- Define conditional rules that match users/groups/services and map them to profiles.
- Add **Ruleset Scripts** with conditions (e.g., `$user == "admin"`, `$nas == "192.168.1.1"`).

### 6. Add Network Devices (Hosts)

Go to **Hosts** → **Add Host**.
- Set the device IP address and `secret_key` (must match what is configured on the device).

### 7. Generate and Activate Config

> **⚠️ This step is required after EVERY configuration change.**

Go to **TACACS Configs** → **Generate Config** → mark the new config as **Active**.

![TACACS Config Generator](../../img/dashboard-tacacs-config.png)

### 8. Configure Network Devices

Point your routers/switches at the TACACS+ server. See [device examples](#typical-device-side-configuration).

---

## Managing TACACS+ Users & Groups

### TACACS Groups

**Path:** Sidebar → TACACS Groups

![TACACS Groups](../../img/tacacs-groups.png)

| Field | Description |
|-------|-------------|
| `group_name` | Unique name for the group (e.g., `network-admins`) |
| `description` | Optional description |

Groups are referenced in TACACS Users and Rulesets to apply policies to multiple users at once.

### TACACS Users

**Path:** Sidebar → TACACS Users

![TACACS Users](../../img/tacacs-users.png)

| Field | Description |
|-------|-------------|
| `username` | Login name used on network devices |
| `password` | User's password (stored hashed) |
| `password_type` | Protocol for password exchange — typically `pap` |
| `member` | Group this user belongs to |
| `description` | Optional description |

**Notes:**
- `password_type: pap` is the most common. Use `login` for ASCII auth.
- Users inherit policies from their group via Rulesets.

> **After adding/editing users:** regenerate and activate config.

---

## Configuring Network Devices (Hosts)

**Path:** Sidebar → Hosts

![Hosts](../../img/hosts.png)

| Field | Description |
|-------|-------------|
| `name` | Identifier for the host (e.g., `core-switch-01`) |
| `ipv4_address` | Device IP address (used to match TACACS requests) |
| `ipv6_address` | Optional IPv6 address |
| `secret_key` | Shared secret — must match the device's TACACS key config |
| `parent` | Optional parent host for inheriting settings |
| `welcome_banner` | Message sent to the user on successful login |
| `reject_banner` | Message sent on denied access |
| `motd_banner` | Message of the day shown after login |
| `failed_authentication_banner` | Message sent on failed authentication |

> **After adding/editing hosts:** regenerate and activate config.

### Typical Device-Side Configuration

**Cisco IOS / IOS-XE:**
```bash
! 1. Enable AAA first (must be before tacacs server block)
aaa new-model

! 2. Define the TACACS+ server
tacacs server MY-TACACS
  address ipv4 <TACACS_SERVER_IP>
  key <secret_key>
  exit

! 3. Create a named server group (allows easy failover/redundancy)
aaa group server tacacs+ TACACS-GROUP
  server name MY-TACACS
  exit

! 4. Authentication, Authorization, Accounting
aaa authentication login default group TACACS-GROUP local
aaa authorization exec default group TACACS-GROUP local
aaa accounting exec default start-stop group TACACS-GROUP
aaa accounting commands 15 default start-stop group TACACS-GROUP

! 5. Apply to VTY lines (SSH/Telnet) — required or TACACS won't be used
line vty 0 4
  login authentication default
  exit
```

**Juniper JunOS:**
```bash
# 1. Define local user classes that TACACS users will be mapped to
set system login class tacacs-admin permissions all
set system login class tacacs-read permissions [ view view-configuration ]
set system login user user_demo uid 9999 class tacacs-admin

# 2. Configure TACACS+ server (source-address = management interface IP)
set system tacplus-server <TACACS_SERVER_IP> port 49 secret <secret_key>
set system tacplus-server <TACACS_SERVER_IP> source-address <DEVICE_MGMT_IP>

# 3. Set authentication order (TACACS first, local password fallback)
set system authentication-order tacplus
set system authentication-order password

# 4. Enable accounting
set system accounting events login
set system accounting events interactive-commands
set system accounting destination tacplus server <TACACS_SERVER_IP> secret <secret_key>
set system accounting destination tacplus server <TACACS_SERVER_IP> source-address <DEVICE_MGMT_IP>
```

**Arista EOS:**
```bash
# 1. Define TACACS+ server (key 7 = encrypted; key 0 = plaintext, avoid in production)
tacacs-server host <TACACS_SERVER_IP> key 7 <encrypted_secret_key>

# 2. Create a named server group
aaa group server tacacs+ TACACS-GROUP
   server <TACACS_SERVER_IP>
!

# 3. Authentication, Authorization, Accounting
aaa authentication login default group TACACS-GROUP local
aaa authorization exec default group TACACS-GROUP local
aaa authorization commands all default group TACACS-GROUP local
aaa accounting exec default start-stop group TACACS-GROUP

# 4. Source TACACS traffic from management interface
ip tacacs source-interface Management0
```

---

## Access Control: Profiles & Rulesets

### Profiles

**Path:** Sidebar → Profiles

![Profiles](../../img/profiles.png)

Profiles define the **authorization response** sent back to a device when access is granted.

| Field | Description |
|-------|-------------|
| `name` | Profile identifier |
| `action` | `permit` or `deny` |
| `description` | Optional description |

#### Profile Scripts

Add attribute-value pairs returned to the device in the authorization response.

**Path:** Profiles → select profile → Profile Scripts

| Field | Description |
|-------|-------------|
| `condition` | Optional condition expression (e.g., `$user == "admin"`) |
| `key` | Attribute name (e.g., `priv-lvl`, `service`) |
| `value` | Attribute value (e.g., `15`, `exec`) |
| `action` | `set`, `add`, or `optional` |

**Example — Grant full privilege to admins:**
```
key: service     value: exec
key: priv-lvl    value: 15
```

**Example — Read-only access:**
```
key: service     value: exec
key: priv-lvl    value: 1
```

#### Profile Script Sets

Sub-parameters for a profile script entry (used for service-level attributes like `cmd` authorization).

### Rulesets

**Path:** Sidebar → Rulesets

![Rulesets](../../img/rulesets.png)

Rulesets define **which users get which profile** based on conditions.

| Field | Description |
|-------|-------------|
| `name` | Ruleset identifier |
| `enabled` | `yes` or `no` — toggle without deleting |
| `action` | Default action if no script matches: `permit` or `deny` |
| `description` | Optional description |

#### Ruleset Scripts

Add conditional rules within a ruleset.

**Path:** Rulesets → select ruleset → Ruleset Scripts

| Field | Description |
|-------|-------------|
| `condition` | Match expression (e.g., `$user == "admin"`, `$group == "network-admins"`) |
| `key` | Attribute to set in response |
| `value` | Attribute value |
| `action` | `permit`, `deny`, or `set` |

**Common condition variables:**
- `$user` — TACACS username
- `$group` — User's group
- `$nas` — NAS (device) IP address
- `$service` — Requested service (e.g., `shell`, `exec`)
- `$protocol` — Protocol (e.g., `telnet`, `ssh`)

**Example ruleset logic:**
```
condition: $group == "network-admins"   action: permit   key: priv-lvl   value: 15
condition: $group == "read-only"        action: permit   key: priv-lvl   value: 1
default action: deny
```

> **After adding/editing profiles or rulesets:** regenerate and activate config.

---

## Server Settings

**Path:** Sidebar → TACACS-NG Settings

![TACACS-NG Settings](../../img/tacacs-ng-settings.png)

| Field | Description |
|-------|-------------|
| `ipv4_enabled` | Enable IPv4 listener |
| `ipv4_address` | Bind address (use `0.0.0.0` to listen on all interfaces) |
| `ipv4_port` | TACACS+ port (default: `49`) |
| `ipv6_enabled` | Enable IPv6 listener |
| `ipv6_address` | IPv6 bind address |
| `ipv6_port` | IPv6 TACACS+ port |
| `instances_min` | Minimum server process instances |
| `instances_max` | Maximum server process instances |
| `background` | Run server in background (`yes`/`no`) |
| `access_logfile_destination` | Path pattern for access logs (e.g., `/var/log/tacacs/%Y/%m/%d/access.log`) |
| `authentication_logfile_destination` | Path for authentication logs |
| `authorization_logfile_destination` | Path for authorization logs |
| `accounting_logfile_destination` | Path for accounting logs |
| `login_backend` | Backend for login auth (`local`, `mavis`) |
| `user_backend` | Backend for user lookups |
| `pap_backend` | Backend for PAP auth |

Log path patterns support `strftime` format — `%Y/%m/%d` creates daily log rotation.

> **After changing server settings:** regenerate and activate config.

---

## Generating and Applying Config Files

**Path:** Sidebar → TACACS Configs

> ### ⚠️ CRITICAL — MUST DO AFTER EVERY CHANGE
>
> Changes to users, groups, hosts, profiles, rulesets, MAVIS, or server settings have **no effect** on the live TACACS+ server until you regenerate and activate the config.

![TACACS Config](../../img/tacacs_config.png)

### Workflow: Generate → Preview → Activate

The page follows a three-step workflow. Each config snapshot is versioned and can be inspected before being promoted.

**Step 1 — Generate Config**

Click **Generate Config** to build a complete `tac_plus-ng` config from all current settings. A dialog asks for a filename and optional description; defaults are pre-filled with the current timestamp.

**Step 2 — Preview Config**

Click **Preview Config** to see what the next generated config would look like without saving it. Useful for reviewing changes before committing.

**Step 3 — Activate**

In the config table, open the Actions menu for any snapshot and select **Activate** to mark it as the live config. The active row is highlighted in green with an **Active** badge.

**Active Config button**

Click **Active Config** to view the currently running configuration file in a syntax-highlighted modal.

![TACACS Config](../../img/tacacs_config.png)

### Config Table

| Column | Description |
|--------|-------------|
| Filename | Config snapshot name — click to view file contents |
| Status | Active (green) or Inactive (gray) |
| Description | Optional description set at generation time |
| Created At | Date and time the snapshot was generated |
| Actions | Activate / Delete |

### Config Reload

After activating, the `tac_plus-ng` daemon picks up the changes. In Docker deployments, the config file is written to the `/app/tacacs_config/` volume shared with the TACACS+ server container.

### Viewing TACACS Logs

**Path:** Sidebar → TACACS Logs

View TACACS+ log events. Use the **Events** tab for a structured, filterable view (see [TACACS Log Events Viewer](#tacacs-log-events-viewer)).

---

## Dashboard Overview

**Path:** Sidebar → Dashboard

The dashboard provides a real-time summary of your TACACS+ environment across four sections.

### Today's Log Summary

Three stat cards pulled directly from live TACACS+ log files:

| Card | Metrics |
|------|---------|
| **Authentication** | ✓ Successful logins / ✗ Failed logins today |
| **Authorization** | ✓ Permit decisions / ✗ Deny decisions today |
| **Accounting** | ▶ Session starts / ■ Session stops today |

Click any card to jump to the TACACS Log Events viewer for detailed records.

### Config Overview

Five clickable count cards showing current entity totals:

| Card | Navigates to |
|------|-------------|
| Hosts | `/hosts` |
| TACACS Users | `/tacacs_users` |
| TACACS Groups | `/tacacs_groups` |
| Profiles | `/profiles` |
| Rulesets | `/rulesets` |

### Recent User Activity

Compact table of the last 10 audit log entries — shows Time, Dashboard User, Action (color-coded badge), Entity type, and Description. Click **View all →** to open the full Audit Logs page.

### Top 5 & AAA Trend

Four pie charts (Top 5 Source IPs, Top 5 NAS IPs, Top 5 Auth Users, Top 5 Authz Users) and a six-series trend line chart (auth success/fail, authz permit/deny, acct start/stop).

**Filter bar** (above the charts):

| Option | Period |
|--------|--------|
| Last 7 Days | Rolling 7-day window ending today |
| Last 30 Days | Rolling 30-day window ending today |
| Date Range | Custom start and end date inputs |

Default is **Last 7 Days**. All options query the database statistics endpoint; data is updated nightly by the statistics batch job.

---

## TACACS Log Events Viewer

**Path:** Sidebar → TACACS Logs → Events tab

Browse and search structured TACACS+ log events parsed from raw log files.

### Filters

| Filter | Options |
|--------|---------|
| Date | Date picker (defaults to today) |
| Type | All / Authentication / Authorization / Accounting |
| Result | All / Success / Failed / Permit / Deny / Start / Stop |
| Username | Free-text search |

### Event Table Columns

| Column | Description |
|--------|-------------|
| Timestamp | Date and time of the event |
| Type | Authentication / Authorization / Accounting (color badge) |
| Result | Success / Failed / Permit / Deny / Start / Stop (color badge) |
| Username | TACACS username |
| NAS IP | Network device IP address |
| Message | Raw log message |

Results are paginated. Use the date picker and filters to narrow down to specific events.

---

## SIEM Integration

tacacs-ng-ui can forward TACACS+ log events in real-time to external security platforms.

### Configuration (`.env`)

```bash
# Enable SIEM forwarding
SIEM_FORWARD_TACACS_EVENTS=true

# HTTP Webhook (Splunk HEC format)
SIEM_WEBHOOK_URL=https://splunk.example.com:8088/services/collector/event
SIEM_WEBHOOK_TOKEN=your-hec-token

# Syslog (UDP or TCP)
SIEM_SYSLOG_HOST=syslog.example.com
SIEM_SYSLOG_PORT=514
SIEM_SYSLOG_PROTOCOL=udp   # or tcp
```

### Webhook Payload (Splunk HEC format)

```json
{
  "time": 1714012800,
  "event": {
    "timestamp": "2026-04-25T10:30:00Z",
    "type": "authentication",
    "result": "success",
    "username": "admin",
    "nas_ip": "192.168.1.1",
    "message": "..."
  }
}
```

Events are forwarded asynchronously — TACACS+ authentication is not blocked if the SIEM endpoint is unavailable.

### Supported Integrations

| Platform | Method |
|----------|--------|
| Splunk | HTTP Event Collector (HEC) webhook |
| Elastic / Logstash | HTTP webhook or syslog input |
| Graylog | GELF HTTP or syslog UDP/TCP |
| Any syslog receiver | UDP or TCP syslog |

---

## Monitoring & Statistics

### AAA Statistics (Today)

**Path:** Sidebar → AAA Statistics

![AAA Statistics](../../img/aaa-statistics.png)

Shows today's totals:
- Authentication success/failure counts
- Authorization permit/deny counts
- Accounting start/stop events
- 7-day trend charts

In a multi-node HA deployment a **Node** dropdown appears at the top right. Select a specific node to view only that node's statistics, or leave it on **All Nodes** to see aggregated totals across all nodes.

### AAA Statistics Range

**Path:** Sidebar → AAA Range Stats

Select a custom date range to view aggregated statistics. In multi-node deployments a **Node** dropdown filters the charts to a single node.

### Node Comparison

**Path:** Sidebar → Node Comparison

Side-by-side comparison of all TACACS-NG nodes over a selected date range. Each node appears as a card showing:
- Authentication success / failure totals
- Authorization permit / deny totals
- Accounting start / stop totals
- Per-node trend chart (AreaChart)
- Top 3 users by success and by failure

The date range picker at the top applies to all node cards simultaneously. Cards load in parallel — each node's data is fetched independently.

> **Multi-node setup required.** This page shows "No node statistics found" on a single-node deployment until statistics have been collected. Run `POST /api/v1/aaa_statistics/run/` or wait for the nightly cron job.

### Authentication Statistics

**Path:** Sidebar → Authentication Statistics

![Authentication Statistics](../../img/aaa-statistics.png)

Per-user, per-device breakdown of authentication events (success/failure counts).

### Authorization Statistics

**Path:** Sidebar → Authorization Statistics

![Authorization Statistics](../../img/aaa-statistics.png)

Per-user breakdown of authorization decisions (permit/deny counts).

### Accounting Statistics

**Path:** Sidebar → Accounting Statistics

![Accounting Statistics](../../img/aaa-statistics.png)

Per-user session accounting (start/stop event counts).

### TACACS Statistics

**Path:** Sidebar → TACACS Statistics

Server-wide performance and request statistics.

---

## Audit Logs

**Path:** Sidebar → Audit Logs

![Audit Logs](../../img/audit-logs.png)

Every configuration change made through the UI is recorded:

| Field | Description |
|-------|-------------|
| `action` | `create`, `update`, `delete` |
| `entity_type` | What was changed (e.g., `TacacsUser`, `Host`) |
| `entity_id` | UUID of the changed record |
| `user_email` | Dashboard user who made the change |
| `ip_address` | IP address of the user's browser |
| `old_values` | Snapshot before the change |
| `new_values` | Snapshot after the change |
| `timestamp` | When the change occurred |

Use audit logs to track who changed what and when — essential for compliance and troubleshooting.

---

## Application User Management

These are users who log into the **dashboard** (not TACACS device users).

**Path:** Sidebar → Admin → Users Management (superuser only)

![Users Management](../../img/users-management.png)

| Field | Description |
|-------|-------------|
| `email` | Login email |
| `full_name` | Display name |
| `is_active` | Activate or deactivate the account |
| `is_superuser` | Grant full admin access |
| `password_login_disabled` | Force OAuth/Passkey login only (disable password) |

### Auth Providers

**Path:** Sidebar → Admin → Auth Providers

![Auth Providers](../../img/auth-providers.png)

Configure which authentication methods are enabled for the dashboard:

| Provider | Configuration |
|----------|--------------|
| `google` | Requires `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` in `.env` |
| `keycloak` | Requires Keycloak server URL, client ID, and client secret |
| `passkeys` | WebAuthn — no extra config required; users register passkeys from their profile settings |

### Password Recovery

Users can request a password reset email from the login page. Requires SMTP configured in `.env` (`SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `EMAILS_FROM_EMAIL`).

### User Account Settings

**Path:** Sidebar → Settings

Each user can:
- Update their name and email
- Change their password
- Register or remove passkeys

---

## Advanced: MAVIS Backends

**Path:** Sidebar → Mavises

![Mavises](../../img/mavises.png)

MAVIS (Modular AAA Via Integrated Scripts) allows `tac_plus-ng` to delegate authentication to external systems (LDAP, Active Directory, etc.).

| Field | Description |
|-------|-------------|
| `mavis_key` | MAVIS configuration directive |
| `mavis_value` | Value for the directive |

Use **Preview** to see the MAVIS config block that will be generated.

Typical use case: authenticate TACACS users against Active Directory via LDAP MAVIS module instead of local passwords.

> **After changing MAVIS settings:** regenerate and activate config.

---

## Advanced: Custom Configuration Options

**Path:** Sidebar → Configuration Options

![Configuration Options](../../img/configuration-options.png)

Inject raw `tac_plus-ng` configuration blocks that are not covered by the UI fields.

| Field | Description |
|-------|-------------|
| `name` | Label for this config block |
| `config_option` | Raw configuration text (appended to generated config) |
| `description` | Optional description |

Use this for advanced directives like custom ACLs, time-based access controls, or any `tac_plus-ng` feature not exposed in the UI.

> **After adding custom options:** regenerate and activate config.

---

## Troubleshooting

| Symptom | Check |
|---------|-------|
| Device cannot authenticate | Verify `secret_key` matches on both Host and device config; verify config was regenerated and activated |
| Changes not taking effect | **Regenerate and activate config** — this is the most common cause |
| Authentication succeeds but no exec shell | Ensure profile returns `service=exec` and `priv-lvl` attribute |
| User not in group policy | Confirm user's `member` field matches exact group name |
| No logs appearing | Check `accounting_logfile_destination` path and directory permissions |
| 401/403 on dashboard | Token expired — log out and back in |
| Config syntax error | Check TACACS Logs for `tac_plus-ng` error output |

---

## Quick Reference: Typical Workflow

```
1. Server Settings        → set IP, port, log paths
2. TACACS Groups          → create groups (e.g., admins, read-only)
3. TACACS Users           → create users, assign to groups
4. Profiles               → define auth response (priv-lvl, service)
5. Profile Scripts        → add key-value attributes to profile
6. Rulesets               → map users/groups to profiles via conditions
7. Hosts                  → add devices with IP and secret key
8. ⚠️  TACACS Configs     → GENERATE CONFIG → mark ACTIVE  ← REQUIRED AFTER EVERY CHANGE
9. Device Config          → configure device to point at TACACS+ server
10. Monitor               → use Statistics and Logs to verify operation
```

---

## Useful Links

- TACACS+ Server: [tac_plus-ng](https://github.com/MarcJHuber/event-driven-servers)
- API Docs: `http://<your-host>:8000/docs` (also see screenshot below)
- Deployment Guide: [deployment.md](./deployment.md)
- Development Guide: [development.md](./development.md)
- Release Notes: [release-notes.md](./release-notes.md)
- Community: [Telegram](https://t.me/+v1eAXg-BhotlODY1) | [Reddit](https://www.reddit.com/r/tacacs_ng_ui/)

![API Docs](../../img/api.png)

