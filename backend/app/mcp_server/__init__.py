"""MCP (Model Context Protocol) server for TACACS+ entity management.

Reads entities and renders/validates config text; with the `mcp:write` scope it
also creates, updates and deletes entities. It never saves a config file, never
activates one and never reloads the daemon — that stays a human action in the UI.

Named `mcp_server` rather than `mcp` so that `from mcp.server.mcpserver import ...`
inside this package unambiguously refers to the SDK.
"""
