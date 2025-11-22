from typing import Any

from sqlmodel import Session, select
from app.models import TacacsUser, TacacsUserCreate, TacacsUserUpdate


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
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_tacacs_user(
    *, session: Session, db_user: TacacsUser, user_in: TacacsUserUpdate
) -> Any:
    user_data = user_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_user.sqlmodel_update(user_data, update=extra_data)
    session.add(db_user)
    session.commit()
    session.refresh(db_user)
    return db_user
