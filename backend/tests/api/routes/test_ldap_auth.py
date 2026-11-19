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
from app.crud import audit_logs as audit_logs_crud
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
    moved = {**LDAP_CONFIG, "hosts": "ldaps://attacker.example.net:636"}

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


def test_an_empty_secret_keeps_the_stored_bind_password(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """``"secret": ""`` means "unchanged", like an omitted one -- never "set it
    to empty", which would break every sign-in and pass the move guard."""
    _enable_ldap(db)
    row = auth_providers_crud.get_provider_config(session=db, provider="ldap")
    assert row is not None
    stored = row.encrypted_secret

    r = client.put(
        ADMIN_LDAP_URL,
        headers=superuser_token_headers,
        json={"config": {**LDAP_CONFIG, "required_group": "netops"}, "secret": ""},
    )
    assert r.status_code == 200, r.text
    db.refresh(row)
    assert row.encrypted_secret == stored

    # Nor does it count as the retyped password a new destination needs.
    moved = {**LDAP_CONFIG, "hosts": "ldaps://attacker.example.net:636"}
    r = client.put(
        ADMIN_LDAP_URL,
        headers=superuser_token_headers,
        json={"config": moved, "secret": ""},
    )
    assert r.status_code == 400, r.text


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


# --- review round 4 ----------------------------------------------------------


def _local_user(db: Session, email: str = "ldap-existing@example.com") -> User:
    user = User(email=email, hashed_password=get_password_hash("local-password-1"))
    db.add(user)
    db.commit()
    return user


def test_standby_never_hands_out_an_unlinked_account(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _local_user(db)
    monkeypatch.setattr(settings, "USERS_OPEN_REGISTRATION", False)
    _enable_ldap(db, allow_email_link="true")
    _fake_ldap_success(monkeypatch, ldap_id="existing", email=user.email)
    monkeypatch.setattr(settings, "NODE_ROLE", "standby")
    r = _login(client, "existing")
    monkeypatch.setattr(settings, "NODE_ROLE", "primary")
    assert r.status_code == 403
    db.refresh(user)
    assert user.ldap_id is None


def test_concurrent_first_sign_in_returns_the_account_not_a_500(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.crud import users as users_crud

    winner = User(
        email="ldap-existing@example.com",
        hashed_password=get_password_hash("x-password-1"),
        ldap_id="raced",
    )
    db.add(winner)
    db.commit()
    # Another worker's insert landed between our lookups and our commit.
    real = users_crud.get_user_by_ldap_id
    calls = {"n": 0}

    def miss_once(*, session: Session, ldap_id: str) -> User | None:
        calls["n"] += 1
        return None if calls["n"] == 1 else real(session=session, ldap_id=ldap_id)

    monkeypatch.setattr(users_crud, "get_user_by_ldap_id", miss_once)
    monkeypatch.setattr(users_crud, "get_user_by_email_ci", lambda **_kw: None)
    user, refusal = users_crud.get_or_create_ldap_user(
        session=db,
        ldap_id="raced",
        email="ldap-existing@example.com",
        full_name=None,
        allow_email_link=False,
    )
    assert refusal is None
    assert user is not None and user.id == winner.id


def test_ldap_tokens_are_shorter_lived(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import jwt

    monkeypatch.setattr(settings, "LDAP_ACCESS_TOKEN_EXPIRE_MINUTES", 30)
    _enable_ldap(db)
    _fake_ldap_success(monkeypatch, ldap_id="netadmin1", email="netadmin1@example.com")
    token = _login(client, "netadmin1").json()["access_token"]
    claims = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
    import time

    assert claims["exp"] - time.time() < 31 * 60


def test_failed_ldap_sign_ins_are_throttled(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    _fake_ldap_success(monkeypatch, ldap_id="x", email="netadmin1@example.com")

    def refuse(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False, reason="invalid_credentials", message="Invalid password"
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", refuse)
    monkeypatch.setattr(settings, "LOGIN_THROTTLE_MAX_FAILURES_PER_USER", 3)
    name = f"victim-{uuid.uuid4().hex[:8]}"
    for _ in range(3):
        assert _login(client, name).status_code == 400
    r = _login(client, name)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    # Another username is unaffected, and the local endpoint never locks a name.
    assert _login(client, f"other-{uuid.uuid4().hex[:8]}").status_code == 400
    for _ in range(5):
        _local_login(client, name, "wrong-password-1")
    assert _local_login(client, name, "wrong-password-1").status_code == 400


def test_failed_sign_ins_from_one_address_are_throttled_on_both_endpoints(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    ip = f"203.0.113.{uuid.uuid4().int % 250 + 1}"
    monkeypatch.setattr(settings, "LOGIN_THROTTLE_MAX_FAILURES_PER_IP", 3)
    # Behind nginx + Traefik: "<caller-written>, <client>, <proxy>". The caller
    # rotates the leftmost entry on every request; the client is the one the
    # proxies saw.
    for i in range(3):
        r = client.post(
            LOGIN_URL,
            data={"username": f"nobody{i}@example.com", "password": "x" * 12},
            headers={"X-Forwarded-For": f"198.51.100.{i + 1}, {ip}, 172.18.0.2"},
        )
        assert r.status_code == 400
    r = client.post(
        LDAP_LOGIN_URL,
        data={"username": "u", "password": "p"},
        headers={"X-Forwarded-For": f"192.0.2.99, {ip}, 172.18.0.2"},
    )
    assert r.status_code == 429


def test_short_forwarded_chain_keeps_sign_in_working_and_audit_consistent(
    client: TestClient, db: Session
) -> None:
    """nginx-only, Vite dev and CI send fewer entries than the hop count. They
    must not share a bucket or lose their address: it falls back to the first
    entry, as in every other audit row."""
    ip = f"203.0.113.{uuid.uuid4().int % 250 + 1}"
    name = f"short-{uuid.uuid4().hex[:8]}@example.com"
    r = client.post(
        LOGIN_URL,
        data={"username": name, "password": "x" * 12},
        headers={"X-Forwarded-For": ip},
    )
    assert r.status_code == 400
    row = db.exec(
        select(AuditLog).where(
            AuditLog.action == "LOGIN_FAILED", AuditLog.entity_id == name
        )
    ).first()
    assert row is not None and row.ip_address == ip


def test_ldap_sign_ins_in_flight_are_capped(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dead directory must not let a flood fill the threadpool: past the cap
    a request is refused at once, without touching the directory."""
    _enable_ldap(db)
    monkeypatch.setattr(settings, "LDAP_MAX_CONCURRENT_SIGNINS", 2)
    calls: list[int] = []

    def never(**_kwargs: Any) -> LdapAuthOutcome:
        calls.append(1)
        raise AssertionError("directory must not be contacted")

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", never)
    from app.api.routes.login import _ldap_semaphore

    slots = _ldap_semaphore()
    assert slots.acquire(blocking=False) and slots.acquire(blocking=False)
    try:
        r = client.post(
            LDAP_LOGIN_URL,
            data={"username": "u", "password": "p"},
            headers={"X-Forwarded-For": "203.0.113.61, 172.18.0.2"},
        )
    finally:
        slots.release()
        slots.release()
    assert r.status_code == 503
    assert r.headers.get("Retry-After") == "5"
    assert calls == []
    # Slots free again: the next request reaches the directory.
    _fake_ldap_success(monkeypatch, ldap_id="cap1", email="netadmin1@example.com")
    assert _login(client, "netadmin1").status_code == 200


def test_database_connection_is_released_before_the_directory_call(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Blocking directory I/O must not hold a pooled connection idle in a
    transaction: with the directory down that would pin up to
    LDAP_MAX_CONCURRENT_SIGNINS connections per worker."""
    from app.core.db import engine

    _enable_ldap(db)
    during: list[int] = []

    def stub(**_kwargs: Any) -> LdapAuthOutcome:
        during.append(engine.pool.checkedout())  # type: ignore[attr-defined]
        return LdapAuthOutcome(
            ok=False, reason="invalid_credentials", message="Invalid password"
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", stub)
    before = engine.pool.checkedout()  # type: ignore[attr-defined]
    r = client.post(
        LDAP_LOGIN_URL,
        data={"username": f"pool-{uuid.uuid4().hex[:8]}", "password": "p"},
        headers={"X-Forwarded-For": "203.0.113.77, 172.18.0.2"},
    )
    assert r.status_code == 400
    assert during and during[0] <= before, (before, during)


def test_overlong_user_agent_is_audited_not_a_server_error(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)
    name = f"ua-{uuid.uuid4().hex[:8]}"

    def refuse(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False, reason="invalid_credentials", message="Invalid password"
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", refuse)
    r = client.post(
        LDAP_LOGIN_URL,
        data={"username": name, "password": "p"},
        headers={"User-Agent": "A" * 700},
    )
    assert r.status_code == 400
    row = db.exec(
        select(AuditLog).where(
            AuditLog.action == "LOGIN_FAILED", AuditLog.entity_id == name
        )
    ).first()
    assert row is not None and len(row.user_agent or "") == 512

    # A correct password with a long User-Agent signs in.
    _fake_ldap_success(monkeypatch, ldap_id="ua1", email="netadmin1@example.com")
    r = client.post(
        LDAP_LOGIN_URL,
        data={"username": "netadmin1", "password": "p"},
        headers={"User-Agent": "B" * 700},
    )
    assert r.status_code == 200, r.text


def test_ldap_throttle_is_per_username_and_address_and_ignores_case(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)

    def refuse(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False, reason="invalid_credentials", message="Invalid password"
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", refuse)
    monkeypatch.setattr(settings, "LOGIN_THROTTLE_MAX_FAILURES_PER_USER", 3)
    base = uuid.uuid4().hex[:8]
    ip = f"203.0.113.{uuid.uuid4().int % 250 + 1}"
    mine = {"X-Forwarded-For": f"{ip}, 172.18.0.2"}

    def attempt(name: str, headers: dict[str, str]) -> int:
        return client.post(
            LDAP_LOGIN_URL,
            data={"username": name, "password": "p"},
            headers=headers,
        ).status_code

    # Case and padding variants are one account.
    assert attempt(f"Alice-{base}", mine) == 400
    assert attempt(f"aLICE-{base}", mine) == 400
    assert attempt(f" alice-{base} ", mine) == 400
    assert attempt(f"alice-{base}", mine) == 429
    # A stranger at another address cannot lock the user out.
    other = {"X-Forwarded-For": "198.51.100.7, 172.18.0.2"}
    assert attempt(f"alice-{base}", other) == 400


def test_ldap_throttle_without_a_client_address_never_keys_on_the_username(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No resolvable address must not turn the pair key into a username key."""
    _enable_ldap(db)

    def refuse(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False, reason="invalid_credentials", message="Invalid password"
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", refuse)
    monkeypatch.setattr(settings, "LOGIN_THROTTLE_MAX_FAILURES_PER_USER", 2)
    name = f"bob-{uuid.uuid4().hex[:8]}"
    # The user's failures from many addresses (a stranger guessing at them).
    for n in range(3):
        r = client.post(
            LDAP_LOGIN_URL,
            data={"username": name, "password": "p"},
            headers={"X-Forwarded-For": f"198.51.100.{n + 20}, 172.18.0.2"},
        )
        assert r.status_code == 400

    def no_address(_request: Any) -> None:
        return None

    monkeypatch.setattr("app.api.routes.login.get_client_ip", no_address)
    r = client.post(LDAP_LOGIN_URL, data={"username": name, "password": "p"})
    assert r.status_code == 400, r.text


def test_directory_outage_is_not_counted_as_failed_logins(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)

    message = f"No LDAP server reachable ({uuid.uuid4().hex[:8]})"

    def down(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(ok=False, reason="unavailable", message=message)

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", down)
    monkeypatch.setattr(settings, "LOGIN_THROTTLE_MAX_FAILURES_PER_IP", 3)
    monkeypatch.setattr(settings, "LOGIN_THROTTLE_MAX_FAILURES_PER_USER", 3)
    name = f"outage-{uuid.uuid4().hex[:8]}"
    headers = {"X-Forwarded-For": f"203.0.113.{uuid.uuid4().int % 250 + 1}, 172.18.0.2"}

    def ldap() -> int:
        return client.post(
            LDAP_LOGIN_URL,
            data={"username": name, "password": "p"},
            headers=headers,
        ).status_code

    for _ in range(7):
        assert ldap() == 503  # never 429
    # The local administrator behind the same address is not locked out.
    r = client.post(
        LOGIN_URL,
        data={"username": f"{name}@example.com", "password": "wrong-password-1"},
        headers=headers,
    )
    assert r.status_code == 400
    failed = db.exec(
        select(AuditLog).where(
            AuditLog.action == "LOGIN_FAILED", AuditLog.entity_id == name
        )
    ).all()
    assert [a for a in failed if "unavailable" in (a.description or "")] == []
    # Seven requests, one row: nothing else bounds LOGIN_ERROR, so a loop
    # against a down directory must not write a row (and SIEM event) each.
    errors = db.exec(
        select(AuditLog).where(
            AuditLog.action == "LOGIN_ERROR",
            AuditLog.description.contains(message),  # type: ignore[union-attr]
        )
    ).all()
    assert len(errors) == 1


def test_failover_audit_row_normalises_and_bounds_the_username(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)

    def partial(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False,
            reason="invalid_credentials",
            message="Invalid password",
            server_used="ldaps://b",
            failed_servers=[("ldaps://a", "timeout")],
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", partial)
    monkeypatch.setattr(audit_logs_crud, "recent_audit_log_exists", lambda **_k: False)
    r = client.post(
        LDAP_LOGIN_URL,
        data={"username": "  Mixed" + "X" * 400, "password": "p"},
        headers={"X-Forwarded-For": "203.0.113.40, 172.18.0.2"},
    )
    assert r.status_code == 400  # not a 500 from the audit insert
    row = db.exec(
        select(AuditLog)
        .where(AuditLog.action == "LDAP_FAILOVER")
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    assert row is not None
    assert row.user_email == ("mixed" + "x" * 400)[:255]


def test_overlong_username_is_audited_not_a_server_error(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    _enable_ldap(db)

    def refuse(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False, reason="invalid_credentials", message="Invalid password"
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", refuse)
    long_name = "u" * 400
    r = client.post(
        LDAP_LOGIN_URL,
        data={"username": long_name, "password": "p"},
        headers={"X-Forwarded-For": "203.0.113.9, " + "1" * 80 + ", 172.18.0.2"},
    )
    assert r.status_code == 400
    row = db.exec(
        select(AuditLog).where(
            AuditLog.action == "LOGIN_FAILED", AuditLog.entity_id == "u" * 255
        )
    ).first()
    assert row is not None
    assert row.ip_address is None or len(row.ip_address) <= 45


def test_inactive_ldap_account_attempt_is_audited(
    client: TestClient, db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = _ldap_account(db)
    user.is_active = False
    db.add(user)
    db.commit()
    _enable_ldap(db)
    _fake_ldap_success(monkeypatch, ldap_id="dirbound", email=user.email)
    assert _login(client, "dirbound").status_code == 400
    audit = db.exec(
        select(AuditLog).where(
            AuditLog.action == "LOGIN_FAILED",
            AuditLog.entity_id == "dirbound",
            AuditLog.description.contains("inactive"),  # type: ignore[union-attr]
        )
    ).first()
    assert audit is not None


def test_card_fills_keys_a_partial_saved_config_lacks(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    monkeypatch.setattr(settings, "LDAP_HOSTS", "ldaps://dc1.example.com")
    monkeypatch.setattr(settings, "LDAP_BASE_DN", "dc=example,dc=com")
    r = client.put(
        ADMIN_LDAP_URL,
        headers=superuser_token_headers,
        json={"config": {"allow_email_link": "true", "required_group": ""}},
    )
    assert r.status_code == 200, r.text
    config = client.get(ADMIN_LDAP_URL, headers=superuser_token_headers).json()[
        "config"
    ]
    assert config["hosts"] == "ldaps://dc1.example.com"
    assert config["base_dn"] == "dc=example,dc=com"
    assert config["allow_email_link"] == "true"
    assert config["required_group"] == ""  # saved empty stays empty


def test_card_asks_for_the_bind_password_when_it_cannot_be_decrypted(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    _enable_ldap(db)

    def broken(_row: Any) -> str:
        raise ValueError("bad token")

    monkeypatch.setattr(auth_providers_crud, "resolve_provider_secret", broken)
    body = client.get(ADMIN_LDAP_URL, headers=superuser_token_headers).json()
    assert body["secret_is_set"] is False
    assert "_secret_undecryptable" not in body["config"]
    enabled, cfg, secret = auth_providers_crud.ldap_login_settings(session=db)
    assert enabled and secret is None and cfg["_secret_undecryptable"] is True


def test_saving_cleartext_or_placeholderless_settings_is_refused(
    client: TestClient, superuser_token_headers: dict[str, str]
) -> None:
    def save(**extra: str) -> Any:
        return client.put(
            ADMIN_LDAP_URL,
            headers=superuser_token_headers,
            json={"config": {**LDAP_CONFIG, **extra}, "secret": "x"},
        )

    r = save(hosts="ldap://dc1.example.com:389")
    assert r.status_code == 422 and "without encryption" in r.json()["detail"]
    assert save(hosts="ldap://dc1.example.com:389", start_tls="true").status_code == 200
    assert (
        save(hosts="ldap://dc1.example.com:389", allow_insecure="true").status_code
        == 200
    )
    r = save(user_search_filter="(uid=svc-account)")
    assert r.status_code == 422 and "{username}" in r.json()["detail"]


def test_concurrent_failover_audits_are_serialised(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The dedupe takes the advisory lock before it checks."""
    from app.api.routes import login as login_routes
    from app.crud import audit_logs as audit_logs_crud

    order: list[str] = []

    def lock(_session: Session) -> None:
        order.append("lock")

    def exists(**_kwargs: Any) -> bool:
        order.append("check")
        return True

    monkeypatch.setattr(audit_logs_crud, "lock_audit_dedupe", lock)
    monkeypatch.setattr(audit_logs_crud, "recent_audit_log_exists", exists)
    login_routes._audit_ldap_failover(
        db,
        outcome_server=None,
        failed_servers=[("ldaps://x.example.com:636", "down")],
        username="u",
        user_agent=None,
        ip=None,
    )
    assert order == ["lock", "check"]


def test_a_directory_id_spelled_like_a_relink_marker_is_refused(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    superuser_token_headers: dict[str, str],
) -> None:
    """`relink:<uuid>` is what a reset stores; an entry whose identifier is
    spelled that way must not sign in as the reset account."""
    alice = _ldap_account(db)
    r = client.post(
        f"{settings.API_V1_STR}/users/{alice.id}/reset-ldap-link",
        headers=superuser_token_headers,
    )
    assert r.status_code == 200, r.text
    _enable_ldap(db)
    _fake_ldap_success(
        monkeypatch, ldap_id=f"RELINK:{alice.id}", email="ldap-standby@example.com"
    )
    r = _login(client, f"relink:{alice.id}")
    assert r.status_code == 403
    db.refresh(alice)
    assert alice.ldap_relink_pending
    assert db.exec(
        select(AuditLog).where(
            AuditLog.action == "LOGIN_FAILED",
            AuditLog.description.contains("reserved relink: prefix"),  # type: ignore[union-attr]
        )
    ).first()


def test_failed_ldap_sign_ins_are_throttled_on_a_standby(
    client: TestClient,
    db: Session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
) -> None:
    """A standby writes no audit rows; its failures are still counted."""
    import tempfile

    _enable_ldap(db)

    def refuse(**_kwargs: Any) -> LdapAuthOutcome:
        return LdapAuthOutcome(
            ok=False, reason="invalid_credentials", message="Invalid password"
        )

    monkeypatch.setattr("app.api.routes.login.authenticate_ldap_user", refuse)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(settings, "LOGIN_THROTTLE_MAX_FAILURES_PER_USER", 3)
    monkeypatch.setattr(settings, "NODE_ROLE", "standby")
    name = f"victim-{uuid.uuid4().hex[:8]}"
    for _ in range(3):
        assert _login(client, name).status_code == 400
    assert _login(client, name).status_code == 429
    monkeypatch.setattr(settings, "NODE_ROLE", "primary")
    # Nothing reached the (replicated) audit table.
    assert not db.exec(select(AuditLog).where(AuditLog.user_email == name)).first()
    # The primary counts its own rows, not the standby's file.
    assert _login(client, name).status_code == 400


def test_an_over_long_user_agent_never_fails_an_audited_change(
    client: TestClient, db: Session, superuser_token_headers: dict[str, str]
) -> None:
    """The change is committed before its audit row is built: a header past
    the column must be cut, not answer 500 with the change live and unlogged."""
    r = client.put(
        ADMIN_LDAP_URL,
        headers={**superuser_token_headers, "User-Agent": "U" * 2000},
        json={"enabled": False, "config": LDAP_CONFIG, "secret": "bind-secret"},
    )
    assert r.status_code == 200, r.text
    row = db.exec(
        select(AuditLog)
        .where(AuditLog.entity_type == "AuthProviderConfig")
        .order_by(AuditLog.created_at.desc())  # type: ignore[attr-defined]
    ).first()
    assert row is not None and row.user_agent == "U" * 512
