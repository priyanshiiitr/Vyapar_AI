from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.models import CollectionCase, Customer, FollowUp, Invoice, Message
from app.services.audit import log_audit
from app.services.collections import create_reminder_draft
from app.services.money import format_inr
from app.services.observability import structured_log


def schedule_followup(
    db: Session,
    *,
    merchant_id: str,
    invoice_id: str,
    followup_date: date,
    reason: str,
) -> dict[str, Any]:
    invoice = db.scalar(
        select(Invoice).where(
            Invoice.merchant_id == merchant_id, Invoice.invoice_number == invoice_id
        )
    )
    if not invoice:
        return {"ok": False, "error": f"Invoice {invoice_id} not found"}
    case = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == invoice.id))
    if not case:
        return {"ok": False, "error": "No collection case"}

    fu = FollowUp(
        merchant_id=merchant_id,
        collection_case_id=case.id,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        followup_date=followup_date,
        reason=reason,
        status="pending",
        is_demo=invoice.is_demo,
    )
    db.add(fu)
    db.flush()

    event_id = None
    settings = get_settings()
    if settings.inngest_configured:
        try:
            from app.scheduler.inngest_app import send_followup_event

            event_id = send_followup_event(
                followup_id=fu.id,
                merchant_id=merchant_id,
                invoice_number=invoice.invoice_number,
                followup_date=followup_date.isoformat(),
            )
            fu.inngest_event_id = event_id
        except Exception as exc:  # noqa: BLE001
            structured_log("inngest_schedule_failed", error=str(exc), followup_id=fu.id)

    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="followup",
        entity_id=fu.id,
        action="followup_scheduled",
        detail=f"{invoice.invoice_number} on {followup_date} inngest={bool(event_id)}",
        actor="agent",
    )
    # caller commits
    return {
        "ok": True,
        "followup_id": fu.id,
        "followup_date": followup_date.isoformat(),
        "inngest_event_id": event_id,
        "reason": reason,
    }


def _precheck_followup(db: Session, fu: FollowUp) -> tuple[bool, str]:
    invoice = db.get(Invoice, fu.invoice_id)
    customer = db.get(Customer, fu.customer_id)
    case = db.get(CollectionCase, fu.collection_case_id)
    if not invoice or not customer or not case:
        return False, "missing_entities"
    if invoice.outstanding_paise <= 0 or invoice.status == "paid":
        return False, "already_paid"
    if case.status == "closed":
        return False, "case_closed"
    if case.status == "disputed" or customer.dispute_active:
        return False, "dispute_active"
    if customer.opted_out:
        return False, "customer_opted_out"
    # duplicate pending approval already exists
    existing = db.scalar(
        select(Message).where(
            Message.collection_case_id == case.id,
            Message.status == "pending_approval",
        )
    )
    if existing:
        return False, "approval_already_pending"
    return True, "ok"


def process_followup(db: Session, followup_id: int) -> dict[str, Any]:
    fu = db.get(FollowUp, followup_id)
    if not fu:
        return {"ok": False, "error": "Follow-up not found"}
    if fu.status != "pending":
        return {"ok": False, "error": f"Follow-up status is {fu.status}"}

    ok, reason = _precheck_followup(db, fu)
    if not ok:
        fu.status = "skipped"
        fu.skip_reason = reason
        fu.processed_at = datetime.utcnow()
        log_audit(
            db,
            merchant_id=fu.merchant_id,
            entity_type="followup",
            entity_id=fu.id,
            action="followup_skipped",
            detail=reason,
        )
        db.commit()
        return {"ok": True, "skipped": True, "reason": reason}

    invoice = db.get(Invoice, fu.invoice_id)
    assert invoice is not None
    draft = create_reminder_draft(
        db,
        merchant_id=fu.merchant_id,
        invoice_id=invoice.invoice_number,
        language="hinglish",
        tone="polite",
        message_text=None,
    )
    fu.status = "processed"
    fu.processed_at = datetime.utcnow()
    log_audit(
        db,
        merchant_id=fu.merchant_id,
        entity_type="followup",
        entity_id=fu.id,
        action="followup_processed",
        detail=f"created draft message_id={draft.get('message_id')} balance={format_inr(invoice.outstanding_paise)}",
    )
    db.commit()
    return {"ok": True, "skipped": False, "draft": draft}


def process_due_followups(db: Session, merchant_id: str | None = None) -> dict[str, Any]:
    today = date.today()
    q = select(FollowUp).where(FollowUp.status == "pending", FollowUp.followup_date <= today)
    if merchant_id:
        q = q.where(FollowUp.merchant_id == merchant_id)
    due = list(db.scalars(q))
    results = []
    for fu in due:
        results.append(process_followup(db, fu.id))
    return {"processed": len(results), "results": results}


def list_followups(db: Session, merchant_id: str, status: str | None = None) -> list[dict]:
    q = (
        select(FollowUp)
        .options(joinedload(FollowUp.collection_case))
        .where(FollowUp.merchant_id == merchant_id)
        .order_by(FollowUp.followup_date.asc())
    )
    if status:
        q = q.where(FollowUp.status == status)
    rows = []
    for fu in db.scalars(q).unique():
        inv = db.get(Invoice, fu.invoice_id)
        rows.append(
            {
                "id": fu.id,
                "invoice_id": inv.invoice_number if inv else None,
                "followup_date": fu.followup_date.isoformat(),
                "reason": fu.reason,
                "status": fu.status,
                "skip_reason": fu.skip_reason,
                "inngest_event_id": fu.inngest_event_id,
            }
        )
    return rows
