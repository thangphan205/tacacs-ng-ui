from sqlmodel import Session, create_engine, select

from app.crud import users
from app.core.config import settings
from app.models import (
    User,
    UserCreate,
    TacacsNgSetting,
    TacacsNgSettingCreate,
    Mavis,
    MavisCreate,
    Host,
    HostCreate,
    TacacsGroup,
    TacacsGroupCreate,
    TacacsUser,
    TacacsUserCreate,
    TacacsService,
    TacacsServiceCreate,
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
)

engine = create_engine(str(settings.SQLALCHEMY_DATABASE_URI))


# make sure all SQLModel models are imported (app.models) before initializing DB
# otherwise, SQLModel might fail to initialize relationships properly
# for more details: https://github.com/fastapi/full-stack-fastapi-template/issues/28


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
            accounting_logfile_destination=settings.ACCOUNTING_LOG_DESTINATION,
            authentication_logfile_destination=settings.AUTHENTICATION_LOG_DESTINATION,
            login_backend=settings.LOGIN_BACKEND,
            user_backend=settings.USER_BACKEND,
            pap_backend=settings.PAP_BACKEND,
        )
        tacacs_settings = TacacsNgSetting.model_validate(tacacs_in)
        session.add(tacacs_settings)
        session.commit()
        session.refresh(tacacs_settings)

    mavis = session.exec(select(Mavis)).first()
    if not mavis:
        mavis_in = MavisCreate(
            ldap_server_type=settings.LDAP_SERVER_TYPE,
            ldap_host=settings.LDAP_HOSTS,
            ldap_base=settings.LDAP_BASE,
            ldap_user=settings.LDAP_USER,
            ldap_passwd=settings.LDAP_PASSWD,
            require_tacacs_group_prefix=settings.REQUIRE_TACACS_GROUP_PREFIX,
            tacacs_group_prefix=settings.TACACS_GROUP_PREFIX,
            ldap_filter=settings.LDAP_FILTER,
        )
        mavis_settings = Mavis.model_validate(mavis_in)
        session.add(mavis_settings)
        session.commit()
        session.refresh(mavis_settings)

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
        session.commit()
        session.refresh(host_settings)

    tacacs_group = session.exec(select(TacacsGroup)).first()
    if not tacacs_group:
        tacacs_group_super_user_in = TacacsGroupCreate(
            group_name="tacacs_super_user",
            description="demo super user group",
        )
        tacacs_group_super_user_settings = TacacsGroup.model_validate(
            tacacs_group_super_user_in
        )
        session.add(tacacs_group_super_user_settings)
        session.commit()
        session.refresh(tacacs_group_super_user_settings)
        tacacs_group_read_only_in = TacacsGroupCreate(
            group_name="tacacs_read_only",
            description="demo read only group",
        )
        tacacs_group_read_only_settings = TacacsGroup.model_validate(
            tacacs_group_read_only_in
        )
        session.add(tacacs_group_read_only_settings)
        session.commit()
        session.refresh(tacacs_group_read_only_settings)

        tacacs_group_level1_in = TacacsGroupCreate(
            group_name="tacacs_group_level1",
            description="cisco privilege level 1",
        )
        tacacs_group_level1_settings = TacacsGroup.model_validate(
            tacacs_group_level1_in
        )
        session.add(tacacs_group_level1_settings)
        session.commit()
        session.refresh(tacacs_group_level1_settings)

        tacacs_group_level15_in = TacacsGroupCreate(
            group_name="tacacs_group_level15",
            description="cisco privilege level 15",
        )
        tacacs_group_level15_settings = TacacsGroup.model_validate(
            tacacs_group_level15_in
        )
        session.add(tacacs_group_level15_settings)
        session.commit()
        session.refresh(tacacs_group_level15_settings)

    tacacs_user = session.exec(select(TacacsUser)).first()
    if not tacacs_user:
        tacacs_user_in = TacacsUserCreate(
            username="user_admin",
            password_type="clear",
            password="change_this",
            member="tacacs_super_user",
            description="demo admin user",
        )
        tacacs_user_settings = TacacsUser.model_validate(tacacs_user_in)
        session.add(tacacs_user_settings)
        session.commit()
        session.refresh(tacacs_user_settings)
        tacacs_user_in = TacacsUserCreate(
            username="user_read_only",
            password_type="clear",
            password="change_this",
            member="tacacs_read_only",
            description="demo read only user",
        )
        tacacs_user_settings = TacacsUser.model_validate(tacacs_user_in)
        session.add(tacacs_user_settings)
        session.commit()
        session.refresh(tacacs_user_settings)

        tacacs_user1_in = TacacsUserCreate(
            username="user_level1",
            password_type="clear",
            password="change_this",
            member="tacacs_group_level1",
            description="privilege level 1 user",
        )
        tacacs_user1_settings = TacacsUser.model_validate(tacacs_user1_in)
        session.add(tacacs_user1_settings)
        session.commit()
        session.refresh(tacacs_user1_settings)

        tacacs_user15_in = TacacsUserCreate(
            username="user_level15",
            password_type="clear",
            password="change_this",
            member="tacacs_group_level15",
            description="privilege level 15 user",
        )
        tacacs_user15_settings = TacacsUser.model_validate(tacacs_user15_in)
        session.add(tacacs_user15_settings)
        session.commit()
        session.refresh(tacacs_user15_settings)

    # Begin Tacacs Service
    tacacs_service = session.exec(select(TacacsService)).first()
    if not tacacs_service:
        tacacs_service_in = TacacsServiceCreate(
            name="junos-exec",
            description="Juniper service",
        )
        tacacs_service_settings = TacacsService.model_validate(tacacs_service_in)
        session.add(tacacs_service_settings)
        session.commit()
        session.refresh(tacacs_service_settings)

        tacacs_service_shell_in = TacacsServiceCreate(
            name="shell",
            description="For Cisco devices",
        )
        tacacs_service_shell_settings = TacacsService.model_validate(
            tacacs_service_shell_in
        )
        session.add(tacacs_service_shell_settings)
        session.commit()
        session.refresh(tacacs_service_shell_settings)
    # Begin Profile
    profile = session.exec(select(Profile)).first()
    if not profile:
        profile_super_user_in = ProfileCreate(
            name="tacacs_super_user_profile", action="deny"
        )
        profile_super_user_settings = Profile.model_validate(profile_super_user_in)
        session.add(profile_super_user_settings)
        session.commit()
        session.refresh(profile_super_user_settings)

        profile_read_only_in = ProfileCreate(
            name="tacacs_read_only_profile", action="deny"
        )
        profile_read_only_settings = Profile.model_validate(profile_read_only_in)
        session.add(profile_read_only_settings)
        session.commit()
        session.refresh(profile_read_only_settings)

        profile_cisco15_in = ProfileCreate(name="tacacs_cisco15_profile", action="deny")
        profile_cisco15_settings = Profile.model_validate(profile_cisco15_in)
        session.add(profile_cisco15_settings)
        session.commit()
        session.refresh(profile_cisco15_settings)

    # Begin Profile script
    profile_script = session.exec(select(ProfileScript)).first()
    if not profile_script:
        profile_script_super_user_in = ProfileScriptCreate(
            condition="if",
            key="service",
            value="junos-exec",
            action="permit",
            description="Allow junos-exec service for super user profile",
            profile_id=profile_super_user_settings.id,
        )
        profile_script__super_user_settings = ProfileScript.model_validate(
            profile_script_super_user_in
        )
        session.add(profile_script__super_user_settings)
        session.commit()
        session.refresh(profile_script__super_user_settings)

        profile_script_read_only_in = ProfileScriptCreate(
            condition="if",
            key="service",
            value="junos-exec",
            action="permit",
            description="Allow junos-exec service for read only profile",
            profile_id=profile_read_only_settings.id,
        )
        profile_script_read_only_settings = ProfileScript.model_validate(
            profile_script_read_only_in
        )
        session.add(profile_script_read_only_settings)
        session.commit()
        session.refresh(profile_script_read_only_settings)

        profile_script_cisco15_in = ProfileScriptCreate(
            condition="if",
            key="service",
            value="shell",
            action="permit",
            description="Allow cisco privilege level 15",
            profile_id=profile_cisco15_settings.id,
        )
        profile_script_cisco15_settings = ProfileScript.model_validate(
            profile_script_cisco15_in
        )
        session.add(profile_script_cisco15_settings)
        session.commit()
        session.refresh(profile_script_cisco15_settings)
    # Begin profile script set
    profile_script_set = session.exec(select(ProfileScriptSet)).first()
    if not profile_script_set:
        profile_script_set_super_user_in = ProfileScriptSetCreate(
            key="local-user-name",
            value="tacacs_super_user",
            description="set local user name for super user",
            profilescript_id=profile_script__super_user_settings.id,
        )

        profile_script_set_super_user_settings = ProfileScriptSet.model_validate(
            profile_script_set_super_user_in
        )
        session.add(profile_script_set_super_user_settings)
        session.commit()
        session.refresh(profile_script_set_super_user_settings)

        profile_script_set_read_only_in = ProfileScriptSetCreate(
            key="local-user-name",
            value="tacacs_read_only",
            description="set local user name for super user",
            profilescript_id=profile_script_read_only_settings.id,
        )

        profile_script_set_read_only_settings = ProfileScriptSet.model_validate(
            profile_script_set_read_only_in
        )
        session.add(profile_script_set_read_only_settings)
        session.commit()
        session.refresh(profile_script_set_read_only_settings)

        profile_script_set_cisco15_in = ProfileScriptSetCreate(
            key="priv-lvl",
            value="15",
            description="Cisco privilege level 15",
            profilescript_id=profile_script_cisco15_settings.id,
        )

        profile_script_set_cisco15_settings = ProfileScriptSet.model_validate(
            profile_script_set_cisco15_in
        )
        session.add(profile_script_set_cisco15_settings)
        session.commit()
        session.refresh(profile_script_set_cisco15_settings)
    # Begin Ruleset
    ruleset = session.exec(select(Ruleset)).first()
    if not ruleset:
        ruleset_in = RulesetCreate(
            name="default_ruleset",
            enabled="yes",
            action="deny",
            description="demo Ruleset",
        )
        ruleset_settings = Ruleset.model_validate(ruleset_in)
        session.add(ruleset_settings)
        session.commit()
        session.refresh(ruleset_settings)
    # Begin Ruleset Script Juniper
    rulesetscript = session.exec(select(RulesetScript)).first()
    if not rulesetscript:
        rulesetscript_super_user_in = RulesetScriptCreate(
            condition="if",
            key="group",
            value="tacacs_super_user",
            description="demo Ruleset",
            action="permit",
            ruleset_id=ruleset_settings.id,
        )
        rulesetscript_super_user_settings = RulesetScript.model_validate(
            rulesetscript_super_user_in
        )
        session.add(rulesetscript_super_user_settings)
        session.commit()
        session.refresh(rulesetscript_super_user_settings)

        rulesetscript_read_only_in = RulesetScriptCreate(
            condition="if",
            key="group",
            value="tacacs_read_only",
            description="demo Ruleset",
            action="permit",
            ruleset_id=ruleset_settings.id,
        )
        rulesetscript_read_only_settings = RulesetScript.model_validate(
            rulesetscript_read_only_in
        )
        session.add(rulesetscript_read_only_settings)
        session.commit()
        session.refresh(rulesetscript_read_only_settings)

        rulesetscript_cisco15_in = RulesetScriptCreate(
            condition="if",
            key="group",
            value="tacacs_group_level15",
            description="Cisco Level 15 Ruleset",
            action="permit",
            ruleset_id=ruleset_settings.id,
        )
        rulesetscript_cisco15_settings = RulesetScript.model_validate(
            rulesetscript_cisco15_in
        )
        session.add(rulesetscript_cisco15_settings)
        session.commit()
        session.refresh(rulesetscript_cisco15_settings)

    rulesetscriptset = session.exec(select(RulesetScriptSet)).first()
    if not rulesetscriptset:
        rulesetscriptset_super_user_in = RulesetScriptSetCreate(
            key="profile",
            value="tacacs_super_user_profile",
            description="demo Ruleset",
            action="permit",
            rulesetscript_id=rulesetscript_super_user_settings.id,
        )
        rulesetscriptset_super_user_settings = RulesetScriptSet.model_validate(
            rulesetscriptset_super_user_in
        )
        session.add(rulesetscriptset_super_user_settings)
        session.commit()
        session.refresh(rulesetscriptset_super_user_settings)

        rulesetscriptset_read_only_in = RulesetScriptSetCreate(
            key="profile",
            value="tacacs_read_only_profile",
            description="demo Ruleset",
            action="permit",
            rulesetscript_id=rulesetscript_read_only_settings.id,
        )
        rulesetscriptset_read_only_settings = RulesetScriptSet.model_validate(
            rulesetscriptset_read_only_in
        )
        session.add(rulesetscriptset_read_only_settings)
        session.commit()
        session.refresh(rulesetscriptset_read_only_settings)

        rulesetscriptset_cisco15_in = RulesetScriptSetCreate(
            key="profile",
            value="tacacs_cisco15_profile",
            description="demo Ruleset",
            action="permit",
            rulesetscript_id=rulesetscript_cisco15_settings.id,
        )
        rulesetscriptset_cisco15_settings = RulesetScriptSet.model_validate(
            rulesetscriptset_cisco15_in
        )
        session.add(rulesetscriptset_cisco15_settings)
        session.commit()
        session.refresh(rulesetscriptset_cisco15_settings)
