from sqlmodel import Session, select

from app.crud.tacacs_configs import generate_tacacs_ng_config
from app.models import (
    Host,
    TacacsGroup,
    TacacsNgSetting,
    TacacsUser,
)


def test_generate_config_filtering(db: Session) -> None:
    # Ensure settings exist
    settings = db.exec(select(TacacsNgSetting)).first()
    if not settings:
        setting = TacacsNgSetting(
            ipv4_enabled=True,
            ipv4_address="127.0.0.1",
            ipv4_port=49,
            instances_min=1,
            instances_max=5,
            background=True,
            access_logfile_destination="/var/log/tacacs_access.log",
            authentication_logfile_destination="/var/log/tacacs_auth.log",
            authorization_logfile_destination="/var/log/tacacs_authz.log",
            accounting_logfile_destination="/var/log/tacacs_acct.log",
        )
        db.add(setting)
        db.commit()

    # 1. Create Hosts
    host_active = Host(
        name="HOST_ACTIVE",
        ipv4_address="192.168.10.1",
        secret_key="secret1",
        generate_config=True,
    )
    host_inactive = Host(
        name="HOST_INACTIVE",
        ipv4_address="192.168.10.2",
        secret_key="secret2",
        generate_config=False,
    )
    db.add(host_active)
    db.add(host_inactive)

    # 2. Create Groups
    group_active = TacacsGroup(
        group_name="GROUP_ACTIVE",
        generate_config=True,
    )
    group_inactive = TacacsGroup(
        group_name="GROUP_INACTIVE",
        generate_config=False,
    )
    db.add(group_active)
    db.add(group_inactive)

    # 3. Create Users
    user_active = TacacsUser(
        username="USER_ACTIVE",
        password_type="clear",
        password="pwd1",
        member="GROUP_ACTIVE",
        generate_config=True,
    )
    user_inactive = TacacsUser(
        username="USER_INACTIVE",
        password_type="clear",
        password="pwd2",
        member="GROUP_ACTIVE",
        generate_config=False,
    )
    db.add(user_active)
    db.add(user_inactive)

    db.commit()

    # Generate config and verify filtering
    config = generate_tacacs_ng_config(session=db)

    # Clean up test database records
    db.delete(host_active)
    db.delete(host_inactive)
    db.delete(group_active)
    db.delete(group_inactive)
    db.delete(user_active)
    db.delete(user_inactive)
    db.commit()

    # Asserts
    assert "HOST_ACTIVE" in config
    assert "HOST_INACTIVE" not in config

    assert "group = GROUP_ACTIVE" in config
    assert "group = GROUP_INACTIVE" not in config

    assert "user USER_ACTIVE" in config
    assert "user USER_INACTIVE" not in config


def test_generate_config_pap_login_for_local_users(db: Session) -> None:
    """Local users must get `password pap = login`, MAVIS users must not.

    Without it, tac_plus-ng has no PAP credential for a locally defined user
    and falls through to `pap backend = mavis`, so PAP auth fails for anyone
    who does not also exist in LDAP. See issue #260.
    """
    user_clear = TacacsUser(
        username="USER_PAP_CLEAR",
        password_type="clear",
        password="pwd1",
        member="GROUP_PAP",
        generate_config=True,
    )
    user_crypt = TacacsUser(
        username="USER_PAP_CRYPT",
        password_type="crypt",
        password="$6$rounds=656000$abc$def",
        member="GROUP_PAP",
        generate_config=True,
    )
    user_mavis = TacacsUser(
        username="USER_PAP_MAVIS",
        password_type="mavis",
        member="GROUP_PAP",
        generate_config=True,
    )
    db.add(user_clear)
    db.add(user_crypt)
    db.add(user_mavis)
    db.commit()

    config: str
    try:
        config = generate_tacacs_ng_config(session=db)
    finally:
        db.delete(user_clear)
        db.delete(user_crypt)
        db.delete(user_mavis)
        db.commit()

    def user_block(username: str) -> str:
        start = config.index(f"user {username} {{")
        return config[start : config.index("}", start)]

    assert "password pap = login" in user_block("USER_PAP_CLEAR")
    assert "password pap = login" in user_block("USER_PAP_CRYPT")
    assert "password pap = login" not in user_block("USER_PAP_MAVIS")
