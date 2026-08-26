# MCP Server

tacacs-ng-ui can expose a [Model Context Protocol](https://modelcontextprotocol.io)
endpoint so an LLM client — Claude Desktop, Claude Code, or any MCP-capable
tool — can inspect your TACACS+ configuration and help author new config in
`tac_plus-ng` syntax.

A key is issued at one of two access levels. **Read-only** keys change nothing.
**Read-write** keys can create, update and delete TACACS+ entities — users,
groups, hosts, profiles, rulesets, services, MAVIS entries and configuration
options.

**Neither level can deploy.** There is no tool that writes the live config file,
activates a config, restarts the daemon or pushes to HA peers, and there will
not be one. An entity edited over MCP sits in the database until a human opens
**TACACS Configs** in the UI and presses *Generate*, then *Activate*. Until
then, the running daemon keeps serving the config it already has.

## Enabling

The feature is **on by default** (`MCP_ENABLED=true`). To turn it off, set in
`.env`:

```
MCP_ENABLED=false
```

Restart the backend after changing it either way. The endpoint is served by
the existing FastAPI app on port 8000 and reached through the frontend's
nginx, which proxies the `/mcp` prefix (along with `/api`, `/docs` and
`/redoc`) to the backend. It therefore lives on the same URL as the UI — no
new container, no new port, no new Traefik labels.

The canonical URL carries a trailing slash:

```
https://${DOMAIN}/mcp/
```

The proxied prefix is `/mcp`, hardcoded in `frontend/nginx-backend-proxy.conf`.
If you change `MCP_PATH`, change it there too.

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
curl -s -X POST https://tacacs.example.com/api/v1/api_keys/ \
  -H "Authorization: Bearer $JWT" \
  -H "Content-Type: application/json" \
  -d '{
        "name": "claude-desktop-laptop",
        "scopes": "mcp:read",
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

Two access levels, plus one independent opt-in:

| Scope | UI label | Grants |
|---|---|---|
| `mcp:read` | Read-only | entity listings, daemon settings, saved configs, config previews and sections, diffs, and every `tac_plus-ng -P` syntax check |
| `mcp:write` | Read-write | everything in `mcp:read` (it does not need to be granted separately) **plus** creating, updating and deleting entities — **additionally requires the key to belong to a superuser**, and refuses on a standby node |
| `mcp:secrets` | *Allow unredacted secrets* | unredacted config output — **additionally requires the key to belong to a superuser**, and every use writes an `EXPORT` audit entry |

Every write is recorded in the audit log with user agent
`mcp/api-key:<key name>`, so an MCP-made change is distinguishable from one made
in the UI.

`validate_config_text` is superuser-only regardless of scope, because it feeds
arbitrary text to a privileged parser.

Anything outside this set is rejected at key creation, so a typo cannot silently
mint a key that grants nothing.

## Connecting a client

### 1. Claude Code (CLI)

Add the HTTP MCP endpoint directly using the `claude` CLI:

```bash
claude mcp add --transport http tacacs-ng https://tacacs.example.com/mcp/ \
  --header "Authorization: Bearer tngk_..."
```

Or add to your project `.claude.json` / user configuration:

```json
{
  "mcpServers": {
    "tacacs-ng": {
      "url": "https://tacacs.example.com/mcp/",
      "headers": {
        "Authorization": "Bearer tngk_..."
      }
    }
  }
}
```

### 2. Claude Desktop

Claude Desktop connects over stdio. Use the [`mcp-remote`](https://www.npmjs.com/package/mcp-remote) bridge to proxy to the Streamable HTTP endpoint:

Edit `claude_desktop_config.json`:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Linux**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "tacacs-ng": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://tacacs.example.com/mcp/",
        "--header",
        "Authorization: Bearer tngk_..."
      ]
    }
  }
}
```

*Restart Claude Desktop after saving the configuration file.*

### 3. Google Antigravity

Add the server to your global config (`~/.gemini/config/mcp_config.json`) or workspace configuration (`.agents/mcp_config.json`):

```json
{
  "mcpServers": {
    "tacacs-ng": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://tacacs.example.com/mcp/",
        "--header",
        "Authorization: Bearer tngk_..."
      ]
    }
  }
}
```

Antigravity automatically discovers and lists active tools. You can verify the tools in the IDE under **Additional Options (...) → MCP Servers**.

### 4. Gemini CLI & Gemini Code Assist

Register with the Gemini CLI:

```bash
gemini mcp add tacacs-ng --url https://tacacs.example.com/mcp/ \
  --header "Authorization: Bearer tngk_..."
```

Or configure in `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "tacacs-ng": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://tacacs.example.com/mcp/",
        "--header",
        "Authorization: Bearer tngk_..."
      ]
    }
  }
}
```

### 5. Cursor & Windsurf

Add to `.cursor/mcp.json` or configure under **Cursor Settings → Features → MCP**:

```json
{
  "mcpServers": {
    "tacacs-ng": {
      "command": "npx",
      "args": [
        "-y",
        "mcp-remote",
        "https://tacacs.example.com/mcp/",
        "--header",
        "Authorization: Bearer tngk_..."
      ]
    }
  }
}
```

### Example Questions & Workflows

Once connected, ask the assistant:

- "Which TACACS hosts and user groups are currently configured?"
- "Render the full config preview from the database and verify that it passes validation."
- "What would change in the config if regenerated right now? (diff vs active)"
- "Draft a read-only profile for Juniper routers and validate the syntax."

## Tools

| Tool | Scope | What it does |
|---|---|---|
| `whoami` | — | reports the key's identity, scopes and node role |
| `list_entities` | `mcp:read` | lists hosts, users, groups, profiles, rulesets, MAVIS entries, configuration options or services |
| `describe_entity` | `mcp:read` | one entity by name, with nested scripts for profiles and rulesets |
| `get_tacacs_settings` | `mcp:read` | daemon settings (listen address, instances, log destinations) |
| `generate_config_preview` | `mcp:read` | renders the full config from current database state |
| `generate_config_section` | `mcp:read` | renders one section (`mavis`, `profiles`, `rulesets`) |
| `validate_config_text` | `mcp:read` + superuser | syntax-checks arbitrary text |
| `validate_generated_config` | `mcp:read` | validates the real unredacted config entirely server-side |
| `list_saved_configs` | `mcp:read` | saved config files and which one is active |
| `read_saved_config` | `mcp:read` | reads a saved config by filename |
| `validate_saved_config` | `mcp:read` | syntax-checks a saved config |
| `diff_generated_vs_active` | `mcp:read` | unified diff between the generated config and the live file |
| `create_entity` | `mcp:write` + superuser | creates one entity from a field dict |
| `update_entity` | `mcp:write` + superuser | updates one entity by name; the payload may be partial |
| `delete_entity` | `mcp:write` + superuser | deletes one entity by name; requires `confirm=true` |

Despite its name, `generate_config_preview` only renders text — it writes
nothing. Every write tool returns a `next_step` field reminding the client that
a human must generate and activate the config for the change to take effect.

There is deliberately **no** tool for saving, activating or reloading a config.
`backend/tests/mcp/test_no_config_writes.py` walks the AST of every module under
`app/mcp_server/` and fails the build if one gains the ability.

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
- **HA standby.** Read tools are safe on a standby node; API-key usage tracking
  and audit writes are skipped there because the replica is read-only. The write
  tools refuse outright on a standby, mirroring `require_primary_node` on the
  REST routes.
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
