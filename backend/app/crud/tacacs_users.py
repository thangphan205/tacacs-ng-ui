from typing import Any

from passlib.context import CryptContext
from sqlmodel import Session, select
from app.models import TacacsUser, TacacsUserCreate, TacacsUserUpdate

# SHA-512 crypt hashing - compatible with tac_plus-ng "crypt" password type
tacacs_pwd_context = CryptContext(schemes=["sha512_crypt"], deprecated="auto")


def hash_tacacs_password(password: str) -> str:
    """Hash a password using SHA-512 crypt for tac_plus-ng compatibility."""
    return tacacs_pwd_context.hash(password)


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
    # Hash the password if type is crypt and a password is provided
    if db_obj.password_type == "crypt" and db_obj.password:
        db_obj.password = hash_tacacs_password(db_obj.password)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_tacacs_user(
    *, session: Session, db_user: TacacsUser, user_in: TacacsUserUpdate
) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    # Hash the password if type is crypt and a new password is provided
    if user_data.get("password_type") == "crypt" and user_data.get("password"):
        user_data["password"] = hash_tacacs_password(user_data["password"])
    db_user.sqlmodel_update(user_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user
