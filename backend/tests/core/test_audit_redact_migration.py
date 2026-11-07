"""Migration d8a41f6b2c95 masks secrets in audit rows stored before redaction."""

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
    / "app/alembic/versions/d8a41f6b2c95_redact_audit_log_secrets.py"
)


@pytest.fixture(scope="module")
def migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("redact_audit_migration", MIGRATION)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def j(**kw: object) -> str:
    return json.dumps(kw, separators=(",", ":"))


def test_frozen_rules_give_known_results(migration: ModuleType) -> None:
    """Hard-coded expectations: the migration must not drift with the app."""
    old, new = migration._redact(
        "TacacsUser",
        j(username="a", password="h1", password_type="crypt"),
        j(username="a", password="h2", password_type="crypt"),
    )
    assert json.loads(old)["password"] == "[redacted]"
    assert json.loads(new)["password"] == "[redacted: changed]"
    assert json.loads(new)["password_type"] == "crypt"

    _, out = migration._redact(
        "Mavis", None, j(mavis_key="LDAP_PASSWD", mavis_value="x")
    )
    assert json.loads(out)["mavis_value"] == "[redacted]"
    raw = j(mavis_key="LDAP_HOSTS", mavis_value="ldaps://h")
    assert migration._redact("Mavis", None, raw) == (None, raw)

    _, out = migration._redact("TacacsConfig", None, j(filename="c", config_text="k"))
    assert json.loads(out) == {"filename": "c", "config_text": "[redacted]"}


def test_upgrade_rewrites_only_rows_with_secrets_and_keeps_updated_at(
    migration: ModuleType,
) -> None:
    rows = {
        "user": (
            "TacacsUser",
            None,
            j(username="u1", password="$6$rounds=1$s$HASH", password_type="crypt"),
        ),
        "host": ("Host", j(name="h", secret_key="SHARED"), None),
        "cfg": ("TacacsConfig", None, j(filename="c", config_text="host{key=SHARED}")),
        "plain": ("Host", None, j(name="p", ipv4_address="192.0.2.1/32")),
        "none": ("Host", None, None),
    }
    ids = {name: uuid.uuid4() for name in rows}
    with engine.connect() as conn:
        trans = conn.begin()  # everything below is rolled back
        try:
            for name, (entity_type, old, new) in rows.items():
                conn.execute(
                    text(
                        "INSERT INTO auditlog (id, action, entity_type, entity_id, "
                        "user_email, old_values, new_values, created_at, updated_at) "
                        "VALUES (:id, 'X', :t, :e, 't@example.com', :o, :n, "
                        "'2020-01-01', '2020-01-02')"
                    ),
                    {"id": ids[name], "t": entity_type, "e": name, "o": old, "n": new},
                )
            with Operations.context(MigrationContext.configure(conn)):
                migration.upgrade()

            def row(name: str) -> tuple[str | None, str | None]:
                got = conn.execute(
                    text("SELECT old_values, new_values FROM auditlog WHERE id = :i"),
                    {"i": ids[name]},
                ).one()
                return got[0], got[1]

            assert json.loads(row("user")[1])["password"] == "[redacted]"
            assert json.loads(row("user")[1])["username"] == "u1"
            assert json.loads(row("host")[0]) == {
                "name": "h",
                "secret_key": "[redacted]",
            }
            assert json.loads(row("cfg")[1])["config_text"] == "[redacted]"
            # Rows without a secret are byte-for-byte untouched.
            assert row("plain") == (None, rows["plain"][2])
            assert row("none") == (None, None)
            everything = " ".join(str(v) for n in ids for v in row(n) if v)
            assert "HASH" not in everything and "SHARED" not in everything
            stamped = conn.execute(
                text("SELECT updated_at::date FROM auditlog WHERE id = :i"),
                {"i": ids["user"]},
            ).scalar()
            assert str(stamped) == "2020-01-02"  # the audit trail's own time is kept
        finally:
            trans.rollback()
