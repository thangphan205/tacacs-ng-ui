import uuid

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import settings
from app.crud import alert_rules as crud_alert_rules
from app.models import AlertRule, AlertRuleCreate


def _make_rule(session: Session, **kwargs) -> AlertRule:
    defaults = dict(
        name=f"test-rule-{uuid.uuid4().hex[:8]}",
        log_type="auth",
        condition_field="fail_count",
        condition_operator="gt",
        threshold=5.0,
        time_window_minutes=10,
        severity="medium",
        cooldown_minutes=60,
        enabled=True,
    )
    defaults.update(kwargs)
    rule_in = AlertRuleCreate(**defaults)
    return crud_alert_rules.create_alert_rule(session=session, rule_in=rule_in)


# ---------------------------------------------------------------------------
# CRUD — Alert Rules
# ---------------------------------------------------------------------------

class TestAlertRuleCRUD:
    def test_create_and_read(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        rule = _make_rule(db, name="crud-read-rule")
        resp = client.get(
            f"{settings.API_V1_STR}/alert_rules/{rule.id}",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == str(rule.id)
        assert data["name"] == "crud-read-rule"
        assert data["is_system"] is False

    def test_list_includes_rule(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        rule = _make_rule(db)
        resp = client.get(
            f"{settings.API_V1_STR}/alert_rules/",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 200
        ids = [r["id"] for r in resp.json()["data"]]
        assert str(rule.id) in ids

    def test_create_via_api(self, client: TestClient, superuser_token_headers: dict) -> None:
        payload = {
            "name": "api-created-rule",
            "log_type": "auth",
            "condition_field": "fail_count",
            "condition_operator": "gt",
            "threshold": 10,
            "time_window_minutes": 15,
            "severity": "high",
            "cooldown_minutes": 30,
            "enabled": True,
        }
        resp = client.post(
            f"{settings.API_V1_STR}/alert_rules/",
            headers=superuser_token_headers,
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == payload["name"]
        assert data["severity"] == "high"
        assert data["is_system"] is False

    def test_update_rule(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        rule = _make_rule(db)
        resp = client.patch(
            f"{settings.API_V1_STR}/alert_rules/{rule.id}",
            headers=superuser_token_headers,
            json={"severity": "critical", "cooldown_minutes": 120},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["severity"] == "critical"
        assert data["cooldown_minutes"] == 120

    def test_delete_user_rule(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        rule = _make_rule(db)
        resp = client.delete(
            f"{settings.API_V1_STR}/alert_rules/{rule.id}",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 200
        resp2 = client.get(
            f"{settings.API_V1_STR}/alert_rules/{rule.id}",
            headers=superuser_token_headers,
        )
        assert resp2.status_code == 404

    def test_delete_system_rule_forbidden(self, client: TestClient, superuser_token_headers: dict, db: Session) -> None:
        system_rule = AlertRule(
            name=f"sys-rule-{uuid.uuid4().hex[:8]}",
            log_type="auth",
            condition_field="fail_count",
            condition_operator="gt",
            threshold=5.0,
            time_window_minutes=10,
            severity="high",
            cooldown_minutes=30,
            enabled=True,
            is_system=True,
        )
        db.add(system_rule)
        db.commit()
        db.refresh(system_rule)

        resp = client.delete(
            f"{settings.API_V1_STR}/alert_rules/{system_rule.id}",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 403
        assert "system" in resp.json()["detail"].lower()

    def test_read_not_found(self, client: TestClient, superuser_token_headers: dict) -> None:
        resp = client.get(
            f"{settings.API_V1_STR}/alert_rules/{uuid.uuid4()}",
            headers=superuser_token_headers,
        )
        assert resp.status_code == 404

    def test_config_type_rule(self, client: TestClient, superuser_token_headers: dict) -> None:
        payload = {
            "name": "config-change-rule",
            "log_type": "config",
            "condition_field": "config_action",
            "condition_operator": "any_change",
            "threshold": 1,
            "time_window_minutes": 5,
            "severity": "high",
            "cooldown_minutes": 5,
            "enabled": True,
        }
        resp = client.post(
            f"{settings.API_V1_STR}/alert_rules/",
            headers=superuser_token_headers,
            json=payload,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["log_type"] == "config"
        assert data["condition_operator"] == "any_change"
