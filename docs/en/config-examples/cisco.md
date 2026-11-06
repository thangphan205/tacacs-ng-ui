# Cisco IOS-XE TACACS+ Integration Guide

This guide details how to integrate a Cisco device running IOS-XE with the `tacacs-ng-ui` server, including the required server-side configurations and device CLI commands.

Verified on Catalyst 9300 and ISR 4331 running IOS-XE 17.9.3. See the [Community Compatibility List](https://github.com/thangphan205/tacacs-ng-ui/discussions/185) for other tested devices.

---

## 1. TACACS+ Server-Side Configuration (tacacs-ng-ui)

> [!NOTE]
> The profiles, groups, users, and ruleset below are pre-seeded by `init_db` on first startup. No manual creation is needed unless you removed them.

IOS-XE requests **service `shell`**, and the privilege level of the session comes from the `priv-lvl` attribute returned by the server.

### A. Host
Under **Hosts**, add the device (or its subnet) with the shared secret it will use:

- **Name**: `cisco-c9300-01`
- **IPv4 Address**: `172.20.20.10/32`, the source IP the device really sends from (see [Source interface](#d-source-interface-and-vrf))
- **Secret Key**: `change_this`

> [!TIP]
> tac_plus-ng silently drops requests from unknown clients. If logins fail with no line in the logs, the device is using a different source IP than the one registered.

### B. Profiles
These profiles are pre-created under **Profiles**:

1. **`tacacs_super_user_profile` (Level 15 — full admin)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 15`

2. **`tacacs_read_only_profile` (Level 1 — read-only)**
   - **Default Action**: `deny`
   - **Profile Scripts**:
     - Condition: `if`, Key: `service`, Value: `shell` → Action: `permit`, Set: `priv-lvl = 1`

With these profiles the read-only restriction is enforced by the **device**: a level-1 session only runs level-1 commands, and `configure terminal` needs level 15. Protect `enable` with a strong `enable secret`, since anyone who knows it can raise their level. The server does not inspect individual commands. To have the server authorize each command too, see [Per-command authorization](#e-per-command-authorization-optional).

### C. Groups, Users & Ruleset
Pre-seeded:

- **Groups**: `tacacs_super_user` (level 15), `tacacs_read_only` (level 1)
- **Users**: `user_admin` → `tacacs_super_user`, `user_read_only` → `tacacs_read_only` (password type `crypt`, default password `change_this`)
- **Ruleset** `default_ruleset`: group `tacacs_super_user` → profile `tacacs_super_user_profile`; group `tacacs_read_only` → profile `tacacs_read_only_profile`

> [!WARNING]
> Change passwords for `user_admin` and `user_read_only` immediately after first login.

> [!IMPORTANT]
> Remember to go to **TACACS Configs** → **Generate Config** → **Activate** the configuration for these changes to take effect on the daemon.

---

## 2. Device-Side Configuration (Cisco IOS-XE)

> [!WARNING]
> The IP addresses and secrets used in the configuration below are examples. You **MUST** replace them with your own network details:
> - **TACACS+ Server IP (`192.168.139.3`)**: Replace this with your actual `tacacs-ng-ui` server IP address.
> - **Shared Secret (`change_this`)**: Replace this with the secret defined for the Host in `tacacs-ng-ui`.
> - **Source interface (`GigabitEthernet0/0`)**: Replace this with the interface whose IP you registered as the Host.

> [!CAUTION]
> Keep a second session open with a local account until every test below passes, and do not `write memory` before that. A `reload` brings back the saved config if you lock yourself out. Make sure a local fallback user exists:
> `username admin privilege 15 secret <local-password>`

### A. Enable AAA

```text
aaa new-model
```

### B. TACACS+ Server and Server Group

```text
tacacs server TACACS-NG-1
 address ipv4 192.168.139.3
 key 0 change_this
 timeout 5
!
aaa group server tacacs+ TACACS-GROUP
 server name TACACS-NG-1
```

For a second (HA) server, define `tacacs server TACACS-NG-2` the same way and add `server name TACACS-NG-2` to the group. Servers are tried in the order they are listed.

### C. Authentication, Authorization and Accounting

```text
! Log in with TACACS+, fall back to local accounts only if no server answers
aaa authentication login default group TACACS-GROUP local
! Ask the server for the session privilege level (priv-lvl)
aaa authorization exec default group TACACS-GROUP local
! Session start/stop and every command run at level 1 and 15
aaa accounting exec default start-stop group TACACS-GROUP
aaa accounting commands 1 default start-stop group TACACS-GROUP
aaa accounting commands 15 default start-stop group TACACS-GROUP
!
line vty 0 4
 login authentication default
 authorization exec default
```

The `local` fallback is used only when **no server answers**. A user rejected by the server is not retried against the local database.

### D. Source Interface and VRF

The device must send TACACS+ from the IP registered as the Host. Set it inside the server group:

```text
aaa group server tacacs+ TACACS-GROUP
 ip tacacs source-interface GigabitEthernet0/0
```

On Catalyst 9000 switches the management port `GigabitEthernet0/0` lives in `Mgmt-vrf`. If the server is reached through it, add the VRF to the group as well:

```text
aaa group server tacacs+ TACACS-GROUP
 ip vrf forwarding Mgmt-vrf
 ip tacacs source-interface GigabitEthernet0/0
```

### E. Per-command Authorization (optional)

To have the server authorize every level-15 command:

```text
aaa authorization commands 15 default group TACACS-GROUP local
aaa authorization config-commands
!
line vty 0 4
 authorization commands 15 default
```

Each request arrives as `service = shell` with the command line in `cmd`. The seeded profiles answer `permit` to **any** `service = shell` request, so they permit every command. To restrict commands on the server, create a profile in **Raw script** mode that separates the session start (`cmd == ""`) from commands, and point the ruleset's read-only rule at it:

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

Add the branches for any other vendor that uses the same profile (for example `if (service == junos-exec) { set local-user-name = tacacs_read_only permit }`) before the final `deny`. Press **Check with tac_plus-ng** before saving.

---

## 3. Verification

Run these from a second session while the first one stays open:

1. `user_admin` logs in and lands in privileged exec (`#` prompt), and can enter `configure terminal`.
2. `user_read_only` logs in at level 1 (`>` prompt): `show version` works, `configure terminal` is rejected.
3. A local account is refused while the TACACS+ server is reachable.
4. `show tacacs` shows the server with increasing packet counters.
5. In tacacs-ng-ui, the logins and commands appear under **Log Events** with the expected source IP.

Useful debug commands: `debug tacacs`, `debug aaa authentication`, `debug aaa authorization`, `test aaa group TACACS-GROUP user_admin change_this new-code`.

---

## 4. Full Reference Configuration

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

After the tests pass: `write memory`.
