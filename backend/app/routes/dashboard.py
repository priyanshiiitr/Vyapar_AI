from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.models import AuditLog, Invoice
from app.services.dashboard import get_dashboard_summary
from app.services.money import format_inr

router = APIRouter()


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return get_dashboard_summary(db, mid)


@router.get("/activity")
def activity(db: Session = Depends(get_db), limit: int = 50):
    mid = get_settings().DEMO_MERCHANT_ID
    rows = list(
        db.scalars(
            select(AuditLog)
            .where(AuditLog.merchant_id == mid)
            .order_by(AuditLog.id.desc())
            .limit(limit)
        )
    )
    return {
        "events": [
            {
                "id": a.id,
                "action": a.action,
                "entity_type": a.entity_type,
                "entity_id": a.entity_id,
                "detail": a.detail,
                "actor": a.actor,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    }


@router.get("/invoices")
def list_invoices(status: str | None = None, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    q = (
        select(Invoice)
        .options(joinedload(Invoice.customer))
        .where(Invoice.merchant_id == mid)
        .order_by(Invoice.id.asc())
    )
    invoices = list(db.scalars(q).unique())
    if status:
        invoices = [i for i in invoices if i.status == status]
    return {
        "invoices": [
            {
                "invoice_id": i.invoice_number,
                "customer": i.customer.name if i.customer else None,
                "amount": format_inr(i.amount_paise),
                "paid": format_inr(i.paid_paise),
                "outstanding": format_inr(i.outstanding_paise),
                "status": i.status,
                "due_date": i.due_date.isoformat(),
                "description": i.description,
            }
            for i in invoices
        ]
    }
