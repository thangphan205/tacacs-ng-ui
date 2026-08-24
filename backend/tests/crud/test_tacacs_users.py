"""Password handling for TACACS+ device users.

The `password` column holds what tac_plus-ng parses directly: either cleartext
or a `$6$rounds=...$` sha512-crypt digest. Getting the hash-vs-plaintext
decision wrong is silent — nothing errors, the account simply stops accepting
the password its owner was given — so it is pinned down here.
"""

import pytest
from passlib.hash import sha512_crypt
from sqlmodel import Session

from app.crud import tacacs_users
from app.models import TacacsUser, TacacsUserCreate, TacacsUserUpdate
from tests.utils.utils import random_lower_string

PLAINTEXT = "Cisco12345!"

# What `openssl passwd -6 'Cisco12345!'` emits: no `rounds=` segment, unlike
# passlib's own output. Both must be recognised as already-hashed.
OPENSSL_STYLE = (
    sha512_crypt.using(rounds=5000).hash(PLAINTEXT).replace("$rounds=5000", "")
)


def _username() -> str:
    return f"u-{random_lower_string()[:10]}"


@pytest.mark.parametrize(
    "value,expected",
    [
        (sha512_crypt.hash(PLAINTEXT), True),
        (OPENSSL_STYLE, True),
        (PLAINTEXT, False),
        # A malformed digest is far likelier to be someone's unusual plaintext
        # than a real hash, so it must still be hashed. CryptContext.identify()
        # accepts these, which is why it is not what the code uses.
        ("$6$notahash", False),
        ("$6$abcdefgh$", False),
        ("$6$salt$tooshort", False),
        ("$1$abc$xxxxxxxxxxxxxxxxxxxxxx", False),
        ("$$$money", False),
        ("", False),
    ],
)
def test_is_tacacs_password_hash(value: str, expected: bool) -> None:
    assert tacacs_users.is_tacacs_password_hash(value) is expected


def test_create_hashes_a_plaintext_password(db: Session) -> None:
    username = _username()
    user = tacacs_users.create_tacacs_user(
        session=db,
        user_create=TacacsUserCreate(
            username=username,
            password_type="crypt",
            member="g1",
            password=PLAINTEXT,
        ),
    )
    try:
        assert user.password is not None
        assert user.password.startswith("$6$")
        assert sha512_crypt.verify(PLAINTEXT, user.password)
    finally:
        db.delete(user)
        db.commit()


def test_create_does_not_hash_an_already_hashed_password(db: Session) -> None:
    """A caller that pre-hashes must not end up with sha512_crypt(sha512_crypt(pw)).

    An MCP client did exactly this: it read `password login = crypt "$6$..."`
    in the syntax reference, ran `openssl passwd -6`, and sent the digest. The
    account then accepted the digest string as its password, not the password
    the operator had chosen.
    """
    username = _username()
    user = tacacs_users.create_tacacs_user(
        session=db,
        user_create=TacacsUserCreate(
            username=username,
            password_type="crypt",
            member="g1",
            password=OPENSSL_STYLE,
        ),
    )
    try:
        assert user.password == OPENSSL_STYLE
        assert sha512_crypt.verify(PLAINTEXT, user.password)
        # The failure mode this guards: the digest becoming the password.
        assert not sha512_crypt.verify(OPENSSL_STYLE, user.password)
    finally:
        db.delete(user)
        db.commit()


def test_clear_password_type_is_never_hashed(db: Session) -> None:
    username = _username()
    user = tacacs_users.create_tacacs_user(
        session=db,
        user_create=TacacsUserCreate(
            username=username,
            password_type="clear",
            member="g1",
            password=PLAINTEXT,
        ),
    )
    try:
        assert user.password == PLAINTEXT
    finally:
        db.delete(user)
        db.commit()


def test_update_hashes_a_new_plaintext_password(db: Session) -> None:
    username = _username()
    user = tacacs_users.create_tacacs_user(
        session=db,
        user_create=TacacsUserCreate(
            username=username,
            password_type="crypt",
            member="g1",
            password="OldPassw0rd!",
        ),
    )
    try:
        tacacs_users.update_tacacs_user(
            session=db,
            db_user=user,
            user_in=TacacsUserUpdate(password=PLAINTEXT),
        )
        refreshed = db.get(TacacsUser, user.id)
        assert refreshed is not None
        assert refreshed.password is not None
        assert sha512_crypt.verify(PLAINTEXT, refreshed.password)
    finally:
        db.delete(user)
        db.commit()


def test_update_leaves_an_echoed_hash_alone(db: Session) -> None:
    """Re-sending the stored hash — as a partial update does — is a no-op."""
    username = _username()
    user = tacacs_users.create_tacacs_user(
        session=db,
        user_create=TacacsUserCreate(
            username=username,
            password_type="crypt",
            member="g1",
            password=PLAINTEXT,
        ),
    )
    stored = user.password
    try:
        tacacs_users.update_tacacs_user(
            session=db,
            db_user=user,
            user_in=TacacsUserUpdate(password=stored, description="edited"),
        )
        refreshed = db.get(TacacsUser, user.id)
        assert refreshed is not None
        assert refreshed.password == stored
        assert refreshed.description == "edited"
        assert sha512_crypt.verify(PLAINTEXT, refreshed.password)
    finally:
        db.delete(user)
        db.commit()


def test_update_does_not_hash_a_supplied_digest(db: Session) -> None:
    """A fresh digest — different salt, so not equal to the stored one."""
    username = _username()
    user = tacacs_users.create_tacacs_user(
        session=db,
        user_create=TacacsUserCreate(
            username=username,
            password_type="crypt",
            member="g1",
            password="OldPassw0rd!",
        ),
    )
    try:
        assert user.password != OPENSSL_STYLE
        tacacs_users.update_tacacs_user(
            session=db,
            db_user=user,
            user_in=TacacsUserUpdate(password=OPENSSL_STYLE),
        )
        refreshed = db.get(TacacsUser, user.id)
        assert refreshed is not None
        assert refreshed.password == OPENSSL_STYLE
        assert sha512_crypt.verify(PLAINTEXT, refreshed.password)
    finally:
        db.delete(user)
        db.commit()
