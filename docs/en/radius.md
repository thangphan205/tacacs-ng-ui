# RADIUS

Some network devices can't use TACACS+ and offer only RADIUS for administrator logins. MikroTik RouterOS is one, and so are many wireless controllers and small firewalls. tacacs-ng-ui can serve RADIUS to them from the same tac_plus-ng server, with the same users, groups, profiles and rulesets.

RADIUS is **off by default**. While it is off, the generated config contains no RADIUS at all: no listener, no dictionary and no RADIUS secrets.

---

## How it works

- **Same server, extra listeners.** tac_plus-ng itself speaks RADIUS. When RADIUS is enabled, the generated config adds UDP listeners on the authentication port (1812) and the accounting port (1813), next to TACACS+ on 49.
- **Shared policy.** A RADIUS login is matched against the same users, the same rulesets and the same profiles as a TACACS+ login. A profile tells the two protocols apart with `aaa.protocol`, and returns RADIUS attributes such as `MikroTik-Group` instead of TACACS+ attributes such as `priv-lvl`.
- **One secret per device.** RADIUS uses its own shared secret, set per host (**RADIUS Secret**). The server answers RADIUS only for hosts that have one, either their own or one inherited from a parent host. A host may have a TACACS+ key, a RADIUS secret, or both. A host with no TACACS+ key of its own or from a parent gets an internal one that no device knows, so it can't be used to log in over TACACS+ (tac_plus-ng would otherwise accept cleartext TACACS+ from a host without a key).
- **Same logs.** RADIUS logins and accounting are written into the same authentication and accounting log files as TACACS+. Statistics, alert rules, anomaly detection and SIEM forwarding count them without extra setup. The Events tab marks RADIUS lines with a **RADIUS** badge, and SIEM events carry `protocol=radius`.

What it does not do:

- **No RadSec or DTLS.** RADIUS runs over plain UDP only.
- **CHAP and MS-CHAP need password type `clear`.** A user with password type `crypt` (a SHA-512 hash, the default) can sign in with **PAP only**. CHAP and MS-CHAP prove the password without sending it, so the server must hold it in cleartext. For a user with password type `clear`, the generated config also adds `password chap` and `password ms-chap` lines. **MikroTik RouterOS logs users in with MS-CHAPv2** (verified on RouterOS 7.25.1), so users who log in to MikroTik devices need password type `clear`. A `clear` password is stored as plain text in the database and the generated config; audit logs and MCP output still redact it. It can't contain quotes, backslashes or line breaks, because it is written inside quotes in the config. The Events tab names the method each device used, for example `radius mschapv2 login succeeded`.

---

## Setup

### 1. Enable RADIUS

Go to **AAA Config → RADIUS** and check **Enable RADIUS**. The defaults are:

| Setting | Default |
|---|---|
| Authentication port (UDP) | 1812 |
| Accounting port (UDP) | 1813 |

`docker-compose.yml` publishes `1812/udp` and `1813/udp` from the backend container. If you change the ports in the UI, change those mappings to match.

On a fresh install you can enable RADIUS from the start with `RADIUS_ENABLED=true` in `.env`. That value is read on first startup only; after that the UI owns the setting.

> [!IMPORTANT]
> RADIUS identifies a device by its source address. The device's real address must reach the container. Docker on Linux keeps it for a device on another machine. Docker Desktop (macOS, Windows) rewrites it, so every device appears to come from the same internal address. So does Docker on Linux for a device running on the same host, for example a containerlab router: its requests arrive from the gateway of the `tacacs-ng-ui_default` network (e.g. `172.19.0.1`). The host entry must match that source address. The Events tab can't show it: its NAS column is the `NAS-IP-Address` the device reports about itself. A request from an address no host matches gets no answer and leaves no log line.

### 2. Give the device a RADIUS secret

Under **Hosts**, add the device or edit it, and fill in **RADIUS Secret**. A RADIUS-only device needs no TACACS+ **Secret Key**. Like the TACACS+ key, the secret can be inherited from a parent host.

Keys can't contain quotes, backslashes or line breaks.

### 3. Return RADIUS attributes from the profile

Open **Profiles**, then use the row menu → **Add RADIUS Attribute**. Pick a vendor attribute and enter its value, for example **MikroTik — user group** with value `full`.

This adds one profile script, or reuses the profile's existing one:

```
if (aaa.protocol == radius) {
    set radius[MikroTik:MikroTik-Group] = full
    permit
}
```

You can write the same script by hand under **Profile Scripts**:

- **Script:** Condition `if`, Key `aaa.protocol`, Value `radius`, Action `permit`.
- **Set:** Key `radius[MikroTik:MikroTik-Group]`, Value `full`.

The key and value fields suggest RADIUS attribute names while RADIUS is enabled. Quote any value that is not a single word, for example `"shell:priv-lvl=15"`.

Keep one RADIUS script per profile. tac_plus-ng stops at its `permit`, so a second `if (aaa.protocol == radius)` below it is never reached. Put all of the profile's RADIUS attributes on that one script.

If a profile has no RADIUS script, its fallback action decides the login. With a `permit` fallback the device accepts the login but receives no attributes, and falls back to its own default (on MikroTik, the `default-group`). Existing TACACS+ scripts such as `if (service == shell)` never match a RADIUS request: in RADIUS, `service` is the Service-Type, for example `Administrative-User`.

### 4. Generate and activate

Go to **TACACS Configs** → **Generate Config** → **Activate**. Until then the change is only in the database.

If RADIUS is disabled but some hosts have a RADIUS secret, the TACACS Configs page says so. The secrets are kept but not used.

---

## Attributes

The built-in dictionary covers the standard RADIUS attributes (RFC 2865, 2866, 2869 and 3162) and these vendors:

| Vendor | Attributes | Typical use |
|---|---|---|
| MikroTik | `MikroTik-Group`, `MikroTik-Rate-Limit`, `MikroTik-Address-List`, … | `MikroTik-Group` = RouterOS user group |
| Cisco | `Cisco-AVPair`, `Cisco-NAS-Port` | `Cisco-AVPair` = `"shell:priv-lvl=15"` |
| Juniper | `Juniper-Local-User-Name`, `Juniper-Allow-Commands`, … | local user template |
| Fortinet | `Fortinet-Access-Profile`, `Fortinet-Group-Name`, `Fortinet-Vdom-Name` | admin profile |
| Palo Alto | `PaloAlto-Admin-Role`, `PaloAlto-Admin-Access-Domain`, … | admin role |
| Aruba | `Aruba-Admin-Role`, `Aruba-User-Role`, … | management role |
| Huawei | `Huawei-Exec-Privilege` | privilege level 0-15 |
| Microsoft | MS-CHAP and MPPE attributes | MS-CHAP |

Refer to an attribute as `radius[Vendor:Attribute]` (vendor-specific) or `radius[Attribute]` (standard), for example `radius[Reply-Message]`.

### Custom dictionary

For another vendor, add its attributes under **AAA Config → RADIUS → Custom RADIUS Dictionary**:

```
radius.dictionary Ubiquiti 41112 {
    attribute Ubiquiti-Admin-Role 1 string
}
```

The format is `radius.dictionary <Vendor> <vendor id> { attribute <Name> <number> <type> }`. The types are `string`, `octets`, `integer`, `time`, `enum`, `address`, `ipaddr`, `ipv4addr`, `ipv6addr` and `vsa`. An `integer`, `time` or `enum` attribute may list named values in braces, as in `{ Read 1 Admin 2 }`. A vendor that does not use one-byte type and length fields adds `format = <type bytes>, <length bytes>` after the vendor id.

Only `radius.dictionary` blocks are accepted. Generate checks the result with `tac_plus-ng -P`.

---

## High availability

Standby nodes receive the RADIUS configuration with the rest of the config. Each node needs `1812/udp` and `1813/udp` published and open in its firewall. Add every node's address to the device's RADIUS servers.

---

## Troubleshooting

| Symptom | Check |
|---|---|
| The device gets no answer | Is RADIUS enabled, and the config generated and activated? Does the host's address match the address the request arrives from? Does the host have a RADIUS secret, its own or its parent's? Is the UDP port open? |
| The device reports a bad secret, or `denied (bad RADIUS secret)` appears in the logs | The secret differs between the device and the host. |
| `radius chap login failed` or `radius mschapv2 login failed` for a password you know is right | The device uses CHAP or MS-CHAP, which a `crypt` (hashed) password can't answer. Set the user's password type to `clear` and re-enter the password, or switch the device to PAP if it allows that (RouterOS doesn't). |
| The login succeeds but has the wrong rights | The profile has no RADIUS script, or the attribute value doesn't match a group or role on the device. The Events tab shows the attributes that were returned at the end of the line. |

See also: [MikroTik RouterOS example](config-examples/mikrotik.md).
