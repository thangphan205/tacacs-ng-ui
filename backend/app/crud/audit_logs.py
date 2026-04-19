import logging
import threading
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from sqlmodel import Session, delete, func, select

from app.core.config import settings
from app.models import AuditLog, AuditLogCreate

logger = logging.getLogger(__name__)


def create_audit_log(
    *,
    session: Session,
    audit_log_in: AuditLogCreate,
    user_id: uuid.UUID | None,
    user_email: str,
    ip_address: str | None,
) -> AuditLog:
    db_obj = AuditLog(
        **audit_log_in.model_dump(),
        user_id=user_id,
        user_email=user_email,
        ip_address=ip_address,
    )
    session.add(db_obj)
    session.commit()
    session.refresh(db_obj)
    _forward_to_siem(db_obj)
    return db_obj


def get_audit_logs(
    *,
    session: Session,
    skip: int = 0,
    limit: int = 100,
    search: str | None = None,
) -> tuple[list[AuditLog], int]:
    stmt = select(AuditLog)
    count_stmt = select(func.count()).select_from(AuditLog)
    if search:
        f = (
            AuditLog.user_email.contains(search)
            | AuditLog.entity_type.contains(search)
            | AuditLog.action.contains(search)
            | AuditLog.entity_id.contains(search)
            | AuditLog.description.contains(search)
        )
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)
    count = session.exec(count_stmt).one()
    logs = session.exec(
        stmt.order_by(AuditLog.created_at.desc()).offset(skip).limit(limit)
    ).all()
    return list(logs), count


def purge_old_audit_logs(*, session: Session) -> int:
    deleted = 0
    if settings.AUDIT_LOG_RETENTION_DAYS > 0:
        cutoff = datetime.now(timezone.utc) - timedelta(days=settings.AUDIT_LOG_RETENTION_DAYS)
        result = session.exec(delete(AuditLog).where(AuditLog.created_at < cutoff))
        deleted += result.rowcount
    if settings.AUDIT_LOG_MAX_ROWS > 0:
        count = session.exec(select(func.count()).select_from(AuditLog)).one()
        excess = count - settings.AUDIT_LOG_MAX_ROWS
        if excess > 0:
            oldest_ids = session.exec(
                select(AuditLog.id).order_by(AuditLog.created_at.asc()).limit(excess)
            ).all()
            session.exec(delete(AuditLog).where(AuditLog.id.in_(oldest_ids)))
            deleted += excess
    session.commit()
    return deleted


_SENSITIVE: frozenset[str] = frozenset({"hashed_password", "encrypted_secret"})


def log_entity_action(
    *,
    session: Session,
    action: str,
    entity_type: str,
    entity_id: str | None,
    user_id: uuid.UUID | None,
    user_email: str,
    ip_address: str | None,
    user_agent: str | None,
    old_values: str | None = None,
    new_values: str | None = None,
    description: str | None = None,
) -> None:
    create_audit_log(
        session=session,
        audit_log_in=AuditLogCreate(
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            user_agent=user_agent,
            old_values=old_values,
            new_values=new_values,
        ),
        user_id=user_id,
        user_email=user_email,
        ip_address=ip_address,
    )


def _forward_to_siem(log: AuditLog) -> None:
    if not settings.SIEM_WEBHOOK_URL:
        return
    payload = {
        "time": log.created_at.timestamp(),
        "event": {
            "id": str(log.id),
            "action": log.action,
            "entity_type": log.entity_type,
            "entity_id": log.entity_id,
            "user_id": str(log.user_id) if log.user_id else None,
            "user_email": log.user_email,
            "ip_address": log.ip_address,
            "description": log.description,
        },
        "sourcetype": "tacacs-ng-ui:audit",
    }
    headers: dict[str, str] = {}
    if settings.SIEM_WEBHOOK_TOKEN:
        headers["Authorization"] = f"Splunk {settings.SIEM_WEBHOOK_TOKEN}"

    def _post() -> None:
        try:
            httpx.post(settings.SIEM_WEBHOOK_URL, json=payload, headers=headers, timeout=3)  # type: ignore[arg-type]
        except Exception:
            logger.warning("Failed to forward audit log to SIEM", exc_info=True)

    threading.Thread(target=_post, daemon=True).start()
