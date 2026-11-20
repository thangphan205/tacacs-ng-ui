# MikroTik RouterOS RADIUS Integration Guide

RouterOS doesn't support TACACS+, so router logins use RADIUS. This guide sets up `tacacs-ng-ui` and a RouterOS v7 device so that administrators log in with their tacacs-ng-ui accounts, and receive a RouterOS user group from their profile.

For how RADIUS works in tacacs-ng-ui, see [RADIUS](../radius.md).

---

## 1. Server side (tacacs-ng-ui)

### A. Enable RADIUS

**NG Settings → RADIUS** → check **Enable RADIUS**. Keep the default ports, 1812 (authentication) and 1813 (accounting).

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

Users, groups and rulesets need no changes. A user in `tacacs_super_user` gets the super-user profile and therefore `full`, just as their TACACS+ logins get privilege 15.

### D. Generate and activate

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

1. Log in to the router over SSH with a tacacs-ng-ui user, for example `user_admin`.
2. On the router, `/user active print` lists the session with the group from the profile. `/user print` doesn't list the user, because the account comes from RADIUS. A `read` user can't change the configuration.
3. In tacacs-ng-ui, **TACACS Logs → Events** shows the login with a **RADIUS** badge, for example `radius pap login succeeded  MikroTik:MikroTik-Group=full`. With `accounting=yes`, start and stop records appear under accounting.

If the Events line says `radius chap login` or `radius mschapv2 login` and fails, the router used CHAP or MS-CHAP. Local tacacs-ng-ui users have hashed passwords, which only PAP can check. See [RADIUS → Troubleshooting](../radius.md#troubleshooting).
