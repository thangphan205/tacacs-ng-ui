import uuid
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.deps import CurrentUser, SessionDep
from app.crud import alert_rules as crud_alert_rules
from app.models import AlertRule, AlertRuleCreate, AlertRulePublic, AlertRulesPublic, AlertRuleUpdate

router = APIRouter(prefix="/alert_rules", tags=["alert_rules"])


@router.get("/", response_model=AlertRulesPublic)
def read_alert_rules(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    rules, count = crud_alert_rules.get_alert_rules(session=session, skip=skip, limit=limit)
    return AlertRulesPublic(data=rules, count=count)


@router.post("/", response_model=AlertRulePublic)
def create_alert_rule(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    rule_in: AlertRuleCreate,
) -> Any:
    return crud_alert_rules.create_alert_rule(session=session, rule_in=rule_in)


@router.get("/{id}", response_model=AlertRulePublic)
def read_alert_rule_by_id(
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> Any:
    rule = crud_alert_rules.get_alert_rule(session=session, rule_id=id)
    if not rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return rule


@router.patch("/{id}", response_model=AlertRulePublic)
def update_alert_rule(
    *,
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
    rule_in: AlertRuleUpdate,
) -> Any:
    db_rule = crud_alert_rules.get_alert_rule(session=session, rule_id=id)
    if not db_rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return crud_alert_rules.update_alert_rule(session=session, db_rule=db_rule, rule_in=rule_in)


@router.delete("/{id}")
def delete_alert_rule(
    *,
    id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUser,
) -> dict[str, str]:
    db_rule = crud_alert_rules.get_alert_rule(session=session, rule_id=id)
    if not db_rule:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    crud_alert_rules.delete_alert_rule(session=session, db_rule=db_rule)
    return {"message": "Alert rule deleted"}
