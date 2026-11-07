"""init_db must seed demo data once, on an empty database, and never touch it again.

Before this was enforced, every primary start re-created deleted demo accounts
with the public password `change_this` and reset hardened ones (password type,
group, profile privilege, rule action) back to the seeded values.

These tests share the dev database with the rest of the suite, so each one puts
the demo rows back the way it found them.
"""

from collections.abc import Generator

import pytest
from sqlmodel import Session, delete, select

from app.core import db as db_module
from app.core.db import engine, init_db
from app.models import (
    Profile,
    ProfileScript,
    ProfileScriptSet,
    Ruleset,
    RulesetScript,
    TacacsNgSetting,
    TacacsUser,
)


@pytest.fixture()
def demo(db: Session) -> Generator[Session, None, None]:
    """The demo rows exist (whatever state the dev database is in)."""
    db_module._seed_demo_data(db)
    db.commit()
    yield db
    db.rollback()


def _user(session: Session, username: str) -> TacacsUser | None:
    return session.exec(
        select(TacacsUser).where(TacacsUser.username == username)
    ).first()


def _priv_lvl_set(session: Session) -> ProfileScriptSet:
    profile = session.exec(
        select(Profile).where(Profile.name == "tacacs_super_user_profile")
    ).one()
    script = session.exec(
        select(ProfileScript)
        .where(ProfileScript.profile_id == profile.id)
        .where(ProfileScript.key == "service")
        .where(ProfileScript.value == "shell")
    ).one()
    return session.exec(
        select(ProfileScriptSet)
        .where(ProfileScriptSet.profilescript_id == script.id)
        .where(ProfileScriptSet.key == "priv-lvl")
    ).one()


def _super_user_rule(session: Session) -> RulesetScript:
    ruleset = session.exec(
        select(Ruleset).where(Ruleset.name == "default_ruleset")
    ).one()
    return session.exec(
        select(RulesetScript)
        .where(RulesetScript.ruleset_id == ruleset.id)
        .where(RulesetScript.key == "group")
        .where(RulesetScript.value == "tacacs_super_user")
    ).one()


def test_deleted_demo_user_is_not_recreated(demo: Session) -> None:
    user = _user(demo, "user_admin")
    assert user is not None
    demo.delete(user)
    demo.commit()
    try:
        init_db(demo)
        demo.expire_all()
        assert _user(demo, "user_admin") is None
    finally:
        db_module._seed_demo_data(demo)
        demo.commit()


def test_hardened_demo_user_is_not_reset(demo: Session) -> None:
    user = _user(demo, "user_read_only")
    assert user is not None
    original = (user.password_type, user.password, user.member, user.description)
    user.password_type = "mavis"
    user.password = None
    user.member = "tacacs_super_user"
    user.description = "hardened by admin"
    demo.add(user)
    demo.commit()
    try:
        init_db(demo)
        # The seed helpers themselves must be create-only, too.
        db_module._seed_demo_data(demo)
        demo.commit()
        demo.expire_all()
        after = _user(demo, "user_read_only")
        assert after is not None
        assert after.password_type == "mavis"
        assert after.password is None
        assert after.member == "tacacs_super_user"
        assert after.description == "hardened by admin"
    finally:
        restore = _user(demo, "user_read_only")
        assert restore is not None
        (
            restore.password_type,
            restore.password,
            restore.member,
            restore.description,
        ) = original
        demo.add(restore)
        demo.commit()


def test_hardened_demo_profile_and_ruleset_are_not_reset(demo: Session) -> None:
    priv = _priv_lvl_set(demo)
    rule = _super_user_rule(demo)
    original_value, original_action = priv.value, rule.action
    priv.value = "7"
    rule.action = "deny"
    demo.add(priv)
    demo.add(rule)
    demo.commit()
    try:
        init_db(demo)
        db_module._seed_demo_data(demo)
        demo.commit()
        demo.expire_all()
        assert _priv_lvl_set(demo).value == "7"
        assert _super_user_rule(demo).action == "deny"
    finally:
        priv = _priv_lvl_set(demo)
        rule = _super_user_rule(demo)
        priv.value = original_value
        rule.action = original_action
        demo.add(priv)
        demo.add(rule)
        demo.commit()


def test_existing_database_skips_all_seeding(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    def fail(_session: Session) -> None:
        raise AssertionError("seeded an already-initialized database")

    monkeypatch.setattr(db_module, "_seed_demo_data", fail)
    monkeypatch.setattr(db_module, "_seed_services", fail)
    assert db.exec(select(TacacsNgSetting)).first() is not None
    init_db(db)


@pytest.mark.parametrize("seed_demo", [True, False])
def test_first_initialization_honours_seed_demo_data(
    seed_demo: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(db_module, "_seed_demo_data", lambda _s: calls.append("demo"))
    monkeypatch.setattr(
        db_module, "_seed_services", lambda _s: calls.append("services")
    )
    monkeypatch.setattr(db_module.settings, "SEED_DEMO_DATA", seed_demo)

    # Simulate a never-initialized database inside a transaction that is rolled
    # back afterwards; init_db's commit only releases a savepoint.
    with engine.connect() as conn:
        outer = conn.begin()
        try:
            with Session(bind=conn, join_transaction_mode="create_savepoint") as s:
                s.exec(delete(TacacsNgSetting))  # type: ignore[call-overload]
                init_db(s)
                assert s.exec(select(TacacsNgSetting)).first() is not None
        finally:
            outer.rollback()

    assert calls == (["services", "demo"] if seed_demo else ["services"])


def test_siem_config_is_seeded_from_env_once(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """SIEM_* env vars seed the row on first start; the UI owns it afterwards."""
    from app.core.security import decrypt_secret
    from app.models import SiemConfig

    saved = db.get(SiemConfig, 1)
    saved_copy = saved.model_dump() if saved else None
    if saved:
        db.delete(saved)
        db.commit()
    monkeypatch.setattr(db_module.settings, "SIEM_WEBHOOK_URL", "https://hec.example/x")
    monkeypatch.setattr(db_module.settings, "SIEM_WEBHOOK_TOKEN", "tok")
    monkeypatch.setattr(db_module.settings, "SIEM_FORWARD_TACACS_EVENTS", True)
    monkeypatch.setattr(db_module.settings, "SIEM_SYSLOG_HOST", None)
    try:
        db_module._seed_siem_config(db)
        db.commit()
        cfg = db.get(SiemConfig, 1)
        assert cfg is not None
        assert cfg.enabled and cfg.ship_authentication and cfg.ship_audit
        assert not cfg.ship_access
        assert cfg.webhook_token_encrypted
        assert decrypt_secret(cfg.webhook_token_encrypted) == "tok"

        cfg.enabled = False
        cfg.webhook_url = "https://changed.example/x"
        db.add(cfg)
        db.commit()
        db_module._seed_siem_config(db)
        db.commit()
        db.expire_all()
        cfg = db.get(SiemConfig, 1)
        assert cfg is not None
        assert cfg.enabled is False
        assert cfg.webhook_url == "https://changed.example/x"
    finally:
        db.exec(delete(SiemConfig))  # type: ignore[call-overload]
        if saved_copy:
            db.add(SiemConfig(**saved_copy))
        db.commit()
