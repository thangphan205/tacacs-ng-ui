"""The MCP server may edit entities. It may never deploy a config.

Generating a config file, activating one and reloading tac_plus-ng stay a human
action taken in the web UI. That guarantee is a source-level property — nothing
under `app.mcp_server` may reach the functions that write `/app/tacacs_config/`
or restart the daemon — so it is asserted here rather than through behaviour.

The checks walk the AST rather than grepping text: the modules describe these
functions in their docstrings precisely to say they are off limits, and a plain
substring search would fire on the prose.
"""

import ast
import pathlib

import app.mcp_server as mcp_server_pkg

# Each of these writes the config directory, flips the active flag, or restarts
# the daemon.
FORBIDDEN_NAMES = frozenset(
    {
        "create_tacacs_config",
        "update_tacacs_config",
        "delete_tacacs_config",
    }
)

# Config files are read in a few places here; none may be opened for writing,
# and nothing may shell out to supervisorctl.
WRITE_MODES = frozenset("wax")
FORBIDDEN_MODULES = frozenset({"subprocess", "os.system", "shutil"})

PACKAGE_DIR = pathlib.Path(mcp_server_pkg.__file__).parent


def _sources() -> list[pathlib.Path]:
    return sorted(PACKAGE_DIR.glob("*.py"))


def _trees() -> list[tuple[str, ast.Module]]:
    return [
        (p.name, ast.parse(p.read_text(encoding="utf-8"), filename=p.name))
        for p in _sources()
    ]


def test_the_package_has_sources_to_check() -> None:
    """Guards the guard: a bad glob would make every assertion below vacuous."""
    names = {p.name for p in _sources()}
    assert {"tools.py", "service.py", "write_service.py"} <= names


def test_no_module_references_a_config_deployment_function() -> None:
    for filename, tree in _trees():
        for node in ast.walk(tree):
            referenced = None
            if isinstance(node, ast.Attribute):
                referenced = node.attr
            elif isinstance(node, ast.Name):
                referenced = node.id
            elif isinstance(node, ast.ImportFrom):
                referenced = next(
                    (a.name for a in node.names if a.name in FORBIDDEN_NAMES), None
                )
            assert referenced not in FORBIDDEN_NAMES, (
                f"{filename} references '{referenced}'. The MCP server must not "
                f"be able to save, activate or reload a tac_plus-ng config."
            )


def test_no_module_imports_a_way_to_shell_out() -> None:
    for filename, tree in _trees():
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported = {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                imported = {node.module or ""}
            else:
                continue
            assert not (imported & FORBIDDEN_MODULES), (
                f"{filename} imports {imported & FORBIDDEN_MODULES}. Restarting "
                f"tac_plus-ng is not the MCP server's to do."
            )


def test_no_module_opens_a_file_for_writing() -> None:
    for filename, tree in _trees():
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
                continue
            if node.func.id != "open":
                continue
            mode = next(
                (
                    a.value
                    for a in node.args[1:2]
                    if isinstance(a, ast.Constant) and isinstance(a.value, str)
                ),
                "r",
            )
            assert not (set(mode) & WRITE_MODES), (
                f"{filename} opens a file with mode '{mode}'."
            )
