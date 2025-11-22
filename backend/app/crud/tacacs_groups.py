from typing import Any

from sqlmodel import Session, select
from app.models import TacacsGroup, TacacsGroupCreate, TacacsGroupUpdate


def get_tacacs_group_by_group_name(
    *, session: Session, group_name: str
) -> TacacsGroup | None:
    statement = select(TacacsGroup).where(TacacsGroup.group_name == group_name)
    session_user = session.exec(statement).first()
    return session_user


def create_tacacs_group(
    *, session: Session, user_create: TacacsGroupCreate
) -> TacacsGroup:
    db_obj = TacacsGroup.model_validate(user_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_tacacs_group(
    *, session: Session, db_tacacs_group: TacacsGroup, group_in: TacacsGroupUpdate
) -> Any:
    user_data = group_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_tacacs_group.sqlmodel_update(user_data, update=extra_data)
    session.add(db_tacacs_group)
    session.commit()
    session.refresh(db_tacacs_group)
    return db_tacacs_group
