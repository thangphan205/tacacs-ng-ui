"""Two first sign-ins racing to link one local account must not both win."""

import uuid

from sqlmodel import Session

from app.core.db import engine
from app.crud import users
from app.models import User
from tests.utils.user import create_random_user


def test_second_entry_cannot_take_an_account_the_first_just_linked(
    db: Session,
) -> None:
    """Entries A and B share a mail address. Both requests read the account
    unlinked; the unique index never fires because their ids differ."""
    account = create_random_user(db)
    a_id, b_id = f"a-{uuid.uuid4().hex[:8]}", f"b-{uuid.uuid4().hex[:8]}"

    with Session(engine) as other:  # request B's view, read before A commits
        stale = other.get(User, account.id)
        assert stale is not None and stale.ldap_id is None

        # Request A links first.
        mine = db.get(User, account.id)
        assert mine is not None
        assert users._link_ldap(session=db, user=mine, ldap_id=a_id, full_name=None)

        # Request B still holds the unlinked row: its link must lose.
        assert (
            users._link_ldap(session=other, user=stale, ldap_id=b_id, full_name=None)
            is None
        )

    db.expire_all()
    linked = db.get(User, account.id)
    assert linked is not None and linked.ldap_id == a_id


def test_same_entry_racing_itself_still_gets_the_account(db: Session) -> None:
    account = create_random_user(db)
    entry = f"same-{uuid.uuid4().hex[:8]}"

    with Session(engine) as other:
        stale = other.get(User, account.id)
        assert stale is not None
        mine = db.get(User, account.id)
        assert mine is not None
        assert users._link_ldap(session=db, user=mine, ldap_id=entry, full_name=None)
        # A double submit of the same entry: the loser is handed the winner.
        won = users._link_ldap(session=other, user=stale, ldap_id=entry, full_name=None)
        assert won is not None and won.id == account.id
