from typing import Any

from passlib.context import CryptContext
from passlib.hash import sha512_crypt
from sqlmodel import Session, select

from app.models import TacacsUser, TacacsUserCreate, TacacsUserUpdate

# SHA-512 crypt hashing - compatible with tac_plus-ng "crypt" password type
tacacs_pwd_context = CryptContext(schemes=["sha512_crypt"], deprecated="auto")


def hash_tacacs_password(password: str) -> str:
    return tacacs_pwd_context.hash(password)


def is_tacacs_password_hash(value: str) -> bool:
    """True when `value` is already a complete sha512-crypt hash.

    The `password` field carries a plaintext password that this module hashes.
    Callers sometimes supply a `$6$...` digest instead — an admin pasting one
    into the UI form, an MCP client that saw `password login = crypt "$6$..."`
    in the syntax reference and produced a matching digest, or an operator
    migrating accounts from another system. Hashing that a second time stores
    `sha512_crypt(sha512_crypt(pw))`, and the account then silently rejects the
    password its owner was given.

    Deliberately stricter than `CryptContext.identify()`, which accepts a bare
    `$6$notahash`: a *malformed* digest is far more likely to be someone's
    unusual plaintext than a real hash, and must still be hashed. Requiring a
    parsed checksum draws that line.
    """
    try:
        parsed = sha512_crypt.from_string(value)
    except (ValueError, TypeError):
        return False
    return bool(parsed.checksum)


def get_tacacs_user_by_username(
    *, session: Session, username: str
) -> TacacsUser | None:
    statement = select(TacacsUser).where(TacacsUser.username == username)
    session_user = session.exec(statement).first()
    return session_user


def create_tacacs_user(
    *, session: Session, user_create: TacacsUserCreate
) -> TacacsUser:
    db_obj = TacacsUser.model_validate(user_create)
    if (
        db_obj.password_type == "crypt"
        and db_obj.password
        and not is_tacacs_password_hash(db_obj.password)
    ):
        db_obj.password = hash_tacacs_password(db_obj.password)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_tacacs_user(
    *, session: Session, db_user: TacacsUser, user_in: TacacsUserUpdate
) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    # Hash the password if type is crypt and a new plaintext password is given.
    # An already-hashed value is stored verbatim — it arrives either because the
    # caller sent a digest (see is_tacacs_password_hash) or because a partial
    # update echoed the stored hash back, and re-hashing either would lock the
    # account's owner out.
    password_type = user_data.get("password_type", db_user.password_type)
    if (
        password_type == "crypt"
        and user_data.get("password")
        and not is_tacacs_password_hash(user_data["password"])
    ):
        user_data["password"] = hash_tacacs_password(user_data["password"])
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user
