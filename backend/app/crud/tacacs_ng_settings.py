from typing import Any

from sqlmodel import Session, select
from app.models import TacacsNgSetting, TacacsNgSettingCreate, TacacsNgSettingUpdate


def get_tacacs_ng(*, session: Session) -> TacacsNgSetting | None:
    statement = select(TacacsNgSetting)
    session_tacacs_ng = session.exec(statement).first()
    return session_tacacs_ng


def create_tacacs_ng(
    *, session: Session, tacacs_ng_create: TacacsNgSettingCreate
) -> TacacsNgSetting:
    db_obj = TacacsNgSetting.model_validate(tacacs_ng_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_tacacs_ng(
    *,
    session: Session,
    db_tacacs_ng: TacacsNgSetting,
    tacacs_ng_in: TacacsNgSettingUpdate
) -> Any:
    tacacs_ng_data = tacacs_ng_in.model_dump(exclude_unset=True)
    db_tacacs_ng.sqlmodel_update(tacacs_ng_data)
    session.add(db_tacacs_ng)
    session.commit()
    session.refresh(db_tacacs_ng)
    return db_tacacs_ng
