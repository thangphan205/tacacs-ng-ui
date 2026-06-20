from typing import Any
from uuid import UUID

from sqlmodel import Session, create_engine, select

from app.core.config import settings
from app.crud import users
from app.crud.tacacs_users import hash_tacacs_password
from app.models import (
    AlertRule,
    Host,
    HostCreate,
    Mavis,
    MavisCreate,
    Profile,
    ProfileCreate,
    ProfileScript,
    ProfileScriptCreate,
    ProfileScriptSet,
    ProfileScriptSetCreate,
    Ruleset,
    RulesetCreate,
    RulesetScript,
    RulesetScriptCreate,
    RulesetScriptSet,
    RulesetScriptSetCreate,
    TacacsGroup,
    TacacsGroupCreate,
    TacacsNgSetting,
    TacacsNgSettingCreate,
    TacacsService,
    TacacsServiceCreate,
    TacacsUser,
    TacacsUserCreate,
    User,
    UserCreate,
)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/thangphan205/tacacs-ng-ui/issues/28


def get_or_create_group(session: Session, name: str, description: str) -> TacacsGroup:
    group = session.exec(
        select(TacacsGroup).where(TacacsGroup.group_name == name)
    ).first()
    if not group:
        group_in = TacacsGroupCreate(group_name=name, description=description)
        group = TacacsGroup.model_validate(group_in)
        session.add(group)
        session.flush()
    return group


def get_or_create_user(
    session: Session,
    username: str,
    password_type: str,
    password: str,
    member: str,
    description: str,
) -> TacacsUser:
    user = session.exec(
        select(TacacsUser).where(TacacsUser.username == username)
    ).first()
    if not user:
        if password_type == "crypt" and password:
            hashed_pwd = hash_tacacs_password(password)
        else:
            hashed_pwd = password
        user_in = TacacsUserCreate(
            username=username,
            password_type=password_type,
            password=hashed_pwd,
            member=member,
            description=description,
        )
        user = TacacsUser.model_validate(user_in)
        session.add(user)
        session.flush()
    else:
        changed = False
        if user.member != member:
            user.member = member
            changed = True
        if user.description != description:
            user.description = description
            changed = True
        if user.password_type != password_type:
            user.password_type = password_type
            if password_type == "crypt" and password and not password.startswith("$6$"):
                user.password = hash_tacacs_password(password)
            else:
                user.password = password
            changed = True
        if changed:
            session.add(user)
            session.flush()
    return user


def get_or_create_service(
    session: Session, name: str, description: str
) -> TacacsService:
    service = session.exec(
        select(TacacsService).where(TacacsService.name == name)
    ).first()
    if not service:
        service_in = TacacsServiceCreate(name=name, description=description)
        service = TacacsService.model_validate(service_in)
        session.add(service)
        session.flush()
    return service


def get_or_create_profile(session: Session, name: str, action: str) -> Profile:
    profile = session.exec(select(Profile).where(Profile.name == name)).first()
    if not profile:
        profile_in = ProfileCreate(name=name, action=action)
        profile = Profile.model_validate(profile_in)
        session.add(profile)
        session.flush()
    return profile


def get_or_create_profile_script(
    session: Session,
    condition: str,
    key: str,
    value: str,
    action: str,
    description: str,
    profile_id: UUID,
) -> ProfileScript:
    script = session.exec(
        select(ProfileScript)
        .where(ProfileScript.profile_id == profile_id)
        .where(ProfileScript.key == key)
        .where(ProfileScript.value == value)
    ).first()
    if not script:
        script_in = ProfileScriptCreate(
            condition=condition,
            key=key,
            value=value,
            action=action,
            description=description,
            profile_id=profile_id,
        )
        script = ProfileScript.model_validate(script_in)
        session.add(script)
        session.flush()
    else:
        if script.condition != condition or script.action != action:
            script.condition = condition
            script.action = action
            session.add(script)
            session.flush()
    return script


def get_or_create_profile_script_set(
    session: Session,
    key: str,
    value: str,
    description: str,
    profilescript_id: UUID,
) -> ProfileScriptSet:
    script_set = session.exec(
        select(ProfileScriptSet)
        .where(ProfileScriptSet.profilescript_id == profilescript_id)
        .where(ProfileScriptSet.key == key)
    ).first()
    if not script_set:
        script_set_in = ProfileScriptSetCreate(
            key=key,
            value=value,
            description=description,
            profilescript_id=profilescript_id,
        )
        script_set = ProfileScriptSet.model_validate(script_set_in)
        session.add(script_set)
        session.flush()
    else:
        if script_set.value != value:
            script_set.value = value
            session.add(script_set)
            session.flush()
    return script_set


def get_or_create_ruleset(
    session: Session,
    name: str,
    enabled: str,
    action: str,
    description: str,
) -> Ruleset:
    ruleset = session.exec(select(Ruleset).where(Ruleset.name == name)).first()
    if not ruleset:
        ruleset_in = RulesetCreate(
            name=name,
            enabled=enabled,
            action=action,
            description=description,
        )
        ruleset = Ruleset.model_validate(ruleset_in)
        session.add(ruleset)
        session.flush()
    return ruleset


def get_or_create_ruleset_script(
    session: Session,
    condition: str,
    key: str,
    value: str,
    description: str,
    action: str,
    ruleset_id: UUID,
) -> RulesetScript:
    script = session.exec(
        select(RulesetScript)
        .where(RulesetScript.ruleset_id == ruleset_id)
        .where(RulesetScript.key == key)
        .where(RulesetScript.value == value)
    ).first()
    if not script:
        script_in = RulesetScriptCreate(
            condition=condition,
            key=key,
            value=value,
            description=description,
            action=action,
            ruleset_id=ruleset_id,
        )
        script = RulesetScript.model_validate(script_in)
        session.add(script)
        session.flush()
    else:
        if script.condition != condition or script.action != action:
            script.condition = condition
            script.action = action
            session.add(script)
            session.flush()
    return script


def get_or_create_ruleset_script_set(
    session: Session,
    key: str,
    value: str,
    description: str,
    rulesetscript_id: UUID,
) -> RulesetScriptSet:
    script_set = session.exec(
        select(RulesetScriptSet)
        .where(RulesetScriptSet.rulesetscript_id == rulesetscript_id)
        .where(RulesetScriptSet.key == key)
    ).first()
    if not script_set:
        script_set_in = RulesetScriptSetCreate(
            key=key,
            value=value,
            description=description,
            rulesetscript_id=rulesetscript_id,
        )
        script_set = RulesetScriptSet.model_validate(script_set_in)
        session.add(script_set)
        session.flush()
    else:
        if script_set.value != value:
            script_set.value = value
            session.add(script_set)
            session.flush()
    return script_set


def init_db(session: Session) -> None:
    # Tables should be created with Alembic migrations
    # But if you don't want to use migrations, create
    # the tables un-commenting the next lines
    # from sqlmodel import SQLModel

    # This works because the models are already imported and registered from app.models
    # SQLModel.metadata.create_all(engine)

    user = session.exec(
        select(User).where(User.email == settings.FIRST_SUPERUSER)
    ).first()
    if not user:
        user_in = UserCreate(
            email=settings.FIRST_SUPERUSER,
            password=settings.FIRST_SUPERUSER_PASSWORD,
            is_superuser=True,
        )
        user = users.create_user(session=session, user_create=user_in)

    tacacs_settings = session.exec(select(TacacsNgSetting)).first()
    if not tacacs_settings:
        tacacs_in = TacacsNgSettingCreate(
            ipv4_enabled=settings.IPV4_ENABLED,
            ipv4_address=settings.IPV4_ADDRESS,
            ipv4_port=settings.IPV4_PORT,
            ipv6_enabled=settings.IPV6_ENABLED,
            ipv6_address=settings.IPV6_ADDRESS,
            ipv6_port=settings.IPV6_PORT,
            instances_min=settings.INSTANCES_MIN,
            instances_max=settings.INSTANCES_MAX,
            background=settings.BACKGROUND,
            access_logfile_destination=settings.ACCESS_LOG_DESTINATION,
            authentication_logfile_destination=settings.AUTHENTICATION_LOG_DESTINATION,
            authorization_logfile_destination=settings.AUTHORIZATION_LOG_DESTINATION,
            accounting_logfile_destination=settings.ACCOUNTING_LOG_DESTINATION,
            login_backend=settings.LOGIN_BACKEND,
            user_backend=settings.USER_BACKEND,
            pap_backend=settings.PAP_BACKEND,
            timezone=settings.TACACS_TIMEZONE,
        )
        tacacs_settings = TacacsNgSetting.model_validate(tacacs_in)
        session.add(tacacs_settings)

    mavis = session.exec(select(Mavis)).all()
    if not mavis:
        for mavis_setting in settings.DEFAULT_MAVIS_SETTINGS:
            mavis_in = MavisCreate(
                mavis_key=mavis_setting["key"],
                mavis_value=mavis_setting["value"],
            )
            mavis_settings = Mavis.model_validate(mavis_in)
            session.add(mavis_settings)

    host = session.exec(select(Host)).first()
    if not host:
        host_in = HostCreate(
            name="DEMO_HOSTS",
            ipv4_address="0.0.0.0/0",
            secret_key="change_this",
            description="delete this after test",
        )
        host_settings = Host.model_validate(host_in)
        session.add(host_settings)

    # 1. Services to seed (needs to be first because scripts reference service names)
    services_to_seed = [
        ("shell", "Shell service — Cisco, Arista, Huawei"),
        ("junos-exec", "Juniper Networks exec service"),
        ("h3c_shell", "Huawei H3C shell service"),
        ("PaloAlto", "Palo Alto Networks service"),
        ("fortigate", "Fortinet FortiGate service"),
    ]
    for svc_name, svc_desc in services_to_seed:
        get_or_create_service(session, svc_name, svc_desc)

    # 2. Groups to seed
    groups_to_seed = [
        (
            "tacacs_super_user",
            "Super user group — full admin access, privilege level 15",
        ),
        ("tacacs_read_only", "Read-only group — view-only access, privilege level 1"),
    ]
    for grp_name, grp_desc in groups_to_seed:
        get_or_create_group(session, grp_name, grp_desc)

    # 3. Users to seed
    users_to_seed = [
        (
            "user_admin",
            "crypt",
            "change_this",
            "tacacs_super_user",
            "Admin user — full access, privilege level 15",
        ),
        (
            "user_read_only",
            "crypt",
            "change_this",
            "tacacs_read_only",
            "Read-only user — view-only access, privilege level 1",
        ),
    ]
    for username, pwd_type, pwd, member, desc in users_to_seed:
        get_or_create_user(session, username, pwd_type, pwd, member, desc)

    # 4. Profiles to seed
    profiles_to_seed = [
        ("tacacs_super_user_profile", "deny"),
        ("tacacs_read_only_profile", "deny"),
    ]
    profile_objs = {}
    for prof_name, prof_action in profiles_to_seed:
        profile_objs[prof_name] = get_or_create_profile(session, prof_name, prof_action)

    # Helper to seed profile script and its set value
    def seed_profile_rule(
        prof_name: str,
        condition: str,
        key: str,
        value: str,
        action: str,
        description: str,
        set_key: str,
        set_val: str,
        set_desc: str,
    ) -> None:
        prof = profile_objs.get(prof_name)
        if not prof:
            return
        ps = get_or_create_profile_script(
            session=session,
            condition=condition,
            key=key,
            value=value,
            action=action,
            description=description,
            profile_id=prof.id,
        )
        get_or_create_profile_script_set(
            session=session,
            key=set_key,
            value=set_val,
            description=set_desc,
            profilescript_id=ps.id,
        )

    # tacacs_super_user_profile — privilege 15 across Cisco, Arista, Huawei, Juniper
    seed_profile_rule(
        "tacacs_super_user_profile",
        "if",
        "service",
        "shell",
        "permit",
        "Cisco/Arista — privilege level 15",
        "priv-lvl",
        "15",
        "Privilege level 15",
    )
    seed_profile_rule(
        "tacacs_super_user_profile",
        "if",
        "service",
        "junos-exec",
        "permit",
        "Juniper — superuser local account",
        "local-user-name",
        "tacacs_super_user",
        "Juniper local user",
    )
    seed_profile_rule(
        "tacacs_super_user_profile",
        "if",
        "service",
        "h3c_shell",
        "permit",
        "Huawei H3C — privilege level 15",
        "priv-lvl",
        "15",
        "Privilege level 15",
    )
    seed_profile_rule(
        "tacacs_super_user_profile",
        "if",
        "service",
        "PaloAlto",
        "permit",
        "Palo Alto — superuser admin role",
        "PaloAlto-Admin-Role",
        "superuser",
        "Palo Alto superuser",
    )
    seed_profile_rule(
        "tacacs_super_user_profile",
        "if",
        "service",
        "fortigate",
        "permit",
        "Fortinet — super_admin profile",
        "admin_prof",
        "super_admin",
        "Fortinet super_admin",
    )

    # tacacs_read_only_profile — privilege 1 across Cisco, Arista, Huawei, Juniper
    seed_profile_rule(
        "tacacs_read_only_profile",
        "if",
        "service",
        "shell",
        "permit",
        "Cisco/Arista — privilege level 1 (read-only)",
        "priv-lvl",
        "1",
        "Privilege level 1",
    )
    seed_profile_rule(
        "tacacs_read_only_profile",
        "if",
        "service",
        "junos-exec",
        "permit",
        "Juniper — read-only local account",
        "local-user-name",
        "tacacs_read_only",
        "Juniper local user",
    )
    seed_profile_rule(
        "tacacs_read_only_profile",
        "if",
        "service",
        "h3c_shell",
        "permit",
        "Huawei H3C — privilege level 1 (read-only)",
        "priv-lvl",
        "1",
        "Privilege level 1",
    )
    seed_profile_rule(
        "tacacs_read_only_profile",
        "if",
        "service",
        "PaloAlto",
        "permit",
        "Palo Alto — devicereader role",
        "PaloAlto-Admin-Role",
        "devicereader",
        "Palo Alto read-only",
    )
    seed_profile_rule(
        "tacacs_read_only_profile",
        "if",
        "service",
        "fortigate",
        "permit",
        "Fortinet — read-only admin profile",
        "admin_prof",
        "read_only",
        "Fortinet read_only",
    )

    # 5. Ruleset
    ruleset = get_or_create_ruleset(
        session=session,
        name="default_ruleset",
        enabled="yes",
        action="deny",
        description="demo Ruleset",
    )

    # Helper to map a group to a profile in the ruleset
    def seed_ruleset_mapping(
        condition: str,
        group_name: str,
        profile_name: str,
        description: str,
    ) -> None:
        rs_script = get_or_create_ruleset_script(
            session=session,
            condition=condition,
            key="group",
            value=group_name,
            description=description,
            action="permit",
            ruleset_id=ruleset.id,
        )
        get_or_create_ruleset_script_set(
            session=session,
            key="profile",
            value=profile_name,
            description=f"Map group {group_name} to profile {profile_name}",
            rulesetscript_id=rs_script.id,
        )

    # Seed ruleset mappings
    seed_ruleset_mapping(
        "if",
        "tacacs_super_user",
        "tacacs_super_user_profile",
        "Super user — full admin, privilege level 15",
    )
    seed_ruleset_mapping(
        "if",
        "tacacs_read_only",
        "tacacs_read_only_profile",
        "Read-only — view-only access, privilege level 1",
    )

    _seed_system_alert_rules(session)
    session.commit()


_SYSTEM_ALERT_RULES: list[dict[str, Any]] = [
    {
        "name": "[System] High Auth Failure Rate",
        "description": "Fires when total authentication failures exceed 10 in a 10-minute window.",
        "log_type": "auth",
        "condition_field": "fail_count",
        "condition_operator": "gt",
        "threshold": 10.0,
        "time_window_minutes": 10,
        "severity": "high",
        "cooldown_minutes": 30,
    },
    {
        "name": "[System] New Username Detected",
        "description": "Fires when a username appears that was not seen in the prior 30 days.",
        "log_type": "auth",
        "condition_field": "username",
        "condition_operator": "new_value",
        "threshold": None,
        "time_window_minutes": 60,
        "severity": "medium",
        "cooldown_minutes": 240,
    },
    {
        "name": "[System] New Source IP Detected",
        "description": "Fires when a source IP appears that was not seen in the prior 30 days.",
        "log_type": "auth",
        "condition_field": "client_ip",
        "condition_operator": "new_value",
        "threshold": None,
        "time_window_minutes": 60,
        "severity": "medium",
        "cooldown_minutes": 240,
    },
    {
        "name": "[System] High Authorization Deny Rate",
        "description": "Fires when total authorization denials exceed 20 in a 10-minute window.",
        "log_type": "authz",
        "condition_field": "deny_count",
        "condition_operator": "gt",
        "threshold": 20.0,
        "time_window_minutes": 10,
        "severity": "high",
        "cooldown_minutes": 30,
    },
    {
        "name": "[System] TACACS Config Changed",
        "description": "Fires when any TACACS config is created, updated, or deleted.",
        "log_type": "config",
        "condition_field": "config_action",
        "condition_operator": "any_change",
        "threshold": 1.0,
        "time_window_minutes": 5,
        "severity": "high",
        "cooldown_minutes": 5,
    },
    {
        "name": "[System] TACACS Config Activated",
        "description": "Fires when a TACACS config is activated (pushed to live).",
        "log_type": "config",
        "condition_field": "config_action",
        "condition_operator": "activated",
        "threshold": 1.0,
        "time_window_minutes": 5,
        "severity": "critical",
        "cooldown_minutes": 5,
    },
]


def _seed_system_alert_rules(session: Session) -> None:
    existing_names = set(session.exec(select(AlertRule.name)).all())
    for rule_def in _SYSTEM_ALERT_RULES:
        if rule_def["name"] in existing_names:
            continue
        rule = AlertRule(
            **rule_def,
            enabled=True,
            is_system=True,
        )
        session.add(rule)
