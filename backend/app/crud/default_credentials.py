"""Find TACACS+ users and hosts that still use the public demo secret.

`init_db` seeds demo data with the password and key `change_this`, which is
printed in the README. Anything that still carries it and is included in the
generated config is a login with a publicly known password on every device that
uses this server, so the UI warns about it until it is changed or removed.
"""

from functools import lru_cache

from sqlmodel import Session, and_, col, or_, select

from app.crud.tacacs_users import is_tacacs_password_hash, tacacs_pwd_context
from app.models import DefaultCredentialFinding, Host, TacacsUser

DEMO_PASSWORD = "change_this"
DEMO_USERNAMES = ("user_admin", "user_read_only")
DEMO_HOST_NAME = "DEMO_HOSTS"


@lru_cache(maxsize=256)
def _hash_is_demo_password(password_hash: str) -> bool:
    # sha512_crypt is deliberately slow; the answer for a given hash string never
    # changes, so cache it rather than paying that cost on every page load.
    return bool(tacacs_pwd_context.verify(DEMO_PASSWORD, password_hash))


def find_default_credentials(*, session: Session) -> list[DefaultCredentialFinding]:
    """Users and hosts in the generated config whose secret is `DEMO_PASSWORD`.

    Clear-text passwords and host keys are compared for every row. Crypt hashes
    are only verified for the seeded usernames: checking every user would cost a
    sha512_crypt round per account.
    """
    findings: list[DefaultCredentialFinding] = []

    users = session.exec(
        select(TacacsUser)
        .where(col(TacacsUser.generate_config).is_(True))
        .where(
            or_(
                and_(
                    col(TacacsUser.password_type) == "clear",
                    col(TacacsUser.password) == DEMO_PASSWORD,
                ),
                and_(
                    col(TacacsUser.password_type) == "crypt",
                    col(TacacsUser.username).in_(DEMO_USERNAMES),
                ),
            )
        )
        .order_by(col(TacacsUser.username))
    ).all()
    for user in users:
        if user.password_type == "crypt" and not (
            user.password
            and is_tacacs_password_hash(user.password)
            and _hash_is_demo_password(user.password)
        ):
            continue
        findings.append(
            DefaultCredentialFinding(kind="tacacs_user", id=user.id, name=user.username)
        )

    hosts = session.exec(
        select(Host)
        .where(col(Host.generate_config).is_(True))
        .where(col(Host.secret_key) == DEMO_PASSWORD)
        .order_by(col(Host.name))
    ).all()
    findings.extend(
        DefaultCredentialFinding(kind="host", id=host.id, name=host.name)
        for host in hosts
    )
    return findings
