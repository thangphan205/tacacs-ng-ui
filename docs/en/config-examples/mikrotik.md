# MikroTik RouterOS RADIUS Integration Guide

RouterOS doesn't support TACACS+, so router logins use RADIUS. This guide sets up `tacacs-ng-ui` and a RouterOS v7 device so that administrators log in with their tacacs-ng-ui accounts, and receive a RouterOS user group from their profile.

For how RADIUS works in tacacs-ng-ui, see [RADIUS](../radius.md).

---

## 1. Server side (tacacs-ng-ui)

### A. Enable RADIUS

**AAA Config → RADIUS** → check **Enable RADIUS**. Keep the default ports, 1812 (authentication) and 1813 (accounting).

### B. Add the router as a host

**Hosts → Add Host**:

- **Name:** `mikrotik-core-01`
- **IPv4 Address / CIDR:** the router's address as seen by the server, for example `192.0.2.1`, or a subnet such as `192.0.2.0/24` for several routers.
- **RADIUS Secret:** a long random secret. You will enter the same value on the router.
- **Secret Key:** leave empty. It is the TACACS+ key, which RouterOS doesn't use.

### C. Return a RouterOS group from the profiles

RouterOS assigns a logged-in RADIUS user the group named in the `MikroTik-Group` attribute. The built-in groups are `full`, `write` and `read`, and you can create your own under `/user group`.

On the **Profiles** page, use the row menu → **Add RADIUS Attribute** → **MikroTik — user group**:

| Profile | Value |
|---|---|
| `tacacs_super_user_profile` | `full` |
| `tacacs_read_only_profile` | `read` |

The demo data includes both profiles. Each profile then has this script:

```
if (aaa.protocol == radius) {
    set radius[MikroTik:MikroTik-Group] = full
    permit
}
```

Groups and rulesets need no changes. A user in `tacacs_super_user` gets the super-user profile and therefore `full`, just as their TACACS+ logins get privilege 15.

### D. Users: password type `clear`

RouterOS logs users in with **MS-CHAPv2** (verified with SSH logins on RouterOS 7.25.1). MS-CHAPv2 can only be checked against a cleartext password. For every user who logs in to MikroTik devices, open **Users**, set **Password Type** to `clear`, and enter the password again. A `crypt` user is refused (`radius mschapv2 login failed` in the Events tab), even with the right password.

> [!WARNING]
> A `clear` password is stored as plain text in the database and in the generated config. Use `clear` only for the accounts that need it, and keep `crypt` for TACACS+-only users. Audit logs and MCP output still redact it.

### E. Generate and activate

**TACACS Configs → Generate Config → Activate**.

---

## 2. Router side (RouterOS v7)

Replace `203.0.113.10` with the address of the tacacs-ng-ui server, and the secret with the host's RADIUS secret. In an HA setup, add one `/radius` entry for each node.

```
/radius
add service=login address=203.0.113.10 secret="RADIUS_SECRET" \
    authentication-port=1812 accounting-port=1813 timeout=3s

/user aaa
set use-radius=yes accounting=yes default-group=read
```

- **`service=login`** uses this RADIUS server for router logins (Winbox, SSH, WebFig, console).
- **`default-group=read`** applies when the server accepts a login but sends no `MikroTik-Group`. Keep it the least privileged group.
- **Local users still work.** RouterOS checks its local users first, then RADIUS. Keep one local admin account for when the server is unreachable.
- On RouterOS 7.15 and later, `/radius set [find] require-message-auth=yes-for-request-resp` makes the router refuse replies without a Message-Authenticator. tac_plus-ng includes one.

---

## 3. Verify

1. Log in to the router over SSH with a tacacs-ng-ui user whose password type is `clear`.
2. On the router, `/user active print` flags the session `R` (RADIUS). `/user print` doesn't list the user, because the account comes from RADIUS. A `read` user gets `not enough permissions` when trying to change the configuration.
3. In tacacs-ng-ui, **TACACS Logs → Events** shows the login with a **RADIUS** badge, for example `radius mschapv2 login succeeded  MikroTik:MikroTik-Group=full …`. With `accounting=yes`, start and stop records appear under accounting, plus an `on` record when the router starts.

If the Events line says `radius mschapv2 login failed` for a correct password, the user's password type is `crypt`; see step 1.D. If nothing appears at all, the request didn't match a host: check the address in the host entry against the address the router sends from. See [RADIUS → Troubleshooting](../radius.md#troubleshooting).
