from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import CollectionCase, FollowUp, Invoice, Message, PaymentPromise
from app.services.audit import log_audit
from app.services.money import format_inr
from app.services.reconciliation import ensure_collection_case


def create_reminder_draft(
    db: Session,
    *,
    merchant_id: str,
    invoice_id: str,
    language: str = "hinglish",
    tone: str = "polite",
    message_text: Optional[str] = None,
) -> dict:
    invoice = db.scalar(
        select(Invoice)
        .options(joinedload(Invoice.customer))
        .where(Invoice.merchant_id == merchant_id, Invoice.invoice_number == invoice_id)
    )
    if not invoice:
        return {"ok": False, "error": f"Invoice {invoice_id} not found"}

    case = ensure_collection_case(db, invoice)
    if not case:
        return {"ok": False, "error": "No open collection case (invoice may be fully paid)"}

    balance = format_inr(invoice.outstanding_paise)
    amount = format_inr(invoice.amount_paise)
    name = invoice.customer.name

    if message_text:
        body = message_text
        # Enforce ledger facts cannot be invented — inject verified balance footer
        if balance not in body and invoice.invoice_number not in body:
            body = f"{body}\n\n(Verified) Invoice {invoice.invoice_number} outstanding: {balance}"
    else:
        body = _template_message(
            language=language.lower(),
            tone=tone.lower(),
            name=name,
            invoice_number=invoice.invoice_number,
            amount=amount,
            balance=balance,
        )

    msg = Message(
        merchant_id=merchant_id,
        collection_case_id=case.id,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        language=language.lower(),
        tone=tone.lower(),
        body=body,
        status="pending_approval",
        channel="sandbox",
        is_demo=invoice.is_demo,
    )
    db.add(msg)
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="message",
        entity_id="pending",
        action="reminder_draft_created",
        detail=f"{invoice.invoice_number} lang={language} tone={tone}",
        actor="agent",
    )
    db.commit()
    db.refresh(msg)
    return {
        "ok": True,
        "message_id": msg.id,
        "status": msg.status,
        "body": msg.body,
        "invoice_id": invoice.invoice_number,
        "outstanding": balance,
    }


def _template_message(*, language: str, tone: str, name: str, invoice_number: str, amount: str, balance: str) -> str:
    if language in ("hi", "hindi"):
        if "firm" in tone:
            return (
                f"नमस्ते {name}, कृपया इनवॉइस {invoice_number} का बकाया {balance} "
                f"(मूल राशि {amount}) जल्द चुकाएँ। धन्यवाद।"
            )
        return (
            f"नमस्ते {name}, इनवॉइस {invoice_number} के लिए बकाया राशि {balance} है। "
            f"कृपया सुविधा अनुसार भुगतान करें। धन्यवाद।"
        )
    if language in ("hinglish", "hi-en"):
        if "firm" in tone:
            return (
                f"Namaste {name}, invoice {invoice_number} ka outstanding {balance} abhi pending hai "
                f"(original {amount}). Please clear jaldi. Dhanyavaad."
            )
        return (
            f"Namaste {name}! Invoice {invoice_number} ke liye {balance} outstanding hai "
            f"(bill {amount}). Jab convenient ho, payment kar dijiye. Shukriya!"
        )
    # english
    if "firm" in tone:
        return (
            f"Hello {name}, a respectful reminder that invoice {invoice_number} still has "
            f"{balance} outstanding (original {amount}). Please arrange payment soon. Thank you."
        )
    if "friendly" in tone:
        return (
            f"Hi {name}! Just a friendly note — invoice {invoice_number} has {balance} left "
            f"(of {amount}). Happy to help if you need anything. Thanks!"
        )
    return (
        f"Dear {name}, regarding invoice {invoice_number}, the verified outstanding balance is "
        f"{balance} (invoice total {amount}). Kindly arrange payment at your earliest convenience."
    )


def approve_message(db: Session, merchant_id: str, message_id: int, edited_body: str | None = None) -> dict:
    msg = db.scalar(
        select(Message).where(Message.id == message_id, Message.merchant_id == merchant_id)
    )
    if not msg:
        return {"ok": False, "error": "Message not found"}
    if msg.status not in ("pending_approval", "draft"):
        return {"ok": False, "error": f"Cannot approve message in status {msg.status}"}
    if edited_body:
        msg.body = edited_body
    msg.status = "sandbox_sent"
    msg.channel = "whatsapp_mock"
    msg.sandbox_note = (
        "Demo WhatsApp mock sent. No real WhatsApp/SMS/email left this laptop."
    )
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="message",
        entity_id=msg.id,
        action="sandbox_message_sent",
        detail=msg.sandbox_note,
        actor="merchant",
    )
    db.commit()
    return {
        "ok": True,
        "message_id": msg.id,
        "status": msg.status,
        "note": msg.sandbox_note,
        "customer_id": msg.customer_id,
        "whatsapp_thread_path": f"/whatsapp?customer={msg.customer_id}" if msg.customer_id else "/whatsapp",
    }


def escalate_case_to_merchant(
    db: Session,
    *,
    merchant_id: str,
    invoice: Invoice,
    customer_name: str,
    customer_reply: str,
    intent: str,
    source_message_id: int | None = None,
) -> dict:
    """Route refusal/dispute replies straight to the merchant — no auto customer send."""
    case = ensure_collection_case(db, invoice)
    if not case:
        return {"ok": False, "error": "No open collection case to escalate"}

    if intent == "dispute":
        case.status = "disputed"
    elif intent == "payment_claim":
        case.status = "escalated"
    else:
        case.status = "escalated"
    case.outstanding_paise = invoice.outstanding_paise

    # Pause automation — merchant owns the next step
    for fu in db.scalars(
        select(FollowUp).where(
            FollowUp.collection_case_id == case.id,
            FollowUp.status == "pending",
        )
    ):
        fu.status = "cancelled"
        fu.skip_reason = f"escalated_to_merchant:{intent}"
        fu.processed_at = datetime.utcnow()

    for msg in db.scalars(
        select(Message).where(
            Message.collection_case_id == case.id,
            Message.status.in_(["draft", "pending_approval"]),
        )
    ):
        msg.status = "cancelled"

    reason_map = {
        "refusal": "payment refusal / can't pay",
        "dispute": "dispute / contest",
        "payment_claim": "customer CLAIMS already paid (await ledger / screenshot)",
    }
    reason_label = reason_map.get(intent, intent)
    alert_body = (
        f"ESCALATION — needs merchant decision\n"
        f"Customer: {customer_name}\n"
        f"Invoice: {invoice.invoice_number}\n"
        f"Outstanding: {format_inr(invoice.outstanding_paise)}\n"
        f"Detected: {reason_label}\n"
        f'Customer reply: "{customer_reply.strip()}"\n'
        f"Ledger unchanged. Do NOT mark paid from chat. "
        + (
            "Ask for UTR/screenshot in WhatsApp mock, then match a bank CSV/txn on Reconciliation."
            if intent == "payment_claim"
            else "Approve any next message manually."
        )
    )
    alert = Message(
        merchant_id=merchant_id,
        collection_case_id=case.id,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        language="en",
        tone="merchant_escalation",
        body=alert_body,
        status="merchant_escalation",
        channel="merchant_inbox",
        sandbox_note=f"Auto-escalated from WhatsApp mock (intent={intent})",
        is_demo=invoice.is_demo,
    )
    db.add(alert)
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="collection_case",
        entity_id=case.id,
        action="escalated_to_merchant",
        detail=(
            f"{invoice.invoice_number} intent={intent} "
            f"from_message={source_message_id} reply={customer_reply[:120]}"
        ),
        actor="system",
    )
    db.flush()
    return {
        "ok": True,
        "escalated": True,
        "intent": intent,
        "case_id": case.id,
        "case_status": case.status,
        "alert_message_id": alert.id,
        "invoice_id": invoice.invoice_number,
        "outstanding": format_inr(invoice.outstanding_paise),
        "merchant_alert": alert_body,
        "note": "Routed to merchant inbox. Automated follow-ups paused.",
    }


def list_merchant_escalations(db: Session, merchant_id: str) -> list[dict]:
    rows = list(
        db.scalars(
            select(Message)
            .where(
                Message.merchant_id == merchant_id,
                Message.status == "merchant_escalation",
            )
            .order_by(Message.id.desc())
            .limit(50)
        )
    )
    out = []
    for m in rows:
        inv = db.get(Invoice, m.invoice_id) if m.invoice_id else None
        out.append(
            {
                "id": m.id,
                "invoice_id": inv.invoice_number if inv else None,
                "customer_id": m.customer_id,
                "body": m.body,
                "sandbox_note": m.sandbox_note,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "case_id": m.collection_case_id,
            }
        )
    return out


def reject_message(db: Session, merchant_id: str, message_id: int, reason: str = "") -> dict:
    msg = db.scalar(
        select(Message).where(Message.id == message_id, Message.merchant_id == merchant_id)
    )
    if not msg:
        return {"ok": False, "error": "Message not found"}
    msg.status = "rejected"
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="message",
        entity_id=msg.id,
        action="message_rejected",
        detail=reason or "rejected by merchant",
        actor="merchant",
    )
    db.commit()
    return {"ok": True, "message_id": msg.id, "status": "rejected"}


def record_payment_promise(
    db: Session,
    *,
    merchant_id: str,
    invoice_id: str,
    promise_date: date,
    customer_statement: str = "",
    promised_amount: str | int | None = None,
) -> dict:
    from app.services.money import parse_amount_to_paise
    from app.scheduler.service import schedule_followup

    invoice = db.scalar(
        select(Invoice)
        .options(joinedload(Invoice.customer))
        .where(Invoice.merchant_id == merchant_id, Invoice.invoice_number == invoice_id)
    )
    if not invoice:
        return {"ok": False, "error": f"Invoice {invoice_id} not found"}
    if invoice.outstanding_paise <= 0:
        return {
            "ok": False,
            "error": f"Invoice {invoice_id} has no outstanding balance — nothing to promise",
        }
    case = ensure_collection_case(db, invoice)
    if not case:
        return {"ok": False, "error": "Invoice has no outstanding balance"}

    if promised_amount is None or promised_amount == "":
        promised_paise = invoice.outstanding_paise
    else:
        promised_paise = (
            promised_amount
            if isinstance(promised_amount, int)
            else parse_amount_to_paise(str(promised_amount))
        )

    promise = PaymentPromise(
        merchant_id=merchant_id,
        collection_case_id=case.id,
        invoice_id=invoice.id,
        customer_id=invoice.customer_id,
        promised_paise=promised_paise,
        promise_date=promise_date,
        customer_statement=customer_statement,
        status="active",
        is_demo=invoice.is_demo,
    )
    db.add(promise)
    case.status = "promised"
    case.outstanding_paise = invoice.outstanding_paise
    db.flush()

    follow = schedule_followup(
        db,
        merchant_id=merchant_id,
        invoice_id=invoice.invoice_number,
        followup_date=promise_date,
        reason=f"Payment promise follow-up for {invoice.invoice_number}",
    )
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="promise",
        entity_id=promise.id,
        action="payment_promise_recorded",
        detail=f"{invoice.invoice_number} on {promise_date} amount={format_inr(promised_paise)}",
        actor="agent",
    )
    db.commit()
    return {
        "ok": True,
        "promise_id": promise.id,
        "followup": follow,
        "promised": format_inr(promised_paise),
        "promise_date": promise_date.isoformat(),
    }


def list_pending_approvals(db: Session, merchant_id: str) -> list[dict]:
    rows = db.scalars(
        select(Message)
        .options(joinedload(Message.collection_case))
        .where(Message.merchant_id == merchant_id, Message.status == "pending_approval")
        .order_by(Message.id.desc())
    )
    from app.models import Customer

    out = []
    for m in rows:
        inv = db.get(Invoice, m.invoice_id) if m.invoice_id else None
        cust = db.get(Customer, m.customer_id) if m.customer_id else None
        out.append(
            {
                "id": m.id,
                "invoice_id": inv.invoice_number if inv else None,
                "customer_id": m.customer_id,
                "customer": cust.name if cust else None,
                "language": m.language,
                "tone": m.tone,
                "body": m.body,
                "status": m.status,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
        )
    return out
