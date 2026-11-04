from typing import Any

from sqlmodel import Session, col, select

from app.crud.ordering import order_columns
from app.crud.script_render import script_header
from app.models import (
    ConfigurationOption,
    Profile,
    ProfileCreate,
    ProfileScript,
    ProfileScriptSet,
    ProfileUpdate,
)


def get_profile_by_name(*, session: Session, name: str) -> Profile | None:
    statement = select(Profile).where(Profile.name == name)
    session_profile = session.exec(statement).first()
    return session_profile


def create_profile(*, session: Session, profile_create: ProfileCreate) -> Profile:
    db_obj = Profile.model_validate(profile_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_profile(
    *, session: Session, db_profile: Profile, profile_in: ProfileUpdate
) -> Any:
    profile_data = profile_in.model_dump(exclude_unset=True)
    db_profile.sqlmodel_update(profile_data)
    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    return db_profile


def profile_generator(session: Session) -> str:
    statement_configuration_profile = select(ConfigurationOption).where(
        ConfigurationOption.name == "profile"
    )
    configuration_profile_options = session.exec(statement_configuration_profile).all()
    profile_template = ""
    if configuration_profile_options:
        profile_template += "\n    # Profile Configuration Options\n"
        for configuration_profile_option in configuration_profile_options:
            profile_template += f"""
    {configuration_profile_option.config_option}
"""
        profile_template += "\n    # End of Profile Configuration Options\n"

    profiles_db = session.exec(
        select(Profile).where(Profile.generate_config == True)
    ).all()
    for profile_db in profiles_db:
        # Order is policy: tac_plus-ng stops at the first matching permit/deny.
        statement = (
            select(ProfileScript)
            .where(ProfileScript.profile_id == profile_db.id)
            .order_by(*order_columns(ProfileScript))
        )
        script_in_profile = session.exec(statement).all()
        if script_in_profile == []:
            continue
        profilescript_template = ""
        for profilescript in script_in_profile:
            scriptset_in_profilescript = session.exec(
                select(ProfileScriptSet)
                .where(ProfileScriptSet.profilescript_id == profilescript.id)
                .order_by(col(ProfileScriptSet.created_at), col(ProfileScriptSet.id))
            ).all()
            # A script with no `set` lines is still a rule — `if (...) { deny }`
            # must not be dropped, or traffic falls through to the next script.
            profilescriptset_template = ""
            for profilescriptset in scriptset_in_profilescript:
                profilescriptset_info = profilescriptset.model_dump()
                profilescriptset_template += """              set {key}={value}
""".format(
                    key=profilescriptset_info["key"],
                    value=profilescriptset_info["value"],
                )

            profilescript_info = profilescript.model_dump()
            profilescript_template += """           {header}{{
{profilescriptset_template}
            {action}
            }}
""".format(
                header=script_header(
                    profilescript_info["condition"],
                    profilescript_info["key"],
                    profilescript_info["value"],
                ),
                profilescriptset_template=profilescriptset_template,
                action=profilescript_info["action"],
            )
        profile_template += f"""
    profile {profile_db.name} {{
        script {{
{profilescript_template}
        {profile_db.action}
        }}
    }}
"""

    return profile_template
