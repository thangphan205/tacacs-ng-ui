from unittest.mock import patch

from fastapi.encoders import jsonable_encoder
from pwdlib.hashers.bcrypt import BcryptHasher
from sqlmodel import Session

from app.core.security import verify_password
from app.crud import users
from app.models import User, UserCreate, UserUpdate
from tests.utils.utils import random_email, random_lower_string


def test_create_user(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = users.create_user(session=db, user_create=user_in)
    assert user.email == email
    assert hasattr(user, "hashed_password")


def test_authenticate_user(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = users.create_user(session=db, user_create=user_in)
    authenticated_user = users.authenticate(session=db, email=email, password=password)
    assert authenticated_user
    assert user.email == authenticated_user.email


def test_not_authenticate_user(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user = users.authenticate(session=db, email=email, password=password)
    assert user is None


def test_check_if_user_is_active(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password)
    user = users.create_user(session=db, user_create=user_in)
    assert user.is_active is True


def test_check_if_user_is_active_inactive(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, disabled=True)
    user = users.create_user(session=db, user_create=user_in)
    assert user.is_active


def test_check_if_user_is_superuser(db: Session) -> None:
    email = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    user = users.create_user(session=db, user_create=user_in)
    assert user.is_superuser is True


def test_check_if_user_is_superuser_normal_user(db: Session) -> None:
    username = random_email()
    password = random_lower_string()
    user_in = UserCreate(email=username, password=password)
    user = users.create_user(session=db, user_create=user_in)
    assert user.is_superuser is False


def test_get_user(db: Session) -> None:
    password = random_lower_string()
    username = random_email()
    user_in = UserCreate(email=username, password=password, is_superuser=True)
    user = users.create_user(session=db, user_create=user_in)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.email == user_2.email
    assert jsonable_encoder(user) == jsonable_encoder(user_2)


def test_update_user(db: Session) -> None:
    password = random_lower_string()
    email = random_email()
    user_in = UserCreate(email=email, password=password, is_superuser=True)
    user = users.create_user(session=db, user_create=user_in)
    new_password = random_lower_string()
    user_in_update = UserUpdate(password=new_password, is_superuser=True)
    if user.id is not None:
        users.update_user(session=db, db_user=user, user_in=user_in_update)
    user_2 = db.get(User, user.id)
    assert user_2
    assert user.email == user_2.email
    assert verify_password(new_password, user_2.hashed_password)[0]


# --- legacy bcrypt hash migration (passlib -> pwdlib) ---


def _user_with_legacy_bcrypt_hash(db: Session, password: str) -> User:
    """Create a user whose stored hash is in the pre-migration bcrypt format."""
    user = users.create_user(
        session=db, user_create=UserCreate(email=random_email(), password=password)
    )
    user.hashed_password = BcryptHasher(rounds=12).hash(password)
    db.add(user)
    db.commit()
    db.refresh(user)
    assert user.hashed_password.startswith("$2b$")
    return user


def test_authenticate_migrates_legacy_bcrypt_hash(db: Session) -> None:
    password = random_lower_string()
    user = _user_with_legacy_bcrypt_hash(db, password)

    authenticated = users.authenticate(session=db, email=user.email, password=password)

    assert authenticated is not None
    db.refresh(user)
    assert user.hashed_password.startswith("$argon2id$")


def test_authenticate_skips_rehash_on_standby(db: Session) -> None:
    """A standby node runs on a read-only replica, so it must not write."""
    password = random_lower_string()
    user = _user_with_legacy_bcrypt_hash(db, password)

    with patch("app.crud.users.settings.NODE_ROLE", "standby"):
        authenticated = users.authenticate(
            session=db, email=user.email, password=password
        )

    assert authenticated is not None
    db.refresh(user)
    assert user.hashed_password.startswith("$2b$")


def test_authenticate_does_not_rehash_argon2(db: Session) -> None:
    """Steady-state logins must cost zero extra writes."""
    password = random_lower_string()
    user = users.create_user(
        session=db, user_create=UserCreate(email=random_email(), password=password)
    )
    before = user.hashed_password
    assert before.startswith("$argon2id$")

    assert users.authenticate(session=db, email=user.email, password=password)

    db.refresh(user)
    assert user.hashed_password == before


def test_authenticate_survives_rehash_write_failure(db: Session) -> None:
    """A failed rehash write must never turn a valid login into an error."""
    password = random_lower_string()
    user = _user_with_legacy_bcrypt_hash(db, password)

    with patch.object(Session, "commit", side_effect=RuntimeError("boom")):
        authenticated = users.authenticate(
            session=db, email=user.email, password=password
        )

    assert authenticated is not None


def test_authenticate_wrong_password_does_not_rehash(db: Session) -> None:
    password = random_lower_string()
    user = _user_with_legacy_bcrypt_hash(db, password)
    before = user.hashed_password

    assert users.authenticate(session=db, email=user.email, password="wrong") is None

    db.refresh(user)
    assert user.hashed_password == before
