from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import get_settings
from app.database import get_db
from app.models import CollectionCase, Invoice, Message, PaymentPromise
from app.services.collections import (
    approve_message,
    create_reminder_draft,
    list_merchant_escalations,
    list_pending_approvals,
    record_payment_promise,
    reject_message,
)
from app.services.money import format_inr
from app.scheduler.service import list_followups

router = APIRouter(prefix="/collections")


class ReminderRequest(BaseModel):
    invoice_id: str
    language: str = "hinglish"
    tone: str = "polite"
    message_text: str | None = None


class ApproveRequest(BaseModel):
    edited_body: str | None = None


class RejectRequest(BaseModel):
    reason: str = ""


class PromiseRequest(BaseModel):
    invoice_id: str
    promise_date: str
    customer_statement: str = ""
    promised_amount: str | None = None


@router.get("/cases")
def cases(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    rows = list(
        db.scalars(
            select(CollectionCase)
            .options(joinedload(CollectionCase.invoice).joinedload(Invoice.customer))
            .where(CollectionCase.merchant_id == mid)
        ).unique()
    )
    return {
        "cases": [
            {
                "id": c.id,
                "invoice_id": c.invoice.invoice_number if c.invoice else None,
                "customer": c.invoice.customer.name if c.invoice and c.invoice.customer else None,
                "status": c.status,
                "outstanding": format_inr(c.outstanding_paise),
                "close_reason": c.close_reason,
            }
            for c in rows
        ]
    }


@router.get("/approvals")
def approvals(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return {"approvals": list_pending_approvals(db, mid)}


@router.get("/messages")
def messages(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    rows = list(
        db.scalars(
            select(Message)
            .options(joinedload(Message.collection_case))
            .where(Message.merchant_id == mid)
            .order_by(Message.id.desc())
        ).unique()
    )
    out = []
    for m in rows:
        inv = db.get(Invoice, m.invoice_id) if m.invoice_id else None
        cust_name = None
        if m.customer_id:
            from app.models import Customer

            cust = db.get(Customer, m.customer_id)
            cust_name = cust.name if cust else None
        out.append(
            {
                "id": m.id,
                "status": m.status,
                "language": m.language,
                "tone": m.tone,
                "body": m.body,
                "sandbox_note": m.sandbox_note,
                "channel": m.channel,
                "customer_id": m.customer_id,
                "customer": cust_name,
                "invoice_id": inv.invoice_number if inv else None,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    return {"messages": out}


@router.post("/reminders")
def reminders(payload: ReminderRequest, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return create_reminder_draft(
        db,
        merchant_id=mid,
        invoice_id=payload.invoice_id,
        language=payload.language,
        tone=payload.tone,
        message_text=payload.message_text,
    )


@router.post("/approvals/{message_id}/approve")
def approve(message_id: int, payload: ApproveRequest, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return approve_message(db, mid, message_id, payload.edited_body)


@router.post("/approvals/{message_id}/reject")
def reject(message_id: int, payload: RejectRequest, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return reject_message(db, mid, message_id, payload.reason)


@router.post("/promises")
def promises(payload: PromiseRequest, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return record_payment_promise(
        db,
        merchant_id=mid,
        invoice_id=payload.invoice_id,
        promise_date=date.fromisoformat(payload.promise_date)
        if "-" in payload.promise_date
        else __import__("app.agent.tools", fromlist=["_parse_date"])._parse_date(payload.promise_date),
        customer_statement=payload.customer_statement,
        promised_amount=payload.promised_amount,
    )


@router.get("/promises")
def list_promises(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    # Backfill promises from WhatsApp chats that were stored before auto-record
    from app.services.whatsapp_mock import sync_promises_from_chat

    sync = sync_promises_from_chat(db, mid)
    rows = list(
        db.scalars(
            select(PaymentPromise)
            .where(PaymentPromise.merchant_id == mid)
            .order_by(PaymentPromise.id.desc())
        )
    )
    return {
        "promises": [
            {
                "id": p.id,
                "invoice_pk": p.invoice_id,
                "invoice_id": (db.get(Invoice, p.invoice_id).invoice_number if p.invoice_id else None),
                "promised": format_inr(p.promised_paise),
                "promise_date": p.promise_date.isoformat(),
                "status": p.status,
                "statement": p.customer_statement,
            }
            for p in rows
        ],
        "sync_from_whatsapp": sync,
    }


@router.get("/followups")
def followups(status: str | None = None, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return {"followups": list_followups(db, mid, status)}


@router.get("/escalations")
def escalations(db: Session = Depends(get_db)):
    """Merchant inbox: refusal/dispute WhatsApp replies routed here automatically."""
    mid = get_settings().DEMO_MERCHANT_ID
    return {"escalations": list_merchant_escalations(db, mid)}
