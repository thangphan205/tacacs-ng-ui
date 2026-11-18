"""LDAP Web UI sign-in (#404): login route, account linking, admin test routes."""

import uuid
from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.core.config import settings
from app.core.ldap_auth import LdapAuthOutcome, LdapIdentity
from app.core.security import get_password_hash
from app.crud import auth_providers as auth_providers_crud
from app.models import (
    AuditLog,
    AuthProviderConfig,
    LdapTestConnectionResponse,
    Mavis,
    User,
)

LOGIN_URL = f"{settings.API_V1_STR}/login/access-token"
LDAP_LOGIN_URL = f"{settings.API_V1_STR}/login/ldap/access-token"
ADMIN_LDAP_URL = f"{settings.API_V1_STR}/admin/auth-providers/ldap"

LDAP_CONFIG: dict[str, str] = {
    "provider_type": "freeipa",
    "hosts": "ldaps://ipa01.example.com:636, ldaps://ipa02.example.com:636",
    "base_dn": "dc=example,dc=com",
    "bind_dn": "uid=svc,cn=users,dc=example,dc=com",
}

_TEST_EMAILS = (
    "netadmin1@example.com",
    "ldap-existing@example.com",
    "ldap-passkey-only@example.com",
    "ldap-standby@example.com",
    "Ldap-Case@example.com",
    "ldap-case@example.com",
)


@pytest.fixture(autouse=True)
def clean_state(db: Session) -> Generator[None, None, None]:
    """Provider rows are singletons and these users are ours — leave no trace."""
    yield
    db.rollback()
    db.execute(delete(AuthProviderConfig))
    db.execute(delete(User).where(User.email.in_(_TEST_EMAILS)))  # type: ignore[attr-defined]
    superuser = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if superuser is not None and superuser.ldap_id is not None:
        superuser.ldap_id = None
        db.add(superuser)
    db.commit()
    db.expire_all()


def _enable_ldap(db: Session, **extra: str) -> None:
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="ldap",
        enabled=True,
        config={**LDAP_CONFIG, **extra},
        secret="bind-secret",
    )


def _fake_ldap_success(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ldap_id: str,
    email: str,
    failed_servers: list[tuple[str, str]] | None = None,
) -> list[dict[str, Any]]:
    calls: list[dict[str, Any]] = []

    def fake_auth(**kwargs: Any) -> LdapAuthOutcome:
        calls.append(kwargs)
        return LdapAuthOutcome(
            ok=True,
            reason="ok",
            message="LDAP authentication succeeded.",
            identity=LdapIdentity(
                ldap_id=ldap_id,
                user_dn=f"uid={ldap_id},cn=users,dc=example,dc=com",
                email=email,
                full_name="Directory User",
            ),
            server_used="ldaps://ipa02.example.com:636",
            failover_occurred=bool(failed_servers),
            failed_servers=failed_servers or [],
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", fake_auth)
    return calls


def _never_call_ldap(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_auth(**_kwargs: Any) -> LdapAuthOutcome:
        raise AssertionError("LDAP must not be contacted here")

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", fake_auth)


def _login(client: TestClient, username: str, password: str = "ldap-pw") -> Any:
    """LDAP sign-in."""
    return client.post(
        LDAP_LOGIN_URL, data={"username": username, "password": password}
    )


def _local_login(client: TestClient, username: str, password: str) -> Any:
    return client.post(LOGIN_URL, data={"username": username, "password": password})


# --- status / presets / MAVIS import -------------------------------------------


def test_auth_providers_status_includes_ldap(client: TestClient, db: Session) -> None:
    r = client.get(f"{settings.API_V1_STR}/auth-providers/status")
    assert r.status_code == 200
    assert r.json()["ldap"] is False

    _enable_ldap(db)
    r = client.get(f"{settings.API_V1_STR}/auth-providers/status")
    assert r.json()["ldap"] is True


def test_admin_ldap_presets_and_mavis_import(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    r = client.get(f"{ADMIN_LDAP_URL}/presets", headers=superuser_token_headers)
    assert r.status_code == 200
    presets = r.json()
    assert {"active_directory", "freeipa", "openldap", "generic"} <= set(presets)
    assert presets["active_directory"]["unique_id_attr"] == "objectGUID"

    saved: dict[str, str | None] = {}
    wanted = {
        "LDAP_HOSTS": "ldaps://ipa.example.com:636",
        "LDAP_PASSWD": "do-not-expose",
        "LDAP_SERVER_TYPE": "generic",
    }
    for key, value in wanted.items():
        row = db.exec(select(Mavis).where(Mavis.mavis_key == key)).first()
        saved[key] = row.mavis_value if row else None
        if row is None:
            row = Mavis(mavis_key=key, mavis_value=value)
        row.mavis_value = value
        db.add(row)
    db.commit()
    try:
        r = client.get(
            f"{ADMIN_LDAP_URL}/mavis-import", headers=superuser_token_headers
        )
        assert r.status_code == 200
        data = r.json()
        assert data["hosts"] == "ldaps://ipa.example.com:636"
        # MAVIS's own "generic" type is not FreeIPA.
        assert data["provider_type"] == "generic"
        assert "do-not-expose" not in str(data)
    finally:
        for key, old in saved.items():
            row = db.exec(select(Mavis).where(Mavis.mavis_key == key)).one()
            if old is None:
                db.delete(row)
            else:
                row.mavis_value = old
                db.add(row)
        db.commit()


# --- login ---------------------------------------------------------------------


def test_ldap_login_creates_read_only_user_and_preserves_local_rbac(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    # Unique per run: identical failovers are audited once per window.
    down_host = f"ipa-{uuid.uuid4().hex[:8]}.example.com"
    _fake_ldap_success(
        monkeypatch,
        ldap_id="netadmin1",
        email="netadmin1@example.com",
        failed_servers=[(f"ldaps://{down_host}:636", "Connection refused")],
    )

    r = _login(client, "netadmin1")
    assert r.status_code == 200, r.text

    user = db.exec(select(User).where(User.ldap_id == "netadmin1")).one()
    assert user.email == "netadmin1@example.com"
    assert user.is_superuser is False
    assert "LDAP" in user.login_methods

    failover = db.exec(
        select(AuditLog)
        .where(AuditLog.action == "LDAP_FAILOVER")
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    assert failover is not None
    assert down_host in (failover.description or "")

    # A local promotion survives the next LDAP sign-in.
    user.is_superuser = True
    db.add(user)
    db.commit()
    assert _login(client, "netadmin1").status_code == 200
    db.refresh(user)
    assert user.is_superuser is True


def test_ldap_group_denied_returns_generic_403(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db, required_group="custom-tacacs-group")

    def fake_auth(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False,
            reason="group_denied",
            message="User 'outsider' is not a member of required LDAP group 'custom-tacacs-group'.",
            server_used="ldaps://ipa01.example.com:636",
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", fake_auth)

    r = _login(client, "outsider")
    assert r.status_code == 403
    # The group name stays in the audit log, not in the unauthenticated response.
    assert "custom-tacacs-group" not in r.json()["detail"]
    audit = db.exec(
        select(AuditLog)
        .where(AuditLog.action == "LOGIN_FAILED", AuditLog.entity_id == "outsider")
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    assert audit is not None
    assert "custom-tacacs-group" in (audit.description or "")


def test_local_emergency_superuser_login_never_contacts_ldap(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    _never_call_ldap(monkeypatch)

    r = _local_login(
        client, settings.FIRST_SUPERUSER, settings.FIRST_SUPERUSER_PASSWORD
    )
    assert r.status_code == 200
    assert "access_token" in r.json()


@pytest.mark.parametrize("allow_email_link", ["false", "true"])
def test_ldap_never_links_to_a_superuser_by_email(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    allow_email_link: str,
) -> None:
    """A directory entry whose `mail` is the admin's must not become the admin."""
    _enable_ldap(db, allow_email_link=allow_email_link)
    _fake_ldap_success(monkeypatch, ldap_id="mallory", email=settings.FIRST_SUPERUSER)

    r = _login(client, "mallory")
    assert r.status_code == 403
    superuser = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).one()
    db.refresh(superuser)
    assert superuser.ldap_id is None


def test_ldap_links_existing_account_only_when_enabled(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    existing = User(
        email="ldap-existing@example.com",
        hashed_password=get_password_hash("local-password-1"),
        is_superuser=False,
    )
    db.add(existing)
    db.commit()
    _fake_ldap_success(monkeypatch, ldap_id="existing", email=existing.email)

    _enable_ldap(db)  # allow_email_link absent -> off
    assert _login(client, "existing").status_code == 403
    db.refresh(existing)
    assert existing.ldap_id is None

    _enable_ldap(db, allow_email_link="true")
    monkeypatch.setattr(settings, "USERS_OPEN_REGISTRATION", False)
    assert _login(client, "existing").status_code == 200
    db.refresh(existing)
    assert existing.ldap_id == "existing"


def test_passkey_only_switch_turns_off_local_passwords_not_ldap(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ "Allow password login" off hides local passwords; LDAP has its own switch."""
    _enable_ldap(db)
    auth_providers_crud.upsert_provider_config(
        session=db,
        provider="passkey",
        enabled=True,
        config={"allow_password_login": "false"},
    )
    _fake_ldap_success(monkeypatch, ldap_id="netadmin1", email="netadmin1@example.com")

    status = client.get(f"{settings.API_V1_STR}/auth-providers/status").json()
    assert status["password_login"] is False
    assert status["ldap"] is True

    r = _local_login(
        client, settings.FIRST_SUPERUSER, settings.FIRST_SUPERUSER_PASSWORD
    )
    assert r.status_code == 400
    assert "disabled by the administrator" in r.json()["detail"]

    assert _login(client, "netadmin1").status_code == 200


def test_per_user_password_flag_restricts_local_password_only(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    db.add(
        User(
            email="ldap-passkey-only@example.com",
            hashed_password=get_password_hash("local-password-1"),
            ldap_id="passkeyonly",
            password_login_disabled=True,
        )
    )
    db.commit()
    _fake_ldap_success(
        monkeypatch, ldap_id="passkeyonly", email="ldap-passkey-only@example.com"
    )

    r = _local_login(client, "ldap-passkey-only@example.com", "local-password-1")
    assert r.status_code == 400
    assert "Use a passkey" in r.json()["detail"]
    assert _login(client, "passkeyonly").status_code == 200


def test_local_endpoint_never_contacts_ldap(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A local password, or a typo of one, is never sent to the directory."""
    _enable_ldap(db)
    _never_call_ldap(monkeypatch)

    r = _local_login(client, "netadmin1", "whatever-password")
    assert r.status_code == 400
    assert r.json()["detail"] == "Incorrect email or password"


def test_ldap_endpoint_refuses_when_ldap_disabled(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _never_call_ldap(monkeypatch)
    r = _login(client, "netadmin1")
    assert r.status_code == 400
    assert r.json()["detail"] == "LDAP sign-in is not enabled"


def test_status_reports_password_login_on_by_default(client: TestClient) -> None:
    status = client.get(f"{settings.API_V1_STR}/auth-providers/status").json()
    assert status["password_login"] is True


def test_standby_does_not_provision_new_ldap_users(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    _fake_ldap_success(
        monkeypatch, ldap_id="standbyuser", email="ldap-standby@example.com"
    )
    monkeypatch.setattr(settings, "NODE_ROLE", "standby")

    r = _login(client, "standbyuser")
    assert r.status_code == 403
    assert "primary" in r.json()["detail"]
    monkeypatch.setattr(settings, "NODE_ROLE", "primary")
    assert db.exec(select(User).where(User.ldap_id == "standbyuser")).first() is None


# --- admin test routes ---------------------------------------------------------


def test_connection_test_needs_bind_password_for_new_destination(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    """The stored bind password is never sent somewhere it was not saved for."""
    _enable_ldap(db)
    secrets_used: list[str | None] = []

    def fake_check(
        *, raw_config: dict[str, Any] | None, secret: str | None
    ) -> LdapTestConnectionResponse:
        _ = raw_config
        secrets_used.append(secret)
        return LdapTestConnectionResponse(ok=True, message="ok")

    monkeypatch.setattr(
        "app.api.routes.admin_auth.check_ldap_servers_connection", fake_check
    )
    url = f"{ADMIN_LDAP_URL}/test-connection"

    # Same servers, same Bind DN: the stored secret is reused.
    r = client.post(url, headers=superuser_token_headers, json={"config": LDAP_CONFIG})
    assert r.status_code == 200, r.text
    assert secrets_used == ["bind-secret"]

    for changed in (
        {"hosts": "ldap://attacker.example.net:389"},
        {"bind_dn": "uid=other,dc=example,dc=com"},
        {"verify_tls": "false"},
    ):
        r = client.post(
            url,
            headers=superuser_token_headers,
            json={"config": {**LDAP_CONFIG, **changed}},
        )
        assert r.status_code == 400, changed
    assert secrets_used == ["bind-secret"]

    # Typing the password again is allowed.
    r = client.post(
        url,
        headers=superuser_token_headers,
        json={
            "config": {**LDAP_CONFIG, "hosts": "ldap://new.example.com"},
            "secret": "typed-again",
        },
    )
    assert r.status_code == 200
    assert secrets_used[-1] == "typed-again"


# --- directory accounts stay governed by the directory --------------------------


def _ldap_account(db: Session, email: str = "ldap-existing@example.com") -> User:
    user = User(
        email=email,
        hashed_password=get_password_hash("local-password-1"),
        ldap_id="dirbound",
    )
    db.add(user)
    db.commit()
    return user


def test_local_password_login_refused_for_ldap_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Removing a user in the directory must remove their Web UI access."""
    _never_call_ldap(monkeypatch)
    _ldap_account(db)
    r = _local_login(client, "ldap-existing@example.com", "local-password-1")
    assert r.status_code == 400
    assert "LDAP" in r.json()["detail"]


def test_password_recovery_refused_for_ldap_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    sent: list[str] = []
    monkeypatch.setattr(
        "app.api.routes.login.send_email", lambda **kw: sent.append(kw["email_to"])
    )
    _ldap_account(db)

    r = client.post(
        f"{settings.API_V1_STR}/password-recovery/ldap-existing@example.com"
    )
    assert r.status_code == 400
    assert sent == []

    # A reset token issued before the account was linked is refused too.
    from app.utils import generate_password_reset_token

    token = generate_password_reset_token(email="ldap-existing@example.com")
    r = client.post(
        f"{settings.API_V1_STR}/reset-password/",
        json={"token": token, "new_password": "Brand-new-password-1!"},
    )
    assert r.status_code == 400
    assert (
        _local_login(
            client, "ldap-existing@example.com", "Brand-new-password-1!"
        ).status_code
        == 400
    )


def test_passkeys_refused_for_ldap_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    _fake_ldap_success(monkeypatch, ldap_id="netadmin1", email="netadmin1@example.com")
    token = _login(client, "netadmin1").json()["access_token"]

    r = client.post(
        f"{settings.API_V1_STR}/passkeys/register/begin",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 400
    assert "LDAP" in r.json()["detail"]


def test_ldap_misconfiguration_is_not_reported_as_a_wrong_password(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)

    def fake_auth(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False, reason="misconfigured", message="LDAP user search failed"
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", fake_auth)
    r = _login(client, "netadmin1")
    assert r.status_code == 503
    assert "misconfigured" in r.json()["detail"]


def test_ldap_email_match_is_case_insensitive(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`Ldap-Case@…` and the directory's `ldap-case@…` are the same account."""
    db.add(
        User(
            email="Ldap-Case@example.com",
            hashed_password=get_password_hash("local-password-1"),
        )
    )
    db.commit()
    _enable_ldap(db)  # linking off
    _fake_ldap_success(monkeypatch, ldap_id="casey", email="ldap-case@example.com")

    assert _login(client, "casey").status_code == 403
    assert db.exec(select(User).where(User.ldap_id == "casey")).first() is None
    assert (
        db.exec(select(User).where(User.email == "ldap-case@example.com")).first()
        is None
    )

    _enable_ldap(db, allow_email_link="true")
    monkeypatch.setattr(settings, "USERS_OPEN_REGISTRATION", False)
    assert _login(client, "casey").status_code == 200
    linked = db.exec(select(User).where(User.ldap_id == "casey")).one()
    assert linked.email == "Ldap-Case@example.com"


# --- admin card ----------------------------------------------------------------


def test_admin_card_shows_env_ldap_settings_before_any_row(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    """Saving what the card shows must not switch off env-configured LDAP."""
    monkeypatch.setattr(settings, "LDAP_HOSTS", "ldaps://dc1.example.com")
    monkeypatch.setattr(settings, "LDAP_BASE_DN", "dc=example,dc=com")
    monkeypatch.setattr(settings, "LDAP_BIND_PASSWORD", "env-secret")

    r = client.get(ADMIN_LDAP_URL, headers=superuser_token_headers)
    assert r.status_code == 200
    body = r.json()
    assert body["enabled"] is True
    assert body["config"]["hosts"] == "ldaps://dc1.example.com"
    assert body["config"]["base_dn"] == "dc=example,dc=com"
    assert body["secret_is_set"] is True
    assert "env-secret" not in r.text

    listed = client.get(
        f"{settings.API_V1_STR}/admin/auth-providers/", headers=superuser_token_headers
    ).json()
    assert next(p for p in listed if p["provider"] == "ldap")["enabled"] is True


def test_saving_an_invalid_ldap_server_is_refused(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.put(
        ADMIN_LDAP_URL,
        headers=superuser_token_headers,
        json={
            "enabled": True,
            "config": {
                **LDAP_CONFIG,
                "hosts": "ldaps://dc1.example.com, ldap://dc2.example.com:99999",
            },
        },
    )
    assert r.status_code == 422
    assert "dc2.example.com:99999" in r.json()["detail"]


def test_email_step_never_repoints_another_directory_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Whoever sets their `mail` to Alice's must not get Alice's account."""
    alice = _ldap_account(db)  # ldap_id="dirbound"
    _enable_ldap(db, allow_email_link="true")
    _fake_ldap_success(monkeypatch, ldap_id="intruder", email=alice.email)

    assert _login(client, "intruder").status_code == 403
    db.refresh(alice)
    assert alice.ldap_id == "dirbound"


def test_single_sign_on_never_links_or_admits_an_ldap_account(db: Session) -> None:
    from fastapi import HTTPException

    from app.api.routes.oauth import _refuse_ldap_account
    from app.crud import users as users_crud

    alice = _ldap_account(db)
    google = users_crud.get_or_create_google_user(
        session=db, email=alice.email, full_name=None, google_id="g-1"
    )
    keycloak = users_crud.get_or_create_keycloak_user(
        session=db, email=alice.email, full_name=None, keycloak_id="k-1"
    )
    microsoft = users_crud.get_or_create_microsoft_user(
        session=db,
        email=alice.email,
        full_name=None,
        microsoft_id="m-1",
        allow_email_link=True,
    )
    for user in (google, keycloak, microsoft):
        assert user is not None
        with pytest.raises(HTTPException) as exc:
            _refuse_ldap_account(user)
        assert exc.value.status_code == 403
    db.refresh(alice)
    assert (alice.google_id, alice.keycloak_id, alice.microsoft_id) == (
        None,
        None,
        None,
    )


def test_saving_new_servers_needs_the_bind_password_again(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """Save, not only Test, must not repoint the stored password."""
    _enable_ldap(db)
    moved = {**LDAP_CONFIG, "hosts": "ldap://attacker.example.net:389"}

    r = client.put(
        ADMIN_LDAP_URL, headers=superuser_token_headers, json={"config": moved}
    )
    assert r.status_code == 400, r.text
    row = auth_providers_crud.get_provider_config(session=db, provider="ldap")
    assert row is not None
    db.refresh(row)
    assert "attacker" not in row.config_json

    # Same destination: no password needed; new destination with one: fine.
    r = client.put(
        ADMIN_LDAP_URL,
        headers=superuser_token_headers,
        json={"config": {**LDAP_CONFIG, "required_group": "netops"}},
    )
    assert r.status_code == 200, r.text
    r = client.put(
        ADMIN_LDAP_URL,
        headers=superuser_token_headers,
        json={"config": moved, "secret": "typed-again"},
    )
    assert r.status_code == 200, r.text


def test_failover_is_audited_once_per_window(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    down_host = f"ipa-dedupe-{uuid.uuid4().hex[:8]}.example.com"
    _fake_ldap_success(
        monkeypatch,
        ldap_id="netadmin1",
        email="netadmin1@example.com",
        failed_servers=[(f"ldaps://{down_host}:636", "down")],
    )

    def count() -> int:
        return len(
            db.exec(
                select(AuditLog).where(
                    AuditLog.action == "LDAP_FAILOVER",
                    AuditLog.description.contains(down_host),  # type: ignore[union-attr]
                )
            ).all()
        )

    before = count()
    for _ in range(3):
        assert _login(client, "netadmin1").status_code == 200
    assert count() == before + 1


def test_email_linking_is_refused_while_anyone_can_sign_up(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A self-registered account with the victim's email must not be linked."""
    db.add(
        User(
            email="ldap-existing@example.com",
            hashed_password=get_password_hash("local-password-1"),
        )
    )
    db.commit()
    monkeypatch.setattr(settings, "USERS_OPEN_REGISTRATION", True)
    _enable_ldap(db, allow_email_link="true")
    _fake_ldap_success(monkeypatch, ldap_id="victim", email="ldap-existing@example.com")

    assert _login(client, "victim").status_code == 403
    audit = db.exec(
        select(AuditLog)
        .where(AuditLog.action == "LOGIN_FAILED", AuditLog.entity_id == "victim")
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    assert audit is not None
    assert "USERS_OPEN_REGISTRATION" in (audit.description or "")


def test_standby_names_the_real_refusal(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A superuser email conflict is not "sign in on the primary first"."""
    _enable_ldap(db)
    _fake_ldap_success(monkeypatch, ldap_id="mallory", email=settings.FIRST_SUPERUSER)
    monkeypatch.setattr(settings, "NODE_ROLE", "standby")
    r = _login(client, "mallory")
    monkeypatch.setattr(settings, "NODE_ROLE", "primary")
    assert r.status_code == 403
    assert "primary" not in r.json()["detail"]


def test_username_keyed_account_is_rekeyed_to_the_unique_id(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Keyed on its username while no ID was readable: same entry, re-keyed."""
    user = User(
        email="ldap-existing@example.com",
        hashed_password=get_password_hash("local-password-1"),
        ldap_id="alice",
    )
    db.add(user)
    db.commit()
    _enable_ldap(db)  # email linking off: not needed for the same entry

    def fake_auth(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=True,
            reason="ok",
            message="ok",
            identity=LdapIdentity(
                ldap_id="0f8c-guid",
                user_dn="uid=alice,dc=example,dc=com",
                email=user.email,
                full_name=None,
                username="Alice",
            ),
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", fake_auth)
    assert _login(client, "alice").status_code == 200
    db.refresh(user)
    assert user.ldap_id == "0f8c-guid"


def test_admin_reset_lets_the_next_ldap_sign_in_relink(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    alice = _ldap_account(db)  # ldap_id="dirbound"
    _enable_ldap(db)  # email linking off
    _fake_ldap_success(monkeypatch, ldap_id="new-guid", email=alice.email)
    assert _login(client, "alice").status_code == 403  # linked elsewhere

    r = client.post(
        f"{settings.API_V1_STR}/users/{alice.id}/reset-ldap-link",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["ldap_relink_pending"] is True
    # Still a directory account meanwhile.
    assert _local_login(client, alice.email, "local-password-1").status_code == 400

    assert _login(client, "alice").status_code == 200
    db.refresh(alice)
    assert alice.ldap_id == "new-guid"
    assert db.exec(
        select(AuditLog).where(
            AuditLog.entity_id == str(alice.id),
            AuditLog.description.contains("LDAP link reset"),  # type: ignore[union-attr]
        )
    ).first()


def test_reset_ldap_link_refuses_superusers_and_local_accounts(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    superuser = db.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).one()
    r = client.post(
        f"{settings.API_V1_STR}/users/{superuser.id}/reset-ldap-link",
        headers=superuser_token_headers,
    )
    assert r.status_code == 400  # not an LDAP account

    alice = _ldap_account(db)
    alice.is_superuser = True
    db.add(alice)
    db.commit()
    r = client.post(
        f"{settings.API_V1_STR}/users/{alice.id}/reset-ldap-link",
        headers=superuser_token_headers,
    )
    assert r.status_code == 400
    assert "superuser" in r.json()["detail"]


def test_api_keys_refused_for_ldap_accounts(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    from app.crud import api_keys as api_keys_crud
    from app.models import ApiKey, ApiKeyCreate

    alice = _ldap_account(db)
    r = client.post(
        f"{settings.API_V1_STR}/api_keys/",
        headers=superuser_token_headers,
        json={"name": "ldap-key", "scopes": "mcp:read", "user_id": str(alice.id)},
    )
    assert r.status_code == 400, r.text

    # A key made before the account was linked stops working.
    _key, plaintext = api_keys_crud.create_api_key(
        session=db,
        api_key_create=ApiKeyCreate(name="pre-link", scopes="mcp:read"),
        owner_id=alice.id,
        created_by_id=alice.id,
    )
    try:
        assert api_keys_crud.resolve_api_key(plaintext) is None
    finally:
        db.execute(delete(ApiKey).where(ApiKey.user_id == alice.id))  # type: ignore[arg-type]
        db.commit()


def test_enable_switch_before_save_still_shows_env_settings(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    """Toggling creates a row with no settings: the card must keep the env's."""
    monkeypatch.setattr(settings, "LDAP_HOSTS", "ldaps://dc1.example.com")
    monkeypatch.setattr(settings, "LDAP_BASE_DN", "dc=example,dc=com")
    r = client.put(
        ADMIN_LDAP_URL, headers=superuser_token_headers, json={"enabled": False}
    )
    assert r.status_code == 200, r.text
    body = client.get(ADMIN_LDAP_URL, headers=superuser_token_headers).json()
    assert body["enabled"] is False
    assert body["config"]["hosts"] == "ldaps://dc1.example.com"
    assert body["config"]["base_dn"] == "dc=example,dc=com"


def test_provider_changes_and_test_sign_ins_are_audited(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    marker = f"grp-{uuid.uuid4().hex[:8]}"
    r = client.put(
        ADMIN_LDAP_URL,
        headers=superuser_token_headers,
        json={
            "config": {**LDAP_CONFIG, "required_group": marker},
            "secret": "s3cret-x",
        },
    )
    assert r.status_code == 200, r.text
    entry = db.exec(
        select(AuditLog).where(
            AuditLog.entity_type == "AuthProviderConfig",
            AuditLog.new_values.contains(marker),  # type: ignore[union-attr]
        )
    ).first()
    assert entry is not None
    assert "s3cret-x" not in (entry.new_values or "")
    assert entry.description == "Secret changed"

    from app.models import LdapTestAuthResponse

    monkeypatch.setattr(
        "app.api.routes.admin_auth.check_ldap_user_auth",
        lambda **_kw: LdapTestAuthResponse(ok=False, message="Invalid password"),
    )
    probe = f"probe-{uuid.uuid4().hex[:8]}"
    r = client.post(
        f"{ADMIN_LDAP_URL}/test-auth",
        headers=superuser_token_headers,
        json={"username": probe, "password": "guess", "config": LDAP_CONFIG},
    )
    assert r.status_code == 200, r.text
    entry = db.exec(
        select(AuditLog).where(
            AuditLog.action == "LDAP_TEST_AUTH",
            AuditLog.description.contains(probe),  # type: ignore[union-attr]
        )
    ).first()
    assert entry is not None
    assert "guess" not in (entry.description or "")


def test_invalid_ca_certificate_is_refused_on_save(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    r = client.put(
        ADMIN_LDAP_URL,
        headers=superuser_token_headers,
        json={
            "config": {
                **LDAP_CONFIG,
                "ca_cert_pem": "-----BEGIN CERTIFICATE-----\nMIIBtrunc\n-----END CERTIFICATE-----",
            },
            "secret": "x",
        },
    )
    assert r.status_code == 422
    assert "CA certificate" in r.json()["detail"]
