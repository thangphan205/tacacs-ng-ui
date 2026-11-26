"""Migration c7e3a9d14f20 scrubs inline secrets in historical auditlog rows."""

import importlib.util
import json
import uuid
from pathlib import Path
from types import ModuleType

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text

from app.core.db import engine

MIGRATION = (
    Path(__file__).parents[2]
    / "app/alembic/versions/c7e3a9d14f20_scrub_inline_audit_log_secrets.py"
)


@pytest.fixture(scope="module")
def migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("scrub_audit_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def j(**kw: object) -> str:
    return json.dumps(kw, separators=(",", ":"))


def test_frozen_rules_scrub_config_option_and_description(
    migration: ModuleType,
) -> None:
    block = (
        'user radclear {\n'
        '    password login = clear "Rad-e5743209427b"\n'
        '    password pap = login\n'
        '    password ms-chap = clear "Rad-e5743209427b"\n'
        "    member = tacacs_super_user\n"
        "}"
    )
    old_out, new_out, desc_out = migration._redact(
        "ConfigurationOption",
        j(name="radclear", config_option=block),
        None,
        "Bearer leak Authorization: Bearer tok_secret_123",
    )
    assert new_out is None
    assert "Rad-e5743209427b" not in (old_out or "")
    assert "password pap = login" in (old_out or "")
    assert 'password login = clear "[redacted]"' in json.loads(old_out)["config_option"]
    assert "tok_secret_123" not in (desc_out or "")
    assert "Authorization: Bearer [redacted]" in (desc_out or "")


def test_upgrade_scrubs_inline_secrets_and_preserves_updated_at(
    migration: ModuleType,
) -> None:
    block = 'user radclear {\n password login = clear "Rad-e5743209427b"\n}'
    rows = {
        "cfg_opt": (
            "ConfigurationOption",
            j(name="rad", config_option=block),
            None,
            None,
        ),
        "radius_host": (
            "Host",
            None,
            j(name="h1", radius_secret_key="RAD-SECRET-99"),
            None,
        ),
        "desc_leak": (
            "ApiKey",
            None,
            None,
            "Issued token tngk_secretapikey12345",
        ),
        "plain": (
            "Host",
            None,
            j(name="plain-host", ipv4_address="192.0.2.1/32"),
            "Normal description",
        ),
    }
    ids = {name: uuid.uuid4() for name in rows}
    with engine.connect() as conn:
        trans = conn.begin()
        try:
            for name, (entity_type, old, new, desc) in rows.items():
                conn.execute(
                    text(
                        "INSERT INTO auditlog (id, action, entity_type, entity_id, "
                        "user_email, description, old_values, new_values, created_at, updated_at) "
                        "VALUES (:id, 'X', :t, :e, 't@example.com', :d, :o, :n, "
                        "'2020-01-01', '2020-01-02')"
                    ),
                    {
                        "id": ids[name],
                        "t": entity_type,
                        "e": name,
                        "d": desc,
                        "o": old,
                        "n": new,
                    },
                )
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()

            def row(name: str) -> tuple[str | None, str | None, str | None]:
                got = conn.execute(
                    text(
                        "SELECT old_values, new_values, description "
                        "FROM auditlog WHERE id = :i"
                    ),
                    {"i": ids[name]},
                ).one()
                return got[0], got[1], got[2]

            assert "Rad-e5743209427b" not in (row("cfg_opt")[0] or "")
            assert "[redacted]" in (row("cfg_opt")[0] or "")
            assert json.loads(row("radius_host")[1] or "")["radius_secret_key"] == "[redacted]"
            assert "tngk_secretapikey12345" not in (row("desc_leak")[2] or "")
            assert row("plain") == (None, rows["plain"][2], "Normal description")
            stamped = conn.execute(
                text("SELECT updated_at::date FROM auditlog WHERE id = :i"),
                {"i": ids["cfg_opt"]},
            ).scalar()
            assert str(stamped) == "2020-01-02"
        finally:
            trans.rollback()
