"""MCP tool, resource and prompt registrations.

Every tool is `async def` and offloads its work with `run_in_threadpool`:
the MCP server invokes synchronous tool functions inline on the event loop, so a
blocking DB query or a 10-second `tac_plus-ng -P` subprocess would freeze one
of the four uvicorn workers.

Scopes: mcp:read (read-only) · mcp:write (read-write, implies mcp:read) ·
mcp:secrets (opt-in, unredacted output). `mcp:write` and `mcp:secrets` both
additionally require the key to be bound to a superuser.

Writes reach entity tables only. No tool here saves a config file, activates a
config or reloads tac_plus-ng — a human does that from the TACACS Configs page.
"""

import functools
import logging
from collections.abc import Awaitable, Callable
from typing import Annotated, Any, Literal

from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field
from sqlmodel import Session
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.core.db import engine
from app.crud import audit_logs as audit_logs_crud
from app.crud.api_keys import ApiKeyPrincipal
from app.mcp_server import resources, service, write_service
from app.mcp_server.auth import (
    McpAuthError,
    principal_from,
    require_scope,
    require_superuser,
)

log = logging.getLogger(__name__)

EntityType = Literal[
    "host",
    "user",
    "group",
    "profile",
    "ruleset",
    "mavis",
    "configuration_option",
    "tacacs_service",
]
Section = Literal["mavis", "profiles", "rulesets"]

# Bound in the tool signature so the JSON schema advertises the range and
# pydantic refuses out-of-range values before any SQL is built. Without it a
# negative limit reaches Postgres and the raw error, SQL text included, is
# handed back to the LLM client.
MAX_PAGE_SIZE = 500

# Appended to every write response. The tools mutate entity rows only; nothing
# reaches tac_plus-ng until a human generates and activates a config in the UI.
NEXT_STEP = (
    "Saved to the database only. The running tac_plus-ng daemon is unchanged: "
    "a human must open the TACACS Configs page in the UI and press Generate, "
    "then Activate, before this takes effect. Call diff_generated_vs_active to "
    "show what is still pending."
)


def _require_read(principal: ApiKeyPrincipal) -> None:
    """Read access: `mcp:write` subsumes `mcp:read`, so either one passes."""
    if not (principal.has("mcp:read") or principal.has("mcp:write")):
        raise McpAuthError("API key is missing the required scope 'mcp:read'.")


def _allow_write(principal: ApiKeyPrincipal, action: str) -> None:
    """Entity writes need the scope, a superuser, and a primary node.

    The node check mirrors `api.deps.require_primary_node`, which MCP tools
    cannot use because they are not FastAPI routes.
    """
    require_scope(principal, "mcp:write")
    require_superuser(principal, action)
    if settings.NODE_ROLE == "standby":
        raise McpAuthError(
            "This node is in standby (read-only) mode. "
            "Make changes on the primary node."
        )


def _allow_unredacted(principal: ApiKeyPrincipal, what: str) -> None:
    """Unredacted config output requires both the scope and superuser status."""
    require_scope(principal, "mcp:secrets")
    require_superuser(principal, f"Returning unredacted {what}")


def _audit_secret_export(principal: ApiKeyPrincipal, what: str) -> None:
    try:
        with Session(engine) as session:
            audit_logs_crud.log_entity_action(
                session=session,
                action="EXPORT",
                entity_type="TacacsConfig",
                entity_id=None,
                user_id=principal.user_id,
                user_email=principal.user_email,
                ip_address=None,
                user_agent=f"mcp/api-key:{principal.api_key_name}",
                description=(
                    f"Unredacted {what} exported over MCP using API key "
                    f"'{principal.api_key_name}'"
                ),
            )
    except Exception:
        log.warning("Failed to audit unredacted MCP export", exc_info=True)


def _audit_write(
    principal: ApiKeyPrincipal, action: str, result: write_service.WriteResult
) -> None:
    """Record an MCP-originated mutation, same shape as the REST routes do."""
    try:
        with Session(engine) as session:
            audit_logs_crud.log_entity_action(
                session=session,
                action=action,
                entity_type=result.audit_type,
                entity_id=result.entity_id,
                user_id=principal.user_id,
                user_email=principal.user_email,
                ip_address=None,
                user_agent=f"mcp/api-key:{principal.api_key_name}",
                old_values=result.old_values,
                new_values=result.new_values,
                description=(
                    f"{action.title()}d over MCP using API key "
                    f"'{principal.api_key_name}'"
                ),
            )
    except Exception:
        log.warning("Failed to audit MCP write", exc_info=True)


# Failures these tools raise on purpose, whose text the model needs to read:
# an auth refusal, a missing entity, an invalid or duplicate payload.
_ANTICIPATED = (McpAuthError, LookupError, ValueError)


def _tool(
    server: MCPServer,
) -> Callable[[Callable[..., Awaitable[Any]]], Callable[..., Awaitable[Any]]]:
    """Register a tool, translating anticipated failures into `ToolError`.

    mcp 2.x reserves `ToolError` for failures a tool saw coming: its message
    reaches the model and the server logs it at INFO. Every *other* exception
    is treated as a crash — the model is told only "Error executing tool
    <name>" and the traceback is logged at ERROR. That default is right for
    real bugs, but it would swallow the scope refusals and validation messages
    these tools exist to report.

    The translation lives here rather than in `service`/`write_service` for the
    same reason `crud/` never raises `HTTPException`: those modules stay plain
    DB helpers raising `LookupError`/`ValueError`, and the transport-shaped
    exception is applied at the boundary.
    """

    def decorate(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await fn(*args, **kwargs)
            except _ANTICIPATED as exc:
                raise ToolError(str(exc)) from exc

        # `functools.wraps` sets `__wrapped__`, so the SDK still reads the
        # wrapped signature when it builds the input schema.
        return server.tool()(wrapper)

    return decorate


def register(server: MCPServer) -> None:
    @_tool(server)
    async def whoami(ctx: Context) -> dict[str, Any]:
        """Identify the API key this session is authenticated with.

        `can_write` reports whether entity writes are permitted. Even when it is
        true, no tool can generate, save, activate or reload a config.
        """
        p = principal_from(ctx)
        can_write = (
            p.has("mcp:write") and p.is_superuser and settings.NODE_ROLE != "standby"
        )
        return {
            "user_email": p.user_email,
            "is_superuser": p.is_superuser,
            "scopes": sorted(p.scopes),
            "api_key_name": p.api_key_name,
            "node_role": settings.NODE_ROLE,
            "can_write": can_write,
            "mcp_read_only": not can_write,
            "can_activate_config": False,
        }

    @_tool(server)
    async def list_entities(
        ctx: Context,
        entity_type: EntityType,
        search: str | None = None,
        limit: Annotated[int, Field(ge=1, le=MAX_PAGE_SIZE)] = 100,
        offset: Annotated[int, Field(ge=0)] = 0,
        only_generated: bool | None = None,
    ) -> dict[str, Any]:
        """List TACACS+ entities of one type.

        `only_generated=true` restricts the result to rows that actually reach
        the generated config. Secret fields are always redacted.
        """
        p = principal_from(ctx)
        _require_read(p)

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.list_entities(
                    session=session,
                    entity_type=entity_type,
                    search=search,
                    limit=limit,
                    offset=offset,
                    only_generated=only_generated,
                )

        return await run_in_threadpool(_run)

    @_tool(server)
    async def describe_entity(
        ctx: Context,
        entity_type: EntityType,
        name: str,
        include_children: bool = True,
    ) -> dict[str, Any]:
        """Describe one entity by name, with its nested scripts where applicable."""
        p = principal_from(ctx)
        _require_read(p)

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.describe_entity(
                    session=session,
                    entity_type=entity_type,
                    name=name,
                    include_children=include_children,
                )

        return await run_in_threadpool(_run)

    @_tool(server)
    async def get_tacacs_settings(ctx: Context) -> dict[str, Any]:
        """Read the tac_plus-ng daemon settings (listen address, instances, logs)."""
        p = principal_from(ctx)
        _require_read(p)

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.get_tacacs_settings(session=session)

        return await run_in_threadpool(_run)

    @_tool(server)
    async def generate_config_preview(
        ctx: Context,
        redact_secrets: bool = True,
    ) -> dict[str, Any]:
        """Render the full tac_plus-ng config from current database state.

        Nothing is written: this is a preview. `secrets_redacted` reports how
        many secret values were masked — a non-zero value means the text is not
        deployable as-is.
        """
        p = principal_from(ctx)
        _require_read(p)
        if not redact_secrets:
            _allow_unredacted(p, "config")
            _audit_secret_export(p, "config preview")

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.generate_config_preview(
                    session=session, redact_secrets=redact_secrets
                )

        return await run_in_threadpool(_run)

    @_tool(server)
    async def generate_config_section(
        ctx: Context,
        section: Section,
        redact_secrets: bool = True,
    ) -> dict[str, Any]:
        """Render a single config section (mavis, profiles or rulesets)."""
        p = principal_from(ctx)
        _require_read(p)
        if not redact_secrets:
            _allow_unredacted(p, "config section")
            _audit_secret_export(p, f"config section '{section}'")

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.generate_config_section(
                    session=session, section=section, redact_secrets=redact_secrets
                )

        return await run_in_threadpool(_run)

    @_tool(server)
    async def validate_config_text(
        ctx: Context,
        text: str,
    ) -> dict[str, Any]:
        """Syntax-check arbitrary config text with `tac_plus-ng -P`.

        Nothing is saved or applied. Returns the first error's line and message
        when the text does not parse.
        """
        p = principal_from(ctx)
        _require_read(p)
        # The parser runs privileged in this container and tac_plus-ng config
        # supports `include`, which would turn arbitrary text into a file-read
        # primitive. Superuser-only, size-capped, and include-directives refused.
        require_superuser(p, "Validating arbitrary config text")

        size = len(text.encode("utf-8"))
        if size > settings.MCP_MAX_CONFIG_TEXT_BYTES:
            raise McpAuthError(
                f"Config text is {size} bytes, over the "
                f"{settings.MCP_MAX_CONFIG_TEXT_BYTES} byte limit."
            )
        for line in text.splitlines():
            stripped = line.strip().lstrip("#").strip()
            if stripped.split(" ")[0].lower() == "include":
                raise McpAuthError(
                    "`include` directives are not accepted by this tool; "
                    "inline the referenced content instead."
                )

        return await run_in_threadpool(
            service.validate_config_text,
            text=text,
            timeout=settings.MCP_VALIDATE_TIMEOUT_SECONDS,
        )

    @_tool(server)
    async def validate_generated_config(ctx: Context) -> dict[str, Any]:
        """Validate the real, unredacted config built from the database.

        Prefer this over `validate_config_text` when the question is "does what
        is in the database right now actually compile" — no secret leaves the
        server.
        """
        p = principal_from(ctx)
        _require_read(p)

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.validate_generated_config(
                    session=session, timeout=settings.MCP_VALIDATE_TIMEOUT_SECONDS
                )

        return await run_in_threadpool(_run)

    @_tool(server)
    async def list_saved_configs(ctx: Context) -> dict[str, Any]:
        """List saved config files and report which one is active."""
        p = principal_from(ctx)
        _require_read(p)

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.list_saved_configs(session=session)

        return await run_in_threadpool(_run)

    @_tool(server)
    async def read_saved_config(
        ctx: Context,
        filename: str,
        redact_secrets: bool = True,
    ) -> dict[str, Any]:
        """Read a saved config file by name (without the .cfg suffix)."""
        p = principal_from(ctx)
        _require_read(p)
        if not redact_secrets:
            _allow_unredacted(p, "saved config")
            _audit_secret_export(p, f"saved config '{filename}'")

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.read_saved_config(
                    session=session, filename=filename, redact_secrets=redact_secrets
                )

        return await run_in_threadpool(_run)

    @_tool(server)
    async def validate_saved_config(
        ctx: Context,
        filename: str,
    ) -> dict[str, Any]:
        """Syntax-check a saved config file by name."""
        p = principal_from(ctx)
        _require_read(p)

        return await run_in_threadpool(
            service.validate_saved_config,
            filename=filename,
            timeout=settings.MCP_VALIDATE_TIMEOUT_SECONDS,
        )

    @_tool(server)
    async def diff_generated_vs_active(
        ctx: Context,
        redact_secrets: bool = True,
    ) -> dict[str, Any]:
        """Diff the config generated from the database against the live file.

        Answers "what would change if this were regenerated and applied".
        """
        p = principal_from(ctx)
        _require_read(p)
        if not redact_secrets:
            _allow_unredacted(p, "diff")
            _audit_secret_export(p, "config diff")

        def _run() -> dict[str, Any]:
            with Session(engine) as session:
                return service.diff_generated_vs_active(
                    session=session, redact_secrets=redact_secrets
                )

        return await run_in_threadpool(_run)

    @_tool(server)
    async def create_entity(
        ctx: Context,
        entity_type: EntityType,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Create one TACACS+ entity.

        `data` holds the entity's fields — read the `tacacs://schema/entities`
        resource for the field list of each type. For a user, `password` is the
        **plaintext** password; the server hashes it. Never pre-hash it.

        The row is written to the database only: the live config file is
        untouched and the daemon is not reloaded, so a human still has to
        generate and activate a config.
        """
        p = principal_from(ctx)
        _allow_write(p, f"Creating a {entity_type}")

        def _run() -> write_service.WriteResult:
            with Session(engine) as session:
                return write_service.create_entity(
                    session=session, entity_type=entity_type, data=data
                )

        result = await run_in_threadpool(_run)
        await run_in_threadpool(_audit_write, p, "CREATE", result)
        return {
            "created": True,
            "entity_type": result.entity_type,
            "id": result.entity_id,
            "item": result.item,
            "next_step": NEXT_STEP,
        }

    @_tool(server)
    async def update_entity(
        ctx: Context,
        entity_type: EntityType,
        name: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Update one TACACS+ entity, addressed by its current name.

        `data` may be partial — omitted fields keep their current value. For a
        user, `password` is the **plaintext** password; the server hashes it.
        Never pre-hash it.

        As with `create_entity`, this changes the database only; nothing reaches
        the running daemon until a human generates and activates a config.
        """
        p = principal_from(ctx)
        _allow_write(p, f"Updating a {entity_type}")

        def _run() -> write_service.WriteResult:
            with Session(engine) as session:
                return write_service.update_entity(
                    session=session, entity_type=entity_type, name=name, data=data
                )

        result = await run_in_threadpool(_run)
        await run_in_threadpool(_audit_write, p, "UPDATE", result)
        return {
            "updated": True,
            "entity_type": result.entity_type,
            "id": result.entity_id,
            "item": result.item,
            "next_step": NEXT_STEP,
        }

    @_tool(server)
    async def delete_entity(
        ctx: Context,
        entity_type: EntityType,
        name: str,
        confirm: bool = False,
    ) -> dict[str, Any]:
        """Delete one TACACS+ entity by name. Requires `confirm=true`.

        Destructive and not undoable — child rows (profile and ruleset scripts)
        cascade with the parent. Call `describe_entity` first and show the caller
        what will be removed. The daemon keeps running the currently active
        config until a human generates and activates a new one.
        """
        p = principal_from(ctx)
        _allow_write(p, f"Deleting a {entity_type}")
        if not confirm:
            raise McpAuthError(
                f"Refusing to delete {entity_type} '{name}' without confirm=true."
            )

        def _run() -> write_service.WriteResult:
            with Session(engine) as session:
                return write_service.delete_entity(
                    session=session, entity_type=entity_type, name=name
                )

        result = await run_in_threadpool(_run)
        await run_in_threadpool(_audit_write, p, "DELETE", result)
        return {
            "deleted": True,
            "entity_type": result.entity_type,
            "id": result.entity_id,
            "name": name,
            "next_step": NEXT_STEP,
        }

    resources.register(server)
