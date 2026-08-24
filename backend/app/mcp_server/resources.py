"""MCP resources and prompts.

The syntax reference is the highest-leverage item here: without it a model
reliably emits tac_plus (v4) syntax or invents directives that tac_plus-ng does
not accept. It documents exactly the grammar this application emits.
"""

from mcp.server.fastmcp import FastMCP
from sqlmodel import Session

from app.core.db import engine
from app.mcp_server import service

SYNTAX_REFERENCE = """\
# tac_plus-ng configuration syntax

This is the grammar tacacs-ng-ui generates. It is **tac_plus-ng** (Marc Huber's
event-driven-servers), *not* the older tac_plus v4 — directives differ.

## File skeleton

```
#!/usr/local/sbin/tac_plus-ng
id = spawnd {
    listen = {
        address = 0.0.0.0
        port = 49
    }
    spawn = {
        instances min = 1
        instances max = 10
    }
    background = no
}
id = tac_plus-ng {
    ... everything below goes here ...
}
```

Note `background` takes `yes`/`no`, not `true`/`false`.

## Logging

Declare a log target, then bind it to a stream. Both halves are required.

```
    log accesslog { destination = /var/log/tacacs/%Y/%m/access-%Y-%m-%d.log }
    log authenticationlog { destination = /var/log/tacacs/%Y/%m/authentication-%Y-%m-%d.log }
    log authorizationlog { destination = /var/log/tacacs/%Y/%m/authorization-%Y-%m-%d.log }
    log accountinglog { destination = /var/log/tacacs/%Y/%m/accounting-%Y-%m-%d.log }

    access log = accesslog
    authentication log = authenticationlog
    authorization log = authorizationlog
    accounting log = accountinglog
```

`%Y`, `%m`, `%d` are strftime expansions applied at write time.

## MAVIS backend (LDAP)

```
    mavis module = external {
        setenv LDAP_SERVER_TYPE="freeipa"
        setenv LDAP_HOSTS="ldaps://ipa.example.com:636"
        setenv LDAP_BASE="dc=example,dc=com"
        setenv LDAP_USER="uid=app_tacacs,cn=users,cn=accounts,dc=example,dc=com"
        setenv LDAP_PASSWD="..."
        setenv LDAP_FILTER="(&(objectClass=inetorgperson)(uid=%s))"
        setenv TACACS_GROUP_PREFIX="tacacs_"
        setenv REQUIRE_TACACS_GROUP_PREFIX="0"
        exec = /usr/local/lib/mavis/mavis_tacplus-ng_ldap.pl
    }

    login backend = mavis
    user backend = mavis
    pap backend = mavis
```

## Hosts (NAS clients)

```
    host = CORE_SWITCHES {
        address = 10.0.0.0/24
        key = "shared-secret"
    }
```

`address` accepts a single address or CIDR. `key` must be quoted.

## Groups

```
    group = tacacs_super_user
```

Bare declaration — group membership is asserted from the user side, or supplied
by MAVIS via the group prefix.

## Users

```
    user alice {
        password login = crypt "$6$rounds=656000$..."
        member = tacacs_super_user
    }
```

`password login` accepts `clear`, `des`, `crypt`, `mavis`, `permit`, `deny`.
With `mavis` there is no quoted argument:

```
    user bob {
        password login = mavis
        member = tacacs_read_only
    }
```

Note there is **no** `=` between `user` and the name — `user alice {`, not
`user = alice {`. Hosts and groups do use `=`.

## Profiles (authorization results)

```
    profile tacacs_super_user_profile {
        script {
            if (service==shell) {
                set priv-lvl=15
                permit
            }
            if (service==junos-exec) {
                set local-user-name=tacacs_super_user
                permit
            }
            deny
        }
    }
```

Conditions compare an attribute to a literal with `==`. `set k=v` assigns an
AV pair. The trailing `deny` is the fall-through. Common `service` values seen
in the field: `shell`, `junos-exec`, `h3c_shell`, `PaloAlto`, `fortigate`,
`nas_admin`.

## Rulesets (which profile applies)

All rules live inside a single `ruleset { }` block.

```
    ruleset {
        rule default_ruleset {
            enabled=yes
            script {
                if (group==tacacs_super_user) {
                    profile=tacacs_super_user_profile
                    permit
                }
                if (group==tacacs_read_only) {
                    profile=tacacs_read_only_profile
                    permit
                }
                deny
            }
        }
    }
```

Inside a rule script, assignments are bare `k=v` (e.g. `profile=...`), *not*
`set k=v` — that difference from profile scripts is a common mistake.

## Ordering

Within `id = tac_plus-ng { }` the generator emits, in order: logs, MAVIS,
backends, hosts, groups, users, profiles, ruleset.

## Validating

Syntax is checked with `tac_plus-ng -P <file>`. Use the `validate_config_text`
tool rather than guessing, and iterate until `status == "success"`.
"""

ENTITY_SCHEMA = """\
# Entity → config mapping

Every table below has a `generate_config` flag unless noted; rows with it unset
exist in the UI but are **not** emitted into the config.

| Entity | Fields that reach the config | Notes |
|---|---|---|
| `TacacsNgSetting` | `ipv4_address`, `ipv4_port`, `instances_min`, `instances_max`, `background`, the four `*_logfile_destination` | Singleton. `ipv6_*`, `login_backend`, `user_backend`, `pap_backend` and `timezone` are stored but **not** emitted — the backends are hardcoded to `mavis`. |
| `Mavis` | `mavis_key`, `mavis_value` → `setenv K="V"` | All rows, unfiltered. A `MAVIS_OVERRIDE_<key>` environment variable takes precedence over the stored value (used for per-zone LDAP servers in HA). |
| `Host` | `name`, `ipv4_address`, `secret_key` | `ipv6_address`, the four banner fields, `parent` and `description` are stored but **not** emitted. |
| `TacacsGroup` | `group_name` | Emits a bare `group = <name>`. |
| `TacacsUser` | `username`, `password_type`, `password`, `member` | `password_type == "mavis"` emits `password login = mavis` with no argument. |
| `Profile` | `name`, `action` (the fall-through verb) | Profiles with zero scripts are skipped entirely. |
| `ProfileScript` | `condition`, `key`, `value`, `action` | Scripts with zero sets are skipped. |
| `ProfileScriptSet` | `key`, `value` → `set k=v` | |
| `Ruleset` | `name`, `action` | `enabled` is stored but the generator always emits `enabled=yes`. |
| `RulesetScript` | `condition`, `key`, `value`, `action` | |
| `RulesetScriptSet` | `key`, `value` → bare `k=v` | |
| `ConfigurationOption` | `config_option` (raw text) | Escape hatch. `name` is unique and must be one of `host`, `group`, `user`, `profile`, `rule`; the text is passed through verbatim into that section. Treated as non-secret by redaction. |
| `TacacsService` | — | Has a `generate_config` flag but **no generator references it**. Currently inert. |

There are no ACL, realm, net or device-group entities in this application.

Secrets (`Host.secret_key`, `TacacsUser.password`, MAVIS credential values) are
masked in every tool response unless explicitly requested by a superuser key
holding the `mcp:secrets` scope.
"""

AUTHOR_PROMPT = """\
You are authoring a tac_plus-ng configuration for this TACACS+ deployment.

Follow this workflow and do not skip steps:

1. Read the `tacacs://syntax/reference` resource. Do not write config from
   memory — this deployment uses tac_plus-ng, whose grammar differs from
   tac_plus v4.
2. Use `list_entities` and `describe_entity` to see what already exists. Reuse
   existing group and profile names rather than inventing parallel ones.
3. Draft the config.
4. Call `validate_config_text` and iterate until `status == "success"`. Report
   the line and message on each failure rather than guessing.
5. Call `diff_generated_vs_active` if the question is what would change.

Constraints you must respect:

- This server is read-only. You cannot save, activate, or reload anything.
  Never state or imply that a change has been applied — hand the validated text
  back and say it still needs to be applied through the UI.
- Config text you receive has secrets masked as `***REDACTED***` whenever
  `secrets_redacted` is greater than zero. Never present such text as
  deployable, and never invent replacement values for masked secrets.
"""


def register(server: FastMCP) -> None:
    @server.resource(
        "tacacs://syntax/reference",
        name="tac_plus-ng syntax reference",
        description="The tac_plus-ng grammar this application generates.",
        mime_type="text/markdown",
    )
    def syntax_reference() -> str:
        return SYNTAX_REFERENCE

    @server.resource(
        "tacacs://schema/entities",
        name="TACACS+ entity schema",
        description="Which database fields reach the generated config, and which do not.",
        mime_type="text/markdown",
    )
    def entity_schema() -> str:
        return ENTITY_SCHEMA

    @server.resource(
        "tacacs://config/active",
        name="Active tac_plus-ng config",
        description="The live config file, with secrets redacted.",
        mime_type="text/plain",
    )
    def active_config() -> str:
        with Session(engine) as session:
            return service.read_active_config_text(session=session)

    @server.prompt(
        name="author_tacacs_config",
        description="Workflow for drafting and validating a tac_plus-ng config.",
    )
    def author_tacacs_config() -> str:
        return AUTHOR_PROMPT
