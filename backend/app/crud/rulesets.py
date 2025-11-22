from typing import Any

from sqlmodel import Session, select
from app.models import (
    Ruleset,
    RulesetCreate,
    RulesetUpdate,
    RulesetScript,
    RulesetScriptSet,
)


def get_ruleset_by_name(*, session: Session, name: str) -> Ruleset | None:
    statement = select(Ruleset).where(Ruleset.name == name)
    session_ruleset = session.exec(statement).first()
    return session_ruleset


def create_ruleset(*, session: Session, ruleset_create: RulesetCreate) -> Ruleset:
    db_obj = Ruleset.model_validate(ruleset_create)
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    return db_obj


def update_ruleset(
    *, session: Session, db_ruleset: Ruleset, ruleset_in: RulesetUpdate
) -> Any:
    ruleset_data = ruleset_in.model_dump(exclude_unset=True)
    extra_data = {}
    db_ruleset.sqlmodel_update(ruleset_data, update=extra_data)
    session.add(db_ruleset)
    session.commit()
    session.refresh(db_ruleset)
    return db_ruleset


def ruleset_generator(session: Session) -> str:
    rulesets_db = session.exec(select(Ruleset)).all()
    ruleset_template = ""
    for ruleset_db in rulesets_db:
        statement = select(RulesetScript).where(
            RulesetScript.ruleset_id == ruleset_db.id
        )
        script_in_ruleset = session.exec(statement).all()

        if script_in_ruleset == []:
            continue
        rulesetscript_template = ""
        for rulesetscript in script_in_ruleset:
            scriptset_in_ruleset = session.exec(
                select(RulesetScriptSet).where(
                    RulesetScriptSet.rulesetscript_id == rulesetscript.id
                )
            ).all()
            if scriptset_in_ruleset == []:
                continue
            rulesetscriptset_template = ""
            for rulesetscriptset in scriptset_in_ruleset:
                rulesetscriptset_info = rulesetscriptset.model_dump()
                rulesetscriptset_template += """{key}={value}""".format(
                    key=rulesetscriptset_info["key"],
                    value=rulesetscriptset_info["value"],
                )

            rulesetscript_info = rulesetscript.model_dump()
            rulesetscript_template += """{condition} ({key}=={value}){{
                {rulesetscriptset_template}
                {action}
            }}
            """.format(
                condition=rulesetscript_info["condition"],
                key=rulesetscript_info["key"],
                value=rulesetscript_info["value"],
                rulesetscriptset_template=rulesetscriptset_template,
                action=rulesetscript_info["action"],
            )
        ruleset_template += """rule {rule_name} {{
            enabled=yes
            script {{
                {rulesetscript_template}
            {action}
            }}
        }}
        """.format(
            rule_name=ruleset_db.name,
            rulesetscript_template=rulesetscript_template,
            action=ruleset_db.action,
        )
    ruleset_all = """
    ruleset {{
        {ruleset_template}
    }}""".format(
        ruleset_template=ruleset_template
    )
    return ruleset_all
