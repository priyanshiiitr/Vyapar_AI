from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog


def log_audit(
    db: Session,
    *,
    merchant_id: str,
    entity_type: str,
    entity_id: str | int,
    action: str,
    detail: str | None = None,
    actor: str = "system",
) -> AuditLog:
    entry = AuditLog(
        merchant_id=merchant_id,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        detail=detail,
        actor=actor,
    )
    db.add(entry)
    return entry
