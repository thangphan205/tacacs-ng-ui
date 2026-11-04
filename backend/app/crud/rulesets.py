from typing import Any

from sqlmodel import Session, col, select

from app.crud import ordering
from app.crud.ordering import order_columns
from app.crud.script_render import script_header
from app.models import (
    ConfigurationOption,
    Ruleset,
    RulesetCreate,
    RulesetScript,
    RulesetScriptSet,
    RulesetUpdate,
)


def get_ruleset_by_name(*, session: Session, name: str) -> Ruleset | None:
    statement = select(Ruleset).where(Ruleset.name == name)
    session_ruleset = session.exec(statement).first()
    return session_ruleset


# Rulesets are siblings of one another: tac_plus-ng evaluates the `rule` blocks
# inside `ruleset { }` top to bottom, so they carry a position like scripts do.
_NO_PARENT = {"parent_column": None, "parent_id": None}


def create_ruleset(*, session: Session, ruleset_create: RulesetCreate) -> Ruleset:
    data = ruleset_create.model_dump(exclude={"position"})
    data["position"] = ordering.next_position(
        session=session, model=Ruleset, **_NO_PARENT
    )
    db_obj = Ruleset.model_validate(data)
    session.add(db_obj)
    if ruleset_create.position is None:
        session.commit()
        session.refresh(db_obj)
        return db_obj
    return move_ruleset(
        session=session, db_ruleset=db_obj, position=ruleset_create.position
    )


def update_ruleset(
    *, session: Session, db_ruleset: Ruleset, ruleset_in: RulesetUpdate
) -> Any:
    ruleset_data = ruleset_in.model_dump(exclude_unset=True)
    new_position = ruleset_data.pop("position", None)
    db_ruleset.sqlmodel_update(ruleset_data)
    session.add(db_ruleset)
    if new_position is None or new_position == db_ruleset.position:
        session.commit()
        session.refresh(db_ruleset)
        return db_ruleset
    return move_ruleset(session=session, db_ruleset=db_ruleset, position=new_position)


def move_ruleset(*, session: Session, db_ruleset: Ruleset, position: int) -> Ruleset:
    ordering.move(
        session=session,
        row=db_ruleset,
        model=Ruleset,
        position=position,
        **_NO_PARENT,
    )
    return db_ruleset


def delete_ruleset(*, session: Session, db_ruleset: Ruleset) -> None:
    """Delete and renumber the remaining rulesets so positions stay 0..n-1."""
    session.delete(db_ruleset)
    session.flush()
    ordering.compact(session=session, model=Ruleset, **_NO_PARENT)
    session.commit()


def ruleset_generator(session: Session) -> str:
    statement_configuration_rule = select(ConfigurationOption).where(
        ConfigurationOption.name == "rule"
    )
    configuration_rule_options = session.exec(statement_configuration_rule).all()
    ruleset_template = ""
    if configuration_rule_options:
        ruleset_template += "\n   # Ruleset Configuration Options\n"
        for configuration_rule_option in configuration_rule_options:
            ruleset_template += f"""     {configuration_rule_option.config_option}\n"""
        ruleset_template += "\n   # End of Ruleset Configuration Options\n"

    rulesets_db = session.exec(
        select(Ruleset)
        .where(Ruleset.generate_config == True)
        .order_by(*order_columns(Ruleset))
    ).all()

    for ruleset_db in rulesets_db:
        # Order is policy: tac_plus-ng stops at the first matching permit/deny.
        statement = (
            select(RulesetScript)
            .where(RulesetScript.ruleset_id == ruleset_db.id)
            .order_by(*order_columns(RulesetScript))
        )
        script_in_ruleset = session.exec(statement).all()

        if script_in_ruleset == []:
            continue
        rulesetscript_template = ""
        for rulesetscript in script_in_ruleset:
            scriptset_in_ruleset = session.exec(
                select(RulesetScriptSet)
                .where(RulesetScriptSet.rulesetscript_id == rulesetscript.id)
                .order_by(col(RulesetScriptSet.created_at), col(RulesetScriptSet.id))
            ).all()
            # A script with no `set` lines is still a rule — `if (...) { deny }`
            # must not be dropped, or traffic falls through to the next script.
            rulesetscriptset_template = ""
            for rulesetscriptset in scriptset_in_ruleset:
                rulesetscriptset_info = rulesetscriptset.model_dump()
                rulesetscriptset_template += """          {key}={value}\n""".format(
                    key=rulesetscriptset_info["key"],
                    value=rulesetscriptset_info["value"],
                )

            rulesetscript_info = rulesetscript.model_dump()
            header = script_header(
                rulesetscript_info["condition"],
                rulesetscript_info["key"],
                rulesetscript_info["value"],
            )
            rulesetscript_template += """       {header}{{
{rulesetscriptset_template}
          {action}
        }}\n""".format(
                header=header,
                rulesetscriptset_template=rulesetscriptset_template,
                action=rulesetscript_info["action"],
            )
        ruleset_template += f"""     rule {ruleset_db.name} {{
        enabled=yes
        script {{
{rulesetscript_template}
            {ruleset_db.action}
            }}
        }}\n"""

    ruleset_all = f"""
    ruleset {{
{ruleset_template}
    }}\n"""
    return ruleset_all
