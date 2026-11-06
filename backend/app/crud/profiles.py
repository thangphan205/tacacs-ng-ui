import textwrap
import uuid
from typing import Any

from sqlmodel import Session, col, func, select

from app.core.raw_script import profile_names_in
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


def count_scripts(*, session: Session, profile_id: uuid.UUID) -> int:
    return session.exec(
        select(func.count())
        .select_from(ProfileScript)
        .where(ProfileScript.profile_id == profile_id)
    ).one()


def update_profile(
    *, session: Session, db_profile: Profile, profile_in: ProfileUpdate
) -> Any:
    """Raises `ValueError` when switching a profile with scripts to raw mode."""
    profile_data = profile_in.model_dump(exclude_unset=True)
    if profile_data.get("raw_script"):
        n = count_scripts(session=session, profile_id=db_profile.id)
        if n:
            raise ValueError(
                f"Profile '{db_profile.name}' has {n} structured script"
                f"{'s' if n != 1 else ''}; delete them before switching to a raw script."
            )
    db_profile.sqlmodel_update(profile_data)
    session.add(db_profile)
    session.commit()
    session.refresh(db_profile)
    return db_profile


def render_raw_profile(name: str, raw_script: str) -> str:
    """A raw profile's block: the text inside `script { }`, re-indented."""
    body = textwrap.indent(textwrap.dedent(raw_script), " " * 12)
    return f"""
    profile {name} {{
        script {{
{body}
        }}
    }}
"""


def script_line_of(
    *, config: str, name: str, raw_script: str, config_line: int
) -> int | None:
    """
    Map a line number in the full config to a line of `raw_script`, when it
    falls inside that profile's rendered body; else None.
    """
    at = config.find(render_raw_profile(name, raw_script))
    if at < 0 or config_line <= 0:
        return None
    # The block starts with a newline ending line N; the profile header is
    # N+1, `script {` N+2, and the body's first line N+3.
    first_body_line = config.count("\n", 0, at) + 1 + 3
    offset = config_line - first_body_line + 1
    return offset if 1 <= offset <= raw_script.count("\n") + 1 else None


def _emits(session: Session, profile: Profile) -> bool:
    """Whether profile_generator writes a block for this row."""
    if not profile.generate_config:
        return False
    return (
        bool(profile.raw_script)
        or count_scripts(session=session, profile_id=profile.id) > 0
    )


def duplicate_profile_names(*, session: Session) -> list[str]:
    """
    Profiles defined both by a Profile row and by a `profile <name> {` block
    in the `profile` Configuration Option. tac_plus-ng rejects the second
    definition with only a line number; this names the profile instead. A
    script-less placeholder row is not emitted, so it does not count.
    """
    options = session.exec(
        select(ConfigurationOption).where(ConfigurationOption.name == "profile")
    ).all()
    in_options: set[str] = set()
    for option in options:
        in_options |= profile_names_in(option.config_option or "")
    if not in_options:
        return []
    rows = session.exec(select(Profile).where(col(Profile.name).in_(in_options))).all()
    return sorted(r.name for r in rows if _emits(session, r))


def profile_generator(
    session: Session,
    override: tuple[uuid.UUID | None, str, str] | None = None,
) -> str:
    """
    The profiles section of the config.

    `override` = (profile id or None, name, raw script) renders that text in
    place of the row with that id, or as an extra profile when the id is None,
    without touching the database. Used to syntax-check an unsaved edit.
    """
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
    override_id = override[0] if override else None
    for profile_db in profiles_db:
        if override and profile_db.id == override_id:
            profile_template += render_raw_profile(override[1], override[2])
            continue
        if profile_db.raw_script:
            profile_template += render_raw_profile(
                profile_db.name, profile_db.raw_script
            )
            continue
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

    if override and (
        override_id is None or all(p.id != override_id for p in profiles_db)
    ):
        # A new profile, or one with generate_config off being checked anyway.
        profile_template += render_raw_profile(override[1], override[2])

    return profile_template
