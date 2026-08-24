# MCP Server

tacacs-ng-ui can expose a [Model Context Protocol](https://modelcontextprotocol.io)
endpoint so an LLM client — Claude Desktop, Claude Code, or any MCP-capable
tool — can inspect your TACACS+ configuration and help author new config in
`tac_plus-ng` syntax.

The server is **read-only**. It never writes to the database, never writes the
live config file, never activates a config, never restarts the daemon, and never
pushes to HA peers. Applying a change remains a deliberate action in the UI.

## Enabling

The feature is off by default. In `.env`:

```
MCP_ENABLED=true
MCP_PATH=/mcp
```

Restart the backend. The endpoint is served by the existing FastAPI app on port
8000, so the Traefik router for `api.${DOMAIN}` already covers it — no new
container, no new port, no new labels.

The canonical URL carries a trailing slash:

```
https://api.${DOMAIN}/mcp/
```

`POST /mcp` (no slash) answers with a 307 redirect to `/mcp/`. Most clients
follow it, but prefer the slash form.

## Authentication

MCP clients authenticate with a dedicated **API key**, not a login JWT. Keys are
stored as an HMAC-SHA256 digest keyed with `SECRET_KEY`; the plaintext is shown
exactly once, at creation, and is not recoverable afterwards.

### From the UI

Sign in as a superuser and open **User Settings → API Keys**. The tab is hidden
from everyone else. *Create API Key* asks for a name, the scopes, a lifetime,
and an optional allowlist of source IPs/CIDRs; the generated key and a
ready-to-paste `claude mcp add` command are shown once, with a copy button.
After you close that dialog only the 20-character prefix is ever displayed
again.

Revoking from the same table takes effect immediately. The IP allowlist can
also be edited later, from the same row, without reissuing the key.

### From the API

```bash
curl -s -X POST https://api.example.com/api/v1/api_keys/ \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "claude-desktop-laptop",
        "scopes": "mcp:read,mcp:generate,mcp:validate",
        "allowed_ips": "203.0.113.4,198.51.100.0/24",
        "expires_in_days": 90
      }' | jq -r .plaintext_key
```

| Endpoint | Who | Purpose |
|---|---|---|
| `POST /api/v1/api_keys/` | superuser | create a key (returns the plaintext once) |
| `GET /api/v1/api_keys/` | superuser | list all keys |
| `GET /api/v1/api_keys/me` | any user | list your own keys |
| `GET /api/v1/api_keys/{id}` | superuser | read one key |
| `PATCH /api/v1/api_keys/{id}` | superuser | update the IP allowlist only |
| `DELETE /api/v1/api_keys/{id}` | superuser | revoke (soft — the row is kept for audit) |

The UI uses these same endpoints. `allowed_ips` is a comma-separated list of
IPv4/IPv6 addresses or CIDR networks the key may authenticate from; omit it (or
send `null`) for no restriction. It's the one field editable after creation —
everything else, including scope, is fixed at creation time, so a change of
scope means minting a replacement and revoking the old key.

A request from a source IP outside the allowlist gets the same generic 401 as
an invalid or expired key — the middleware doesn't distinguish the reason, so
an unauthenticated caller can't learn that a key exists but is IP-restricted.

Creation and revocation are recorded in the audit log. The digest is never
returned by any endpoint and never appears in audit values.

> **Rotating `SECRET_KEY` invalidates every API key**, exactly as it already
> invalidates every JWT and every stored provider secret.

### Scopes

| Scope | Grants |
|---|---|
| `mcp:read` | entity listings, saved configs, daemon settings |
| `mcp:generate` | rendering config previews, sections and diffs |
| `mcp:validate` | running `tac_plus-ng -P` |
| `mcp:secrets` | unredacted config output — **additionally requires the key to belong to a superuser**, and every use writes an `EXPORT` audit entry |

`validate_config_text` is superuser-only regardless of scope, because it feeds
arbitrary text to a privileged parser.

## Connecting a client

```bash
claude mcp add --transport http tacacs-ng https://api.example.com/mcp/ \
  --header "Authorization: Bearer tngk_..."
```

Then ask, for example:

- "Which TACACS hosts are configured?"
- "Render the config from the database and check that it compiles."
- "What would change if the config were regenerated right now?"
- "Draft a read-only profile for Juniper devices and validate it."

## Tools

| Tool | Scope | What it does |
|---|---|---|
| `whoami` | — | reports the key's identity, scopes and node role |
| `list_entities` | `mcp:read` | lists hosts, users, groups, profiles, rulesets, MAVIS entries, configuration options or services |
| `describe_entity` | `mcp:read` | one entity by name, with nested scripts for profiles and rulesets |
| `get_tacacs_settings` | `mcp:read` | daemon settings (listen address, instances, log destinations) |
| `generate_config_preview` | `mcp:generate` | renders the full config from current database state |
| `generate_config_section` | `mcp:generate` | renders one section (`mavis`, `profiles`, `rulesets`) |
| `validate_config_text` | `mcp:validate` + superuser | syntax-checks arbitrary text |
| `validate_generated_config` | `mcp:validate` | validates the real unredacted config entirely server-side |
| `list_saved_configs` | `mcp:read` | saved config files and which one is active |
| `read_saved_config` | `mcp:read` | reads a saved config by filename |
| `validate_saved_config` | `mcp:validate` | syntax-checks a saved config |
| `diff_generated_vs_active` | `mcp:generate` | unified diff between the generated config and the live file |

### Resources

- `tacacs://syntax/reference` — the tac_plus-ng grammar this application emits.
  Clients should read this before authoring config; without it a model tends to
  produce tac_plus v4 syntax.
- `tacacs://schema/entities` — which database fields reach the config and which
  are UI-only.
- `tacacs://config/active` — the live config file, redacted.

### Prompt

`author_tacacs_config` — a workflow template (read the syntax reference → survey
existing entities → draft → validate → iterate). It surfaces as a slash command
in Claude Code.

## Secrets

`Host.secret_key`, `TacacsUser.password` and MAVIS credentials are written into
the generated config in cleartext. Every tool that can emit config text redacts
them by default, replacing each value with `***REDACTED***` and reporting a
`secrets_redacted` count.

Redaction runs in two passes: exact replacement of the values read from the
database (which catches secrets embedded in raw `ConfigurationOption`
passthrough blocks), then pattern matching on `key = "..."`,
`password login = ... "..."` and `setenv *PASSWD*="..."`.

`key = "***REDACTED***"` is still valid syntax, so redacted config still passes
`tac_plus-ng -P` structurally. What it loses is semantic verification — which is
why `validate_generated_config` exists: it validates the real, unredacted config
without any secret crossing the wire.

> Content stored in `ConfigurationOption` rows is treated as non-secret unless
> the same value also exists in a secret database column. Avoid pasting
> credentials into raw passthrough blocks.

## Operational notes

- **Multi-worker safety.** The server runs in stateless mode, which is required
  because supervisord starts `uvicorn --workers 4`. Turning that off would need
  a dedicated single-process program or sticky sessions.
- **No SSE.** Responses are plain JSON, so proxy buffering and idle timeouts are
  not a concern.
- **HA standby.** Every phase-1 tool is a read, so running MCP on a standby node
  is safe; API-key usage tracking and audit writes are skipped there because the
  replica is read-only.
- **`include` directives** are refused by `validate_config_text`, and input is
  capped by `MCP_MAX_CONFIG_TEXT_BYTES`.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `401` with `WWW-Authenticate: Bearer` | missing, malformed, revoked or expired key, or the key's user is inactive |
| `503 MCP server is not running` | `MCP_ENABLED` was false when the app started |
| `404` on `/mcp/` | `MCP_ENABLED` is false — the mount is only added at startup |
| Tool error naming a scope | the key lacks that scope; mint a new one (scopes are fixed at creation) |
| `tac_plus-ng command not found` | the binary is missing from the container image |
