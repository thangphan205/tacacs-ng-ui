# Ciena 6500 TACACS+ Integration Guide

This guide details how to integrate a **Ciena 6500 Packet-Optical Platform** network element (NE) with the `tacacs-ng-ui` server, using Site Manager or TL1. It covers the server-side configuration, the NE configuration and the checks to run afterwards.

> [!NOTE]
> Tested with Release 16.91 (`REL1691Z`) on about 190 NEs (2-slot, 7-slot and 14-slot shelves), both standalone shelves and consolidated nodes (TIDc, 2–5 shelves), against a 2-node `tacacs-ng-ui` HA deployment. Procedure numbers refer to the *6500 Administration and Security* guide for R16.91 (323-1851-301).

---

## 1. Key Facts: How the 6500 Talks TACACS+

| Topic | Behavior |
|---|---|
| **Service** | The NE requests **service `shell`**. There is no Ciena-specific service, so the pre-seeded profiles work as they are. |
| **Privilege** | `priv-lvl` is mapped to the 6500 user privilege codes (UPC 1–5) by thresholds configured on the NE (defaults `3 / 6 / 9 / 12 / 15`). With the defaults, `priv-lvl = 15` gives **UPC 5** (admin) and `priv-lvl = 1` gives **UPC 1** (read-only). |
| **Interfaces** | TACACS+ is selected per interface (TL1, CLI, ...). Site Manager logins use **TL1**. |
| **Source IP** | Selected by the **TACACS+ Client IP** attribute. Use `SHELF-IP` and register that IP as the host (see [Troubleshooting](#5-verification--troubleshooting)). |
| **Test request** | When TACACS+ is turned on, the NE sends a test request as user **`TACACSTEST`**. The server logs it as a failed/denied request; that is expected and confirms reachability and source IP. |
| **Local accounts** | With TL1 on TACACS+, local accounts of type **Super** still authenticate locally (before TACACS+). Every other local account is sent to the TACACS+ server. |
| **Per-command authorization** | Not needed. Keep it **disabled** (default) and use accounting for command logs. |
| **Consolidated nodes (TIDc)** | Configure the **primary shelf only**, with the TACACS+ proxy enabled. Member shelves reach the server through the primary. |

---

## 2. Server-Side Configuration (tacacs-ng-ui)

> [!NOTE]
> The profiles, groups, users, and ruleset below are pre-seeded by `init_db` on first startup. No manual creation is needed unless you removed them.

### A. Profiles
The pre-seeded profiles already return what the 6500 needs:

1. **`tacacs_super_user_profile`**: Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 15` (UPC 5 on the NE)
2. **`tacacs_read_only_profile`**: Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 1` (UPC 1 on the NE)

### B. Groups, Users & Ruleset
- **Groups**: `tacacs_super_user` (level 15) and `tacacs_read_only` (level 1).
- **Users**: `user_admin` (member of `tacacs_super_user`) and `user_read_only` (member of `tacacs_read_only`), or your directory users through MAVIS.
- **Ruleset**: `default_ruleset` permits both groups and attaches their respective profiles.

### C. Host Registration
Navigate to **Hosts** → **Add Host**, one host per NE:
- **Name**: the NE name (e.g., `CIENA-NE01`)
- **IPv4 Address / CIDR**: the **shelf IP** of the NE, as `/32` (e.g., `172.20.20.10/32`). On a consolidated node (TIDc), register **only the primary shelf**.
- **Secret Key**: the shared secret you will configure on the NE (e.g., `change_this`)
- **Parent Host** *(optional)*: with many NEs, create one parent host holding the shared secret and set it as the parent of every NE; a child without its own key inherits the parent's.

> [!IMPORTANT]
> Always navigate to **TACACS Configs** → **Generate Config** → **Activate** after adding hosts or changing rules.

---

## 3. Device-Side Configuration (Ciena 6500)

> [!WARNING]
> The IP addresses and secrets used below are examples. You **MUST** replace them with your own network details:
> - **TACACS+ Server IPs (`192.168.139.3`, `192.168.139.4`)**: your `tacacs-ng-ui` server(s). The 6500 accepts up to two servers.
> - **NE shelf IP (`172.20.20.10`)**: the shelf IP of the NE, the same IP registered as the host.
> - **Shared Secret (`change_this`)**: the secret defined for the host in `tacacs-ng-ui`.
> - **`NE01`**: the TID of the NE. **`SHELF-1`**: the shelf number of the NE (read it with `RTRV-MEMBER`; a standalone NE is not always shelf 1).

> [!CAUTION]
> **Do step 1 first, or your NMS loses the NE.** Once TL1 is switched to TACACS+, every local account that is **not** of type *Super* is authenticated against the TACACS+ server. The account your NMS (e.g., Ciena MCP / Navigator) uses does not exist there, so it is rejected: the NE drops out of NMS management, and the NMS retries can also trigger the NE's intrusion lockout. A *Super* account is checked locally **before** TACACS+, so the NMS keeps working with no change on its side. Do not create the NMS account on the TACACS+ server instead.

### Before You Start
- Log in to Site Manager with a local admin account and **keep that session open until the end**. It is your way back.
- Check that nobody is locked out: **Security → Intrusion Attempt Handling → Locked Out Users** must be empty *(Proc. 2-32)*.
- Write down the current values of the TACACS+ tab, the Alternate setting and the Authentication Mode, for rollback.
- **Do not test a non-Super local account while TACACS+ is on.** It is sent to TACACS+, rejected, and counted as an intrusion attempt.

### Option A: Site Manager

| Step | Site Manager path | Set |
|---|---|---|
| 1. NMS account as Super | Security → User Profile → *(NMS user)* → Edit → **User Type** tab | **Super** *(Proc. 2-3)* |
| 2. Servers | Security → Centralized Security Administration → *(Shelf)* → **TACACS+** tab → select SERVER1 / SERVER2 → **Edit Server** | Status **Enable**, IP Address, Port **49**, Timeout **5**, Shared Secret *(Proc. 2-47)* |
| 3a. Attributes (TACACS+ still **Off**) | same **TACACS+** tab → **Edit** | TACACS+ Client IP **SHELF-IP**, Accounting Status **Enable for UPC2+ commands**, Authorization Status **Disable**, UPC 1–5 Privilege Code **3 / 6 / 9 / 12 / 15** (default), TACACS+ Proxy **Disable** (**Enable** on a TIDc primary shelf) → OK *(Proc. 2-48)* |
| 3b. Turn on | same **TACACS+** tab → **Edit** again | TACACS+ Status **On** → OK *(Proc. 2-48)* |
| 4. Alternate | Security → Centralized Security Administration → **Edit** (below *Alternate*) | Alternate **Local** → OK *(Proc. 2-39)* |
| 5. TL1 via TACACS+ | Security → **Authentication Mode** → *(Shelf)* → Refresh | TL1 Authentication Mode **TACACS+**; leave Default and CLI as they are *(Proc. 2-37)* |

> [!TIP]
> Site Manager's **Tools → CommLog** shows the exact TL1 each dialog sends (the secret is masked). The TL1 below was taken from it.

### Option B: TL1

**Step 1: NMS account as Super** (authenticates locally before TACACS+)
```text
ED-SECU-USER:NE01:<NMS_USER>:CTAG::,,,<UPC>:USERTYPE=SUPER;
```

**Step 2: Servers** (the secret and its confirmation are the two positional fields)
```text
SET-TACACS-SRVR:NE01:SERVER-1-1:CTAG::"change_this","change_this":STATE=ENABLE,IPADDR=192.168.139.3,TMOUT=5;
SET-TACACS-SRVR:NE01:SERVER-1-2:CTAG::"change_this","change_this":STATE=ENABLE,IPADDR=192.168.139.4,TMOUT=5;
```

**Step 3a: Source IP and accounting, while TACACS+ is still OFF**
```text
SET-ATTR-TACACS:NE01:SHELF-1:CTAG:::IPIF=SHELF-IP,ACCT=ENABLE_UPC2_PLUS;
```

**Step 3b: Only now turn TACACS+ on**
```text
SET-ATTR-TACACS:NE01:SHELF-1:CTAG:::STATE=ENABLE;
```

**Step 4: Fall back to local accounts only if no server answers**
```text
SET-REMAUTH-ALTERNATE:NE01:SHELF-1:CTAG::LOCAL;
```

**Step 5: Use TACACS+ for TL1** (CLI can stay `DEFAULT`)
```text
SET-AUTH-MODE:NE01:SHELF-1:CTAG:::TL1=TACACS;
```

> [!IMPORTANT]
> Keep steps 3a and 3b separate. The test request is sent when TACACS+ is enabled, using the client IP saved at that moment. If both are changed in the same edit, the test still goes out with the old (`Auto`) source and fails.

### Consolidated Nodes (TIDc)
- Do **all** steps on the **primary shelf only** (the shelf with `PRIMARY=ENABLE` in `RTRV-SHELF`), and add `PROXY=ENABLE` to step 3a:
  ```text
  SET-ATTR-TACACS:NE01:SHELF-1:CTAG:::IPIF=SHELF-IP,ACCT=ENABLE_UPC2_PLUS,PROXY=ENABLE;
  ```
- The member shelves then configure themselves: their TACACS+ server points to the primary shelf (port `9003`), and all requests, including accounting of commands run on member shelves, reach the server from the **primary shelf IP**.
- Register only the primary shelf IP as a host in `tacacs-ng-ui`.

---

## 4. Full Reference Configuration

Software version details:

```text
RTRV-NETYPE:NE01::CTAG;

   "NE01" 26-11-03 23:08:36
M  CTAG COMPLD
   "CIENA,\"6500 OPTICAL\",CNE,\"REL1691Z.LQ\""
;
```

Complete TL1 sequence for a standalone NE (shelf 1), in order:

```text
ED-SECU-USER:NE01:<NMS_USER>:CTAG::,,,<UPC>:USERTYPE=SUPER;
SET-TACACS-SRVR:NE01:SERVER-1-1:CTAG::"change_this","change_this":STATE=ENABLE,IPADDR=192.168.139.3,TMOUT=5;
SET-TACACS-SRVR:NE01:SERVER-1-2:CTAG::"change_this","change_this":STATE=ENABLE,IPADDR=192.168.139.4,TMOUT=5;
SET-ATTR-TACACS:NE01:SHELF-1:CTAG:::IPIF=SHELF-IP,ACCT=ENABLE_UPC2_PLUS;
SET-ATTR-TACACS:NE01:SHELF-1:CTAG:::STATE=ENABLE;
SET-REMAUTH-ALTERNATE:NE01:SHELF-1:CTAG::LOCAL;
SET-AUTH-MODE:NE01:SHELF-1:CTAG:::TL1=TACACS;
```

---

## 5. Verification & Troubleshooting

### Check the NE Configuration
```text
RTRV-ATTR-TACACS:NE01:SHELF-1:CTAG;
   "SHELF-1::STATE=ENABLE,AUTHN=ENABLE,AUTHOR=DISABLE,ACCT=ENABLE_UPC2_PLUS,UPC1MPG=3,UPC2MPG=6,UPC3MPG=9,UPC4MPG=12,UPC5MPG=15,PROXY=DISABLE,IPIF=SHELF-IP"

RTRV-TACACS-SRVR:NE01:SERVER-1-1:CTAG:::EXINFO=N;
   "SERVER-1-1::STATE=ENABLE,TMOUT=5,IPADDR=\"192.168.139.3\",PORT=49"

RTRV-REMAUTH-ALTERNATE:NE01:SHELF-1:CTAG;
   "SHELF-1:LOCAL"

RTRV-AUTH-MODE:NE01:SHELF-1:CTAG;
   "SHELF-1::TL1=TACACS,CLI=DEFAULT,REST=DEFAULT,GRPC=DEFAULT,FTP=DEFAULT,NETCONF=DEFAULT"
```
Use `EXINFO=Y` on `RTRV-TACACS-SRVR` to see the request/error counters of each server.

### Test a Login
With the admin session from *Before You Start* still open:
1. Log in (Site Manager or TL1 `ACT-USER`) with a user that should be admin. A TACACS+ login answers with `/*AUTHTYPE=TACACS*/` and you get UPC 5.
2. Log in with a user outside the allowed groups: denied.
3. The NMS still manages/synchronizes the NE (its *Super* account authenticates locally).
4. In `tacacs-ng-ui` → **TACACS Logs**, the `TACACSTEST` request, the login and the accounting records show up from the NE's shelf IP.

`RTRV-AUDIT-SECULOG` on the NE shows the UPC granted to each login.

### Common Problems

| Symptom | Cause / Fix |
|---|---|
| Site Manager: *"Failed to contact TACACS+ Server 1 OR Server 2"* when turning TACACS+ on | The request left from another interface (a COLAN or other management interface) because TACACS+ Client IP was `Auto`, and `tac_plus-ng` dropped it as an unknown host. Set `IPIF=SHELF-IP` with TACACS+ **off**, then turn it on (steps 3a / 3b), and register the shelf IP as the host. |
| The NMS loses the NE right after TL1 goes to TACACS+ | The NMS account is not of type *Super*. Make it *Super* (step 1) and unlock it if needed. |
| A user or source is locked out after failed attempts | Security → Intrusion Attempt Handling → Locked Out Users → select → **Unlock**: *On-User Based → Unlock* for one user, *On-Source Based → Unlock All* for a source address such as the NMS *(Proc. 2-34)*. |
| `SET-ATTR-TACACS ... AUTHN=...` returns `IPNV` | `AUTHN` cannot be set directly: it follows `STATE`. Turning TACACS+ off sets `AUTHN=DISABLE`. |
| `RTRV-ATTR-TACACS` returns `ICNV` | Release 11.10 has no TACACS+ TL1 commands (only RADIUS and local). Upgrade the NE. Releases 12.x and 15.x were not tested. |
| *"Remote authentication service is unavailable"* for one user only | With a directory backend (MAVIS LDAP), an **expired** user password makes the server return an error with no line in the authentication log. Check the account in the directory. |

### Rollback
In this order: Authentication Mode TL1 = **Default** → Alternate back to its previous value → TACACS+ tab → Edit: Status **Off** (and Authorization back to its previous value) → SERVER1 / SERVER2 back to their previous values.
