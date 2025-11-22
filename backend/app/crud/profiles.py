from typing import Any

from sqlmodel import Session, select
from app.models import (
    Profile,
    ProfileCreate,
    ProfileUpdate,
    ProfileScript,
    ProfileScriptSet,
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
    extra_data = {}
    db_profile.sqlmodel_update(profile_data, update=extra_data)
    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    return db_profile


def profile_generator(session: Session) -> str:
    profiles_db = session.exec(select(Profile)).all()
    profile_template = ""
    for profile_db in profiles_db:

        statement = select(ProfileScript).where(
            ProfileScript.profile_id == profile_db.id
        )
        script_in_profile = session.exec(statement).all()
        if script_in_profile == []:
            continue
        profilescript_template = ""
        for profilescript in script_in_profile:
            scriptset_in_profilescript = session.exec(
                select(ProfileScriptSet).where(
                    ProfileScriptSet.profilescript_id == profilescript.id
                )
            ).all()
            if scriptset_in_profilescript == []:
                continue
            profilescriptset_template = ""
            for profilescriptset in scriptset_in_profilescript:
                profilescriptset_info = profilescriptset.model_dump()
                profilescriptset_template += """set {key}={value}""".format(
                    key=profilescriptset_info["key"],
                    value=profilescriptset_info["value"],
                )

            profilescript_info = profilescript.model_dump()
            profilescript_template += """{condition} ({key}=={value}){{
            {profilescriptset_template}
            {action}
            }}""".format(
                condition=profilescript_info["condition"],
                key=profilescript_info["key"],
                value=profilescript_info["value"],
                profilescriptset_template=profilescriptset_template,
                action=profilescript_info["action"],
            )
        profile_template += """
    profile {profile_name} {{
        script {{
        {profilescript_template}
        {action}
        }}
    }}""".format(
            profile_name=profile_db.name,
            profilescript_template=profilescript_template,
            action=profile_db.action,
        )

    return profile_template
