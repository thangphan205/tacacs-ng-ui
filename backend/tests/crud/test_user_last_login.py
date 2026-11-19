from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings
from app.crud.users import record_last_login
from app.models import User, UserPublic, WebAuthnCredential


def _make_engine():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(
        engine, tables=[User.__table__, WebAuthnCredential.__table__]
    )
    return engine


def test_record_last_login_updates_timestamp_and_preserves_updated_at() -> None:
    engine = _make_engine()
    created = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    login_ts = datetime(2026, 11, 19, 14, 20, 0, tzinfo=timezone(timedelta(hours=7)))
    expected_utc = datetime(2026, 11, 19, 7, 20, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = User(
            email="alice@example.com",
            hashed_password="x",
            created_at=created,
            updated_at=created,
        )
        session.add(user)
        session.commit()
        user_id = user.id

    with Session(engine) as session:
        record_last_login(session=session, user_id=user_id, when=login_ts)

    with Session(engine) as session:
        reloaded = session.get(User, user_id)
        assert reloaded is not None
        assert reloaded.last_login_at is not None
        assert reloaded.last_login_at.replace(tzinfo=timezone.utc) == expected_utc
        assert reloaded.updated_at.replace(tzinfo=timezone.utc) == created

        public = UserPublic.model_validate(reloaded)
        assert public.last_login_at is not None


def test_record_last_login_is_noop_on_standby(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _make_engine()
    created = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = User(
            email="standby@example.com",
            hashed_password="x",
            created_at=created,
            updated_at=created,
        )
        session.add(user)
        session.commit()
        user_id = user.id

    monkeypatch.setattr(settings, "NODE_ROLE", "standby")
    with Session(engine) as session:
        record_last_login(session=session, user_id=user_id)

    with Session(engine) as session:
        reloaded = session.get(User, user_id)
        assert reloaded is not None
        assert reloaded.last_login_at is None
