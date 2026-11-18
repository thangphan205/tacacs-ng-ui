"""LDAP Web UI sign-in (#404): login route, account linking, admin test routes."""

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
    _fake_ldap_success(
        monkeypatch,
        ldap_id="netadmin1",
        email="netadmin1@example.com",
        failed_servers=[("ldaps://ipa01.example.com:636", "Connection refused")],
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
    assert "ipa01.example.com" in (failover.description or "")

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
