from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from sqlmodel import Session, SQLModel, create_engine

from app.crud.tacacs_users import (
    to_public_with_live_auth,
    update_last_authenticated,
)
from app.models import TacacsUser
from scripts._log_stats_base import build_log_file_path, parse_authentication_logs

DAY = date(2026, 11, 19)


def _write_auth_log(base_dir: Path, lines: list[str]) -> str:
    log_dir = str(base_dir) + "/"
    path = Path(build_log_file_path(DAY, "authentication", log_dir))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(lines), encoding="utf-8")
    return log_dir


def test_parse_authentication_logs_tracks_latest_successful_login(
    tmp_path: Path,
) -> None:
    lines = [
        # alice succeeds twice -> keep the later timestamp (10:15 +0700 == 03:15 UTC)
        "2026-11-19 08:00:00 +0700 10.0.0.1\talice\ttty0\t192.0.2.1\tshell login succeeded\n",
        "2026-11-19 10:15:30 +0700 10.0.0.1\talice\ttty0\t192.0.2.1\tpap login succeeded\n",
        # alice fails later -> must NOT overwrite last successful login
        "2026-11-19 11:00:00 +0700 10.0.0.1\talice\ttty0\t192.0.2.1\tpap login failed [Invalid credentials.]\n",
        # bob only fails -> must NOT appear in last_auth
        "2026-11-19 09:00:00 +0700 10.0.0.1\tbob\ttty0\t192.0.2.2\tshell login failed\n",
        # carol only changes password -> not a login, must NOT appear
        "2026-11-19 09:30:00 +0700 10.0.0.1\tcarol\ttty0\t192.0.2.3\tpassword change succeeded\n",
    ]
    log_dir = _write_auth_log(tmp_path, lines)

    last_auth: dict[str, datetime] = {}
    ok, fail = parse_authentication_logs(DAY, log_dir, last_auth=last_auth)

    assert sum(ok.values()) == 2
    assert sum(fail.values()) == 2
    assert set(last_auth.keys()) == {"alice"}
    assert last_auth["alice"] == datetime(2026, 11, 19, 3, 15, 30, tzinfo=timezone.utc)


def test_to_public_with_live_auth_merges_stored_and_live() -> None:
    t1 = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 19, 6, 0, 0, tzinfo=timezone.utc)
    now = datetime(2026, 11, 19, 7, 0, 0, tzinfo=timezone.utc)

    u_never = TacacsUser(
        username="never",
        password_type="crypt",
        member="g1",
        created_at=now,
        updated_at=now,
    )
    assert to_public_with_live_auth(u_never, {}).last_authenticated_at is None
    assert (
        to_public_with_live_auth(u_never, {"never": t2}).last_authenticated_at == t2
    )

    u_stored = TacacsUser(
        username="alice",
        password_type="crypt",
        member="g1",
        last_authenticated_at=t2,
        created_at=now,
        updated_at=now,
    )
    # Older live value must not downgrade stored value
    assert (
        to_public_with_live_auth(u_stored, {"alice": t1}).last_authenticated_at == t2
    )
    # Newer live value overrides stored value
    t3 = t2 + timedelta(minutes=5)
    assert (
        to_public_with_live_auth(u_stored, {"alice": t3}).last_authenticated_at == t3
    )


def test_update_last_authenticated_advances_and_preserves_updated_at() -> None:
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine, tables=[TacacsUser.__table__])

    created = datetime(2026, 11, 1, 0, 0, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 11, 19, 4, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 11, 19, 5, 0, 0, tzinfo=timezone.utc)

    with Session(engine) as session:
        user = TacacsUser(
            username="alice",
            password_type="crypt",
            member="g1",
            created_at=created,
            updated_at=created,
        )
        session.add(user)
        session.commit()
        user_id = user.id

    with Session(engine) as session:
        changed = update_last_authenticated(
            session=session, last_auth={"alice": t2, "unknown_user": t2}
        )
        session.commit()
        assert changed == 1

    with Session(engine) as session:
        reloaded = session.get(TacacsUser, user_id)
        assert reloaded is not None
        assert reloaded.last_authenticated_at is not None
        assert reloaded.last_authenticated_at.replace(tzinfo=timezone.utc) == t2
        assert reloaded.updated_at.replace(tzinfo=timezone.utc) == created

    # Older timestamp must not overwrite a newer stored timestamp
    with Session(engine) as session:
        changed = update_last_authenticated(session=session, last_auth={"alice": t1})
        session.commit()
        assert changed == 0

    with Session(engine) as session:
        reloaded = session.get(TacacsUser, user_id)
        assert reloaded is not None
        assert reloaded.last_authenticated_at is not None
        assert reloaded.last_authenticated_at.replace(tzinfo=timezone.utc) == t2
