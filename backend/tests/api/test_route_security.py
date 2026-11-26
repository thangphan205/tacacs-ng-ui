"""Deny-by-default OpenAPI security guard for every /api/v1/* operation.

Prevents accidental omission of authentication dependencies (such as the
unauthenticated GET /api/v1/audit_logs/ regression). Any intentionally public
or custom-header-authenticated endpoint must be listed explicitly below.
"""

from app.main import app

# Intentionally unauthenticated or non-OAuth2-authenticated /api/v1/* endpoints.
PUBLIC_OPERATIONS: frozenset[tuple[str, str]] = frozenset(
    {
        # Public feature flags & health
        ("GET", "/api/v1/auth-providers/status"),
        ("GET", "/api/v1/utils/health-check/"),
        # Login, signup, password recovery
        ("POST", "/api/v1/login/access-token"),
        ("POST", "/api/v1/login/ldap/access-token"),
        ("POST", "/api/v1/password-recovery/{email}"),
        ("POST", "/api/v1/reset-password/"),
        ("POST", "/api/v1/users/signup"),
        # OAuth / OIDC login flows
        ("GET", "/api/v1/oauth/google/authorize"),
        ("GET", "/api/v1/oauth/google/callback"),
        ("GET", "/api/v1/oauth/keycloak/authorize"),
        ("GET", "/api/v1/oauth/keycloak/callback"),
        ("GET", "/api/v1/oauth/microsoft/authorize"),
        ("GET", "/api/v1/oauth/microsoft/callback"),
        # Passkey authentication
        ("POST", "/api/v1/passkeys/authenticate/begin"),
        ("POST", "/api/v1/passkeys/authenticate/complete"),
        # Internal HA sync endpoints (authenticated via X-HA-Sync-Secret header)
        ("POST", "/api/v1/sync/internal/collect-stats"),
        ("POST", "/api/v1/sync/internal/reload-config"),
        # Local-only test helper (only mounted when ENVIRONMENT == "local")
        ("POST", "/api/v1/private/users/"),
    }
)


def test_every_api_v1_route_declares_security_unless_explicitly_public() -> None:
    schema = app.openapi()
    unexpected: list[tuple[str, str]] = []
    for path, methods in sorted(schema["paths"].items()):
        if not path.startswith("/api/v1/"):
            continue
        for method, operation in methods.items():
            verb = method.upper()
            if verb not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                continue
            if not operation.get("security") and (verb, path) not in PUBLIC_OPERATIONS:
                unexpected.append((verb, path))
    assert unexpected == [], (
        f"Routes missing OpenAPI security requirement: {unexpected}"
    )


def test_audit_log_routes_declare_oauth2_security() -> None:
    paths = app.openapi()["paths"]
    for path, method in (
        ("/api/v1/audit_logs/", "get"),
        ("/api/v1/audit_logs/{id}", "get"),
        ("/api/v1/audit_logs/purge", "delete"),
    ):
        security = paths[path][method].get("security")
        assert security, f"{method.upper()} {path} is missing security"
