import uuid
from typing import Any

from sqlmodel import Session, col, func, select

from app.core.raw_script import (
    check_profile_name,
    normalize_raw_script,
    profile_names_in,
)
from app.crud import ordering, profilescripts
from app.crud.ordering import order_columns
from app.crud.script_render import script_header
from app.models import (
    ConfigurationOption,
    Profile,
    ProfileCreate,
    ProfileNamePublic,
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
    """
    Raises `ValueError` when a new name or new raw text fails the checks, or when switching
    a profile with scripts to raw mode.
    """
    profile_data = profile_in.model_dump(exclude_unset=True)
    new_name = profile_data.get("name")
    if new_name and new_name != db_profile.name:
        check_profile_name(new_name)
    new_text = profile_data.get("raw_script")
    if new_text and new_text != db_profile.raw_script:
        profile_data["raw_script"] = normalize_raw_script(new_text)
    if new_text:
        # Same lock as adding a script, so a concurrent script insert can't
        # slip in between this count and the commit.
        ordering.lock_parents(session, profilescripts.SIBLINGS, [db_profile.id])
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
    """
    A raw profile's block: the text inside `script { }`, verbatim. Not
    re-indented: quoted strings may span lines, and indenting them would
    change the value sent to the device.
    """
    return f"""
    profile {name} {{
        script {{
{raw_script}
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


def name_clash(
    *, session: Session, name: str, exclude_id: uuid.UUID | None
) -> str | None:
    """
    Why `name` can't be a profile's name, or None: another Profile row has it,
    or the `profile` Configuration Option already defines it (tac_plus-ng
    rejects a second definition with only a line number).
    """
    other = get_profile_by_name(session=session, name=name)
    if other is not None and other.id != exclude_id:
        return f"Another profile is already named '{name}'."
    options = session.exec(
        select(ConfigurationOption).where(ConfigurationOption.name == "profile")
    ).all()
    if any(name in profile_names_in(o.config_option or "") for o in options):
        return f"The 'profile' Configuration Option already defines '{name}'."
    return None


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
    # A row is emitted when generate_config is on and it has a raw script or
    # at least one structured script; one query for all candidates.
    with_scripts = select(ProfileScript.profile_id).distinct()
    rows = session.exec(
        select(Profile.name).where(
            col(Profile.name).in_(in_options),
            Profile.generate_config == True,  # noqa: E712
            col(Profile.raw_script).is_not(None) | col(Profile.id).in_(with_scripts),
        )
    ).all()
    return sorted(rows)


def profile_names(*, session: Session) -> list[ProfileNamePublic]:
    """
    Every profile name a ruleset can assign: the Profile rows that the
    generator emits (same rule as `duplicate_profile_names`), plus the
    `profile <name> {` blocks of the `profile` Configuration Option. A name
    defined both ways is listed once, as the row. Only name and description
    are read: `raw_script` can be large.
    """
    with_scripts = select(ProfileScript.profile_id).distinct()
    rows = session.exec(
        select(Profile.name, Profile.description).where(
            Profile.generate_config == True,  # noqa: E712
            col(Profile.raw_script).is_not(None) | col(Profile.id).in_(with_scripts),
        )
    ).all()
    names = {
        name: ProfileNamePublic(name=name, source="profile", description=description)
        for name, description in rows
    }
    options = session.exec(
        select(ConfigurationOption).where(ConfigurationOption.name == "profile")
    ).all()
    for option in options:
        for name in profile_names_in(option.config_option or ""):
            names.setdefault(
                name,
                ProfileNamePublic(
                    name=name,
                    source="config_option",
                    description="Defined in Configuration Option 'profile'",
                ),
            )
    return sorted(names.values(), key=lambda n: n.name)


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
