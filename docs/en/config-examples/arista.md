# Arista EOS TACACS+ Integration Guide

This guide details how to integrate an Arista switch running EOS with the `tacacs-ng-ui` server, including the required server-side configurations and device CLI commands.

Verified on vEOS running EOS 4.28F. See the [Community Compatibility List](https://github.com/thangphan205/tacacs-ng-ui/discussions/185) for other tested devices.

---

## 1. TACACS+ Server-Side Configuration (tacacs-ng-ui)

> [!NOTE]
> The profiles, groups, users, and ruleset below are pre-seeded by `init_db` on first startup. No manual creation is needed unless you removed them.

EOS requests **service `shell`**. The `priv-lvl` attribute returned by the server sets the session privilege: `15` lands in privileged exec, lower levels in unprivileged exec.

### A. Host
Under **Hosts**, add the switch (or its subnet) with the shared secret it will use:

- **Name**: `arista-leaf-01`
- **IPv4 Address**: `172.20.20.20/32`, the source IP the switch really sends from (see [Source interface](#d-source-interface-and-vrf))
- **Secret Key**: `change_this`

> [!TIP]
> tac_plus-ng silently drops requests from unknown clients. If logins fail with no line in the logs, the switch is using a different source IP than the one registered.

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

## 2. Device-Side Configuration (Arista EOS)

> [!WARNING]
> The IP addresses and secrets used in the configuration below are examples. You **MUST** replace them with your own network details:
> - **TACACS+ Server IP (`192.168.139.3`)**: Replace this with your actual `tacacs-ng-ui` server IP address.
> - **Shared Secret (`change_this`)**: Replace this with the secret defined for the Host in `tacacs-ng-ui`.
> - **Source interface (`Management1`)**: Replace this with the interface whose IP you registered as the Host.

> [!CAUTION]
> Keep a second session open with a local account until every test below passes, and do not `write memory` before that. Command authorization (step C) applies to your own session as soon as it is entered, so a wrong key or an unreachable server can lock you out of the next command. Make sure a local fallback user exists:
> `username admin privilege 15 role network-admin secret <local-password>`
>
> On EOS you can also stage everything in a configuration session and apply it with `commit timer 00:10:00`, then `commit` again to confirm.

### A. TACACS+ Server

```text
tacacs-server host 192.168.139.3 key 0 change_this
tacacs-server timeout 5
```

For a second (HA) server, add another `tacacs-server host` line. Servers are tried in the order they are configured.

### B. Server Group

```text
aaa group server tacacs+ TACACS_GROUP
   server 192.168.139.3
```

### C. Authentication, Authorization and Accounting

```text
! Log in with TACACS+, fall back to local accounts only if no server answers
aaa authentication login default group TACACS_GROUP local
! Ask the server for the session privilege level (priv-lvl)
aaa authorization exec default group TACACS_GROUP local
! Ask the server before running each command
aaa authorization commands all default group TACACS_GROUP local
! Session start/stop and every command
aaa accounting exec default start-stop group TACACS_GROUP
aaa accounting commands all default start-stop group TACACS_GROUP
```

The `local` fallback is used only when **no server answers**. A user rejected by the server is not retried against the local database.

> [!WARNING]
> With `aaa authorization commands all`, each command arrives as `service = shell` with the command line in `cmd`. The seeded profiles answer `permit` to **any** `service = shell` request, so the server permits every command. The read-only user is then held back only by its unprivileged exec session. To restrict commands on the server too, see [Restricting commands on the server](#e-restricting-commands-on-the-server-recommended).

### D. Source Interface and VRF

The switch must send TACACS+ from the IP registered as the Host:

```text
ip tacacs source-interface Management1
```

If the server is reached through a management VRF (for example `MGMT`), put the VRF on the server, the group and the source interface:

```text
tacacs-server host 192.168.139.3 vrf MGMT key 0 change_this
!
aaa group server tacacs+ TACACS_GROUP
   server 192.168.139.3 vrf MGMT
!
ip tacacs vrf MGMT source-interface Management1
```

### E. Restricting Commands on the Server (recommended)

Create a profile in **Raw script** mode that separates the session start (`cmd == ""`) from commands, and point the ruleset's read-only rule at it:

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

1. `user_admin` logs in and lands in privileged exec (`#` prompt), and can enter `configure`.
2. `user_read_only` logs in unprivileged (`>` prompt): `show version` works, `configure` does not.
3. A local account is refused while the TACACS+ server is reachable.
4. `show tacacs` shows the server with increasing message counters.
5. In tacacs-ng-ui, the logins and commands appear under **Log Events** with the expected source IP.

---

## 4. Full Reference Configuration

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

After the tests pass: `write memory`.
