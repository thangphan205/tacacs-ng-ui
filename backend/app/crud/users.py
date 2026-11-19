import logging
import secrets
import uuid
from typing import Any

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from app.core.config import settings
from app.core.security import get_password_hash, verify_password
from app.models import (
    LDAP_RELINK_PREFIX,
    Item,
    ItemCreate,
    User,
    UserCreate,
    UserUpdate,
)

logger = logging.getLogger(__name__)


def create_user(*, session: Session, user_create: UserCreate) -> User:
    db_obj = User.model_validate(
        user_create, update={"hashed_password": get_password_hash(user_create.password)}
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_user(*, session: Session, db_user: User, user_in: UserUpdate) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    if "password" in user_data:
        password = user_data["password"]
        hashed_password = get_password_hash(password)
        extra_data["hashed_password"] = hashed_password
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user


def get_user_by_email(*, session: Session, email: str) -> User | None:
    statement = select(User).where(User.email == email)
    session_user = session.exec(statement).first()
    return session_user


def get_user_by_email_ci(*, session: Session, email: str) -> User | None:
    """Case-insensitive email lookup, preferring an exact match.

    Stored emails keep the case of their local part (``Admin@corp.com``), so
    an exact lookup of a directory's ``admin@corp.com`` would miss it.
    """
    exact = get_user_by_email(session=session, email=email)
    if exact is not None:
        return exact
    statement = select(User).where(func.lower(User.email) == email.strip().lower())
    return session.exec(statement).first()


def authenticate(*, session: Session, email: str, password: str) -> User | None:
    db_user = get_user_by_email(session=session, email=email)
    if not db_user:
        return None
    valid, updated_hash = verify_password(password, db_user.hashed_password)
    if not valid:
        return None
    if updated_hash is not None:
        _persist_rehashed_password(
            session=session, db_user=db_user, updated_hash=updated_hash
        )
    return db_user


def _persist_rehashed_password(
    *, session: Session, db_user: User, updated_hash: str
) -> None:
    """Transparently upgrade a legacy bcrypt hash to argon2 on successful login.

    Best effort by design: a failed write must never turn a valid login into an
    error, and must never block the token from being issued. The user simply
    keeps their old hash and we try again on their next login.

    Standby nodes run against a read-only PostgreSQL replica where any write
    raises, so skip it there entirely — same rule as
    crud.audit_logs.create_audit_log.
    """
    if settings.NODE_ROLE == "standby":
        return
    try:
        db_user.hashed_password = updated_hash
        session.add(db_user)
        session.commit()
        session.refresh(db_user)
    except Exception:
        session.rollback()
        logger.warning(
            "Could not persist rehashed password for user %s", db_user.id, exc_info=True
        )


def get_user_by_google_id(*, session: Session, google_id: str) -> User | None:
    return session.exec(select(User).where(User.google_id == google_id)).first()


def get_or_create_google_user(
    *, session: Session, email: str, full_name: str | None, google_id: str
) -> User:
    # 1. Already linked via google_id
    user = get_user_by_google_id(session=session, google_id=google_id)
    if user:
        return user

    # 2. Existing account with same email — link it, unless it belongs to
    # the directory (the route refuses LDAP accounts)
    user = get_user_by_email(session=session, email=email)
    if user and user.ldap_id:
        return user
    if user:
        user.google_id = google_id
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    # 3. New user — create with random unguessable password
    user = User(
        email=email,
        full_name=full_name,
        is_active=True,
        is_superuser=False,
        hashed_password=get_password_hash(secrets.token_hex(32)),
        google_id=google_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_keycloak_id(*, session: Session, keycloak_id: str) -> User | None:
    return session.exec(select(User).where(User.keycloak_id == keycloak_id)).first()


def get_or_create_keycloak_user(
    *, session: Session, email: str, full_name: str | None, keycloak_id: str
) -> User:
    # 1. Already linked via keycloak_id
    user = get_user_by_keycloak_id(session=session, keycloak_id=keycloak_id)
    if user:
        return user

    # 2. Existing account with same email — link it, unless it belongs to
    # the directory (the route refuses LDAP accounts)
    user = get_user_by_email(session=session, email=email)
    if user and user.ldap_id:
        return user
    if user:
        user.keycloak_id = keycloak_id
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    # 3. New user — create with random unguessable password
    user = User(
        email=email,
        full_name=full_name,
        is_active=True,
        is_superuser=False,
        hashed_password=get_password_hash(secrets.token_hex(32)),
        keycloak_id=keycloak_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_microsoft_id(*, session: Session, microsoft_id: str) -> User | None:
    return session.exec(select(User).where(User.microsoft_id == microsoft_id)).first()


def get_or_create_microsoft_user(
    *,
    session: Session,
    email: str,
    full_name: str | None,
    microsoft_id: str,
    allow_email_link: bool,
) -> User | None:
    """Find, link or create the user for a Microsoft identity.

    Returns ``None`` when an account with this email exists but is not yet
    linked and ``allow_email_link`` is false. Entra's ``email`` claim is
    mutable and unverified in multi-tenant apps, so linking on it there would
    let any tenant admin take over a local account (the "nOAuth" attack).
    """
    # 1. Already linked via microsoft_id
    user = get_user_by_microsoft_id(session=session, microsoft_id=microsoft_id)
    if user:
        return user

    # 2. Existing account with same email — link it, only when the email is trusted
    user = get_user_by_email(session=session, email=email)
    if user and user.ldap_id:
        return user  # the route refuses LDAP accounts; never link onto one
    if user:
        if not allow_email_link:
            return None
        user.microsoft_id = microsoft_id
        session.add(user)
        session.commit()
        session.refresh(user)
        return user

    # 3. New user — create with random unguessable password
    user = User(
        email=email,
        full_name=full_name,
        is_active=True,
        is_superuser=False,
        hashed_password=get_password_hash(secrets.token_hex(32)),
        microsoft_id=microsoft_id,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def get_user_by_ldap_id(*, session: Session, ldap_id: str) -> User | None:
    return session.exec(select(User).where(User.ldap_id == ldap_id)).first()


# An account an administrator reset with "Reset LDAP link" keeps an
# ``ldap_id`` of LDAP_RELINK_PREFIX + its id: still a directory account (truthy,
# so local passwords, passkeys, SSO and API keys stay refused), and the next
# LDAP sign-in with its email re-links it even when email linking is off.
# Unique per user, as the column is.


def is_ldap_relink_pending(user: User) -> bool:
    return user.ldap_relink_pending


def mark_ldap_relink(*, session: Session, user: User) -> User:
    """Let the next LDAP sign-in with this account's email link it again.

    For after the directory's identifier changed (a new Unique ID Attribute
    or provider type), which would otherwise lock every account out: the email
    step never re-points an account already linked to another entry.
    """
    user.ldap_id = f"{LDAP_RELINK_PREFIX}{user.id}"
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


# Why `get_or_create_ldap_user` gave no account.
LDAP_NEW_ON_STANDBY = "new_on_standby"
LDAP_EMAIL_LINK_OFF = "email_link_off"
LDAP_SUPERUSER = "superuser"
LDAP_LINKED_ELSEWHERE = "linked_elsewhere"
LDAP_OPEN_REGISTRATION = "open_registration"


def _link_ldap(
    *, session: Session, user: User, ldap_id: str, full_name: str | None
) -> User | None:
    """Link `user` to the directory entry; None when another request won.

    A compare-and-set on the ``ldap_id`` this request read: the unique index
    only stops two requests writing the *same* id, so two entries sharing a
    ``mail`` could otherwise each pass the checks above on an unlinked account
    and the second UPDATE would silently take the account the first one linked.
    """
    expected = user.ldap_id
    values: dict[str, str] = {"ldap_id": ldap_id}
    if full_name and not user.full_name:
        values["full_name"] = full_name
    try:
        result = session.execute(
            update(User)
            .where(User.id == user.id, User.ldap_id.is_not_distinct_from(expected))  # type: ignore[union-attr]
            .values(**values)
        )
        session.commit()
    except IntegrityError:
        # Two first sign-ins of the same entry raced on the unique ldap_id.
        session.rollback()
        return get_user_by_ldap_id(session=session, ldap_id=ldap_id)
    if result.rowcount == 0:  # type: ignore[attr-defined]
        # The row changed since it was read: another entry linked it first. It
        # is still ours only if that other request was this same entry.
        return get_user_by_ldap_id(session=session, ldap_id=ldap_id)
    session.refresh(user)
    return user


def get_or_create_ldap_user(
    *,
    session: Session,
    ldap_id: str,
    email: str,
    full_name: str | None,
    allow_email_link: bool,
    username: str = "",
) -> tuple[User | None, str | None]:
    """Find, link or create the user for an authenticated LDAP identity.

    Returns ``(user, None)``, or ``(None, reason)`` when the identity cannot be
    given an account — one of the ``LDAP_*`` reasons above:

    - ``linked_elsewhere``: an account with this email is already linked to a
      *different* directory entry; never re-pointed, whatever
      ``allow_email_link`` says. Two exceptions, both the same person: an
      administrator reset the link (`mark_ldap_relink`), or the account was
      keyed on this very username because the entry had no readable unique ID
      then;
    - ``email_link_off`` / ``superuser``: an unlinked account with this email
      exists and email linking is off, or it is a superuser. LDAP ``mail`` is
      directory data that help desks and self-service portals can often edit,
      so linking on it would let whoever controls an entry's ``mail`` sign in
      as the local account holding that address — including the emergency
      administrator;
    - ``open_registration``: linking would be allowed, but anyone can sign up
      (``USERS_OPEN_REGISTRATION``), so the "existing" account may be one an
      attacker registered with the victim's address — and its tokens would
      survive the link;
    - ``new_on_standby``: the identity is new, or would be linked to an
      existing account, and this node is a standby (read-only replica).

    Authentication only: an existing account keeps its ``is_superuser`` and
    ``is_active`` flags, and new accounts are created read-only.
    """
    normalized_id = ldap_id.strip().lower()
    normalized_email = email.strip().lower()
    standby = settings.NODE_ROLE == "standby"

    # 1. Already linked via ldap_id
    user = get_user_by_ldap_id(session=session, ldap_id=normalized_id)
    if user:
        return user, None

    # 2. Existing account with same email. Case-insensitive: a miss here would
    # create a near-duplicate account next to `Admin@corp.com` and skip the
    # superuser protection below.
    user = get_user_by_email_ci(session=session, email=normalized_email)
    if user:
        if user.ldap_id is not None:
            # Keyed on this username while the entry had no readable unique
            # ID: same username and same email, so the same directory entry.
            same_entry = bool(username) and user.ldap_id == username.strip().lower()
            admin_reset = is_ldap_relink_pending(user)
            if not (same_entry or admin_reset):
                # Already another directory entry's account: re-pointing it
                # would hand it to whoever can set their `mail` to this address.
                logger.warning(
                    "LDAP identity %s refused: %s is already linked to another "
                    "directory entry",
                    normalized_id,
                    user.email,
                )
                return None, LDAP_LINKED_ELSEWHERE
            if admin_reset and user.is_superuser:
                # Until its owner signs in, whoever's `mail` matches would claim
                # it: demote, reset, let them sign in, then promote again.
                return None, LDAP_SUPERUSER
            if standby:
                return None, LDAP_NEW_ON_STANDBY
            linked = _link_ldap(
                session=session, user=user, ldap_id=normalized_id, full_name=full_name
            )
            return (linked, None) if linked else (None, LDAP_LINKED_ELSEWHERE)
        if user.is_superuser:
            return None, LDAP_SUPERUSER
        if not allow_email_link:
            return None, LDAP_EMAIL_LINK_OFF
        if settings.USERS_OPEN_REGISTRATION:
            return None, LDAP_OPEN_REGISTRATION
        if standby:
            # The link is a write: refuse like any first sign-in. Returning the
            # unlinked account would skip every LDAP-only protection on it.
            return None, LDAP_NEW_ON_STANDBY
        linked = _link_ldap(
            session=session, user=user, ldap_id=normalized_id, full_name=full_name
        )
        return (linked, None) if linked else (None, LDAP_LINKED_ELSEWHERE)

    # 3. New user — created on the primary only, with a random unguessable
    # password and the read-only role
    if standby:
        return None, LDAP_NEW_ON_STANDBY
    user = User(
        email=normalized_email,
        full_name=full_name,
        is_active=True,
        is_superuser=False,
        hashed_password=get_password_hash(secrets.token_hex(32)),
        ldap_id=normalized_id,
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError:
        # A concurrent first sign-in (double submit, another worker) created it.
        session.rollback()
        existing = get_user_by_ldap_id(session=session, ldap_id=normalized_id)
        if existing is not None:
            return existing, None
        return None, LDAP_LINKED_ELSEWHERE  # the email is taken by another account
    session.refresh(user)
    return user, None


def create_item(*, session: Session, item_in: ItemCreate, owner_id: uuid.UUID) -> Item:
    db_item = Item.model_validate(item_in, update={"owner_id": owner_id})
    session.add(db_item)
    session.commit()
    session.refresh(db_item)
    return db_item
