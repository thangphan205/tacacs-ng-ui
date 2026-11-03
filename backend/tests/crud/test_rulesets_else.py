import uuid

from sqlmodel import Session, select

from app.crud.rulesets import ruleset_generator
from app.models import Ruleset, RulesetScript, RulesetScriptSet


def test_else_script_renders_without_test_expression(db: Session) -> None:
    tag = uuid.uuid4().hex[:8]
    ruleset = Ruleset(name=f"rs-{tag}", action="permit")
    db.add(ruleset)
    db.commit()
    db.refresh(ruleset)

    for condition, key, value in (("if", "service", "shell"), ("else", "x", "y")):
        script = RulesetScript(
            condition=condition,
            key=key,
            value=value,
            action="permit",
            ruleset_id=ruleset.id,
        )
        db.add(script)
        db.commit()
        db.refresh(script)
        db.add(RulesetScriptSet(key="priv-lvl", value="15", rulesetscript_id=script.id))
        db.commit()

    out = ruleset_generator(session=db)
    assert "if (service==shell){" in out
    assert "else{" in out
    assert "else (" not in out
    db.delete(ruleset)
    for script in db.exec(
        select(RulesetScript).where(RulesetScript.ruleset_id == ruleset.id)
    ).all():
        for scriptset in db.exec(
            select(RulesetScriptSet).where(
                RulesetScriptSet.rulesetscript_id == script.id
            )
        ).all():
            db.delete(scriptset)
        db.delete(script)
    db.commit()
