"""Demo-only WhatsApp conversation mock — no real WhatsApp API."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import DATA_DIR
from app.models import CollectionCase, Customer, Invoice, Message, PaymentPromise
from app.services.audit import log_audit
from app.services.collections import escalate_case_to_merchant, record_payment_promise
from app.services.money import format_inr
from app.services.reply_intent import analyze_debtor_reply

EVIDENCE_DIR = DATA_DIR / "whatsapp_evidence"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)


def _bubble_time(dt: datetime | None) -> str:
    if not dt:
        return "9:41"
    return dt.strftime("%H:%M")


def list_threads(db: Session, merchant_id: str) -> list[dict]:
    rows = list(
        db.scalars(
            select(Message)
            .where(Message.merchant_id == merchant_id, Message.customer_id.is_not(None))
            .order_by(Message.id.desc())
        )
    )
    by_customer: dict[int, list[Message]] = {}
    for m in rows:
        if m.customer_id is None:
            continue
        by_customer.setdefault(m.customer_id, []).append(m)

    threads = []
    for cid, msgs in by_customer.items():
        customer = db.get(Customer, cid)
        visible = [
            m
            for m in msgs
            if m.status
            in {
                "sandbox_sent",
                "inbound_mock",
                "pending_approval",
                "approved",
                "payment_claim_evidence",
            }
        ]
        if not visible:
            continue
        last = max(visible, key=lambda x: x.id)
        threads.append(
            {
                "customer_id": cid,
                "customer_name": customer.name if customer else f"Customer {cid}",
                "phone": customer.phone if customer else None,
                "message_count": len(visible),
                "last_preview": last.body[:80],
                "last_status": last.status,
                "last_at": last.created_at.isoformat() if last.created_at else None,
            }
        )
    threads.sort(key=lambda t: t["last_at"] or "", reverse=True)
    return threads


def get_thread(db: Session, merchant_id: str, customer_id: int) -> dict:
    customer = db.get(Customer, customer_id)
    if not customer or customer.merchant_id != merchant_id:
        return {"error": "Customer not found", "messages": []}

    rows = list(
        db.scalars(
            select(Message)
            .options(joinedload(Message.collection_case))
            .where(
                Message.merchant_id == merchant_id,
                Message.customer_id == customer_id,
                Message.status.in_(
                    [
                        "sandbox_sent",
                        "inbound_mock",
                        "pending_approval",
                        "approved",
                        "rejected",
                        "payment_claim_evidence",
                    ]
                ),
            )
            .order_by(Message.id.asc())
        )
    )

    bubbles = []
    for m in rows:
        inv = db.get(Invoice, m.invoice_id) if m.invoice_id else None
        if m.status in {"inbound_mock", "payment_claim_evidence"}:
            role = "them"
            label = customer.name
        else:
            role = "me"
            label = "Vyapar AI (merchant)"
        bubbles.append(
            {
                "id": m.id,
                "role": role,
                "label": label,
                "body": m.body,
                "status": m.status,
                "time": _bubble_time(m.created_at),
                "invoice_id": inv.invoice_number if inv else None,
                "outstanding": format_inr(inv.outstanding_paise) if inv else None,
                "sandbox_note": m.sandbox_note,
                "evidence_file": (
                    m.sandbox_note.replace("evidence_file:", "", 1)
                    if m.sandbox_note and m.sandbox_note.startswith("evidence_file:")
                    else None
                ),
                "ticks": "read" if m.status == "sandbox_sent" else ("sent" if role == "me" else None),
            }
        )

    case_status = None
    open_escalation = None
    if bubbles:
        last_inv_id = None
        for b in reversed(bubbles):
            if b.get("invoice_id"):
                last_inv_id = b["invoice_id"]
                break
        if last_inv_id:
            inv_row = db.scalar(
                select(Invoice).where(
                    Invoice.merchant_id == merchant_id, Invoice.invoice_number == last_inv_id
                )
            )
            if inv_row and inv_row.collection_case:
                case_status = inv_row.collection_case.status
    alert = db.scalar(
        select(Message)
        .where(
            Message.merchant_id == merchant_id,
            Message.customer_id == customer_id,
            Message.status == "merchant_escalation",
        )
        .order_by(Message.id.desc())
        .limit(1)
    )
    if alert:
        open_escalation = {
            "id": alert.id,
            "body": alert.body,
            "created_at": alert.created_at.isoformat() if alert.created_at else None,
        }

    status_line = "online · sandbox demo"
    if case_status == "promised":
        status_line = "promised · follow-up scheduled · sandbox demo"
    elif case_status in {"escalated", "disputed"}:
        status_line = f"{case_status} · needs merchant · sandbox demo"

    return {
        "customer_id": customer_id,
        "customer_name": customer.name,
        "phone": customer.phone,
        "status_line": status_line,
        "case_status": case_status,
        "merchant_escalation": open_escalation,
        "messages": bubbles,
        "disclaimer": (
            "Mock WhatsApp only. Promises auto-record from chat. "
            "'I paid' needs ledger/CSV match — screenshot is evidence for merchant review, not payment truth."
        ),
    }


def simulate_customer_reply(
    db: Session,
    merchant_id: str,
    customer_id: int,
    body: str,
    invoice_id: str | None = None,
) -> dict:
    customer = db.get(Customer, customer_id)
    if not customer or customer.merchant_id != merchant_id:
        return {"error": "Customer not found"}

    inv = None
    if invoice_id:
        inv = db.scalar(
            select(Invoice).where(Invoice.merchant_id == merchant_id, Invoice.invoice_number == invoice_id)
        )
    if inv is None:
        last = db.scalar(
            select(Message)
            .where(
                Message.merchant_id == merchant_id,
                Message.customer_id == customer_id,
                Message.invoice_id.is_not(None),
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
        if last:
            inv = db.get(Invoice, last.invoice_id)

    analysis = analyze_debtor_reply(body, use_sarvam=True)
    intent = analysis["intent"]
    case_id = None
    if inv:
        case = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == inv.id))
        case_id = case.id if case else None

    msg = Message(
        merchant_id=merchant_id,
        collection_case_id=case_id,
        invoice_id=inv.id if inv else None,
        customer_id=customer_id,
        language="hinglish",
        tone="customer_reply",
        body=body.strip(),
        status="inbound_mock",
        channel="whatsapp_mock",
        sandbox_note=(
            f"Simulated reply; intent={intent}; source={analysis.get('source')}; "
            f"promise_date={analysis.get('promise_date')}"
        ),
        is_demo=True,
    )
    db.add(msg)
    db.flush()
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="message",
        entity_id=customer_id,
        action="whatsapp_mock_reply",
        detail=f"{customer.name} intent={intent} src={analysis.get('source')}: {body[:160]}",
        actor="demo",
    )

    escalation = None
    promise = None

    if inv and intent in {"refusal", "dispute", "payment_claim"}:
        escalation = escalate_case_to_merchant(
            db,
            merchant_id=merchant_id,
            invoice=inv,
            customer_name=customer.name,
            customer_reply=body,
            intent=intent,
            source_message_id=msg.id,
        )

    if inv and intent == "promise":
        promise_date_s = analysis.get("promise_date")
        promise_date = date.fromisoformat(promise_date_s) if promise_date_s else date.today()
        promise = record_payment_promise(
            db,
            merchant_id=merchant_id,
            invoice_id=inv.invoice_number,
            promise_date=promise_date,
            customer_statement=body.strip(),
        )
        if promise.get("ok"):
            log_audit(
                db,
                merchant_id=merchant_id,
                entity_type="promise",
                entity_id=promise.get("promise_id") or inv.invoice_number,
                action="whatsapp_auto_promise",
                detail=(
                    f"Auto-recorded from WhatsApp for {inv.invoice_number} "
                    f"on {promise_date.isoformat()} via {analysis.get('source')}"
                ),
                actor="system",
            )
            db.commit()
        else:
            # Keep the chat bubble even if promise could not be created (e.g. already paid)
            db.commit()

    if not (inv and intent == "promise"):
        db.commit()
    elif promise is None:
        db.commit()

    db.refresh(msg)
    thread = get_thread(db, merchant_id, customer_id)
    thread["intent"] = intent
    thread["analysis"] = analysis

    if escalation and escalation.get("ok"):
        thread["escalation"] = escalation
        if intent == "payment_claim":
            thread["status_line"] = "payment claimed · await ledger evidence · sandbox"
            thread["hint"] = (
                "Customer says they paid. Upload a screenshot here for merchant review, "
                "then match a bank txn/CSV on Reconciliation — chat alone never marks paid."
            )
        else:
            thread["status_line"] = "escalated to merchant · sandbox demo"
    elif promise and promise.get("ok"):
        thread["promise"] = promise
        thread["status_line"] = "promised · auto-recorded · sandbox demo"
        thread["hint"] = (
            f"Payment promise auto-recorded for {promise.get('promise_date')} "
            f"({format_inr(inv.outstanding_paise) if inv else ''}). Follow-up scheduled. Not marked paid."
        )

    return {
        "ok": True,
        "message_id": msg.id,
        "intent": intent,
        "analysis": analysis,
        "escalated": bool(escalation and escalation.get("ok")),
        "escalation": escalation,
        "promise_recorded": bool(promise and promise.get("ok")),
        "promise": promise,
        "thread": thread,
    }


def attach_payment_evidence(
    db: Session,
    *,
    merchant_id: str,
    customer_id: int,
    filename: str,
    content: bytes,
    note: str = "",
    invoice_id: str | None = None,
) -> dict:
    """Store screenshot/proof in chat as evidence — never marks invoice paid."""
    customer = db.get(Customer, customer_id)
    if not customer or customer.merchant_id != merchant_id:
        return {"ok": False, "error": "Customer not found"}
    if not content:
        return {"ok": False, "error": "Empty file"}
    if len(content) > 8_000_000:
        return {"ok": False, "error": "File too large (max ~8MB)"}

    inv = None
    if invoice_id:
        inv = db.scalar(
            select(Invoice).where(Invoice.merchant_id == merchant_id, Invoice.invoice_number == invoice_id)
        )
    if inv is None:
        last = db.scalar(
            select(Message)
            .where(
                Message.merchant_id == merchant_id,
                Message.customer_id == customer_id,
                Message.invoice_id.is_not(None),
            )
            .order_by(Message.id.desc())
            .limit(1)
        )
        if last:
            inv = db.get(Invoice, last.invoice_id)
    if not inv:
        return {"ok": False, "error": "No invoice linked to this chat"}

    safe_name = Path(filename).name.replace(" ", "_")
    stamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    dest = EVIDENCE_DIR / f"{merchant_id}_{inv.invoice_number}_{stamp}_{safe_name}"
    dest.write_bytes(content)

    case = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == inv.id))
    if case and case.status not in {"closed"}:
        case.status = "escalated"

    body = (
        f"[Payment proof attached by {customer.name}]\n"
        f"Chat customer: {customer.name}\n"
        f"Invoice: {inv.invoice_number}\n"
        f"Outstanding: {format_inr(inv.outstanding_paise)}\n"
        f"File: {safe_name}\n"
        f"{note.strip() or 'Customer uploaded payment screenshot / receipt.'}\n"
        f"(Evidence only — ledger unpaid until matched bank CSV/txn. "
        f"Uploader name always comes from this WhatsApp chat, not the filename.)"
    )
    msg = Message(
        merchant_id=merchant_id,
        collection_case_id=case.id if case else None,
        invoice_id=inv.id,
        customer_id=customer_id,
        language="en",
        tone="payment_evidence",
        body=body,
        status="payment_claim_evidence",
        channel="whatsapp_mock",
        sandbox_note=f"evidence_file:{dest.name}",
        is_demo=True,
    )
    db.add(msg)
    escalate_case_to_merchant(
        db,
        merchant_id=merchant_id,
        invoice=inv,
        customer_name=customer.name,
        customer_reply=(
            f"[{customer.name} via WhatsApp] Uploaded payment proof for "
            f"{inv.invoice_number}: {safe_name}. {note}"
        ).strip(),
        intent="payment_claim",
        source_message_id=None,
    )
    db.commit()
    db.refresh(msg)
    return {
        "ok": True,
        "message_id": msg.id,
        "customer_id": customer_id,
        "customer_name": customer.name,
        "filename": safe_name,
        "invoice_id": inv.invoice_number,
        "outstanding": format_inr(inv.outstanding_paise),
        "note": "Evidence saved for merchant review. Invoice NOT marked paid.",
        "thread": get_thread(db, merchant_id, customer_id),
    }


def list_payment_evidence(db: Session, merchant_id: str) -> list[dict]:
    """WhatsApp-uploaded proofs — customer name always from the chat customer_id."""
    rows = list(
        db.scalars(
            select(Message)
            .where(
                Message.merchant_id == merchant_id,
                Message.status == "payment_claim_evidence",
            )
            .order_by(Message.id.desc())
            .limit(50)
        )
    )
    out = []
    for m in rows:
        customer = db.get(Customer, m.customer_id) if m.customer_id else None
        inv = db.get(Invoice, m.invoice_id) if m.invoice_id else None
        evidence_name = None
        if m.sandbox_note and m.sandbox_note.startswith("evidence_file:"):
            evidence_name = m.sandbox_note.replace("evidence_file:", "", 1)
        out.append(
            {
                "id": m.id,
                "customer_id": m.customer_id,
                "customer_name": customer.name if customer else "Unknown chat customer",
                "invoice_id": inv.invoice_number if inv else None,
                "outstanding": format_inr(inv.outstanding_paise) if inv else None,
                "invoice_status": inv.status if inv else None,
                "filename": evidence_name,
                "body": m.body,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "download_path": f"/api/whatsapp/evidence-file/{m.id}" if evidence_name else None,
                "whatsapp_path": f"/whatsapp?customer={m.customer_id}" if m.customer_id else None,
                "suggested_txn_hint": (
                    f"Import a bank CSV with reference={inv.invoice_number} and "
                    f"customer_name={customer.name} amount matching outstanding"
                    if inv and customer
                    else None
                ),
            }
        )
    return out


def sync_promises_from_chat(db: Session, merchant_id: str) -> dict:
    """
    Backfill payment promises from inbound WhatsApp mock replies.
    Fixes chats recorded before auto-promise landed (or if recording failed).
    """
    rows = list(
        db.scalars(
            select(Message)
            .where(
                Message.merchant_id == merchant_id,
                Message.status == "inbound_mock",
                Message.invoice_id.is_not(None),
            )
            .order_by(Message.id.asc())
        )
    )
    created = []
    skipped = []
    for msg in rows:
        analysis = analyze_debtor_reply(msg.body, use_sarvam=False)
        if analysis["intent"] != "promise":
            continue
        inv = db.get(Invoice, msg.invoice_id)
        if not inv or inv.outstanding_paise <= 0:
            skipped.append({"message_id": msg.id, "reason": "no_outstanding"})
            continue
        # Skip if an active promise already exists for this invoice with same/similar statement
        existing = list(
            db.scalars(
                select(PaymentPromise).where(
                    PaymentPromise.merchant_id == merchant_id,
                    PaymentPromise.invoice_id == inv.id,
                    PaymentPromise.status == "active",
                )
            )
        )
        if any(
            (p.customer_statement or "").strip().lower() == msg.body.strip().lower() for p in existing
        ):
            skipped.append({"message_id": msg.id, "reason": "already_recorded"})
            continue
        if existing:
            # Already have an active promise for this invoice from another path
            skipped.append({"message_id": msg.id, "reason": "active_promise_exists"})
            continue

        promise_date_s = analysis.get("promise_date")
        promise_date = date.fromisoformat(promise_date_s) if promise_date_s else date.today()
        result = record_payment_promise(
            db,
            merchant_id=merchant_id,
            invoice_id=inv.invoice_number,
            promise_date=promise_date,
            customer_statement=msg.body.strip(),
        )
        if result.get("ok"):
            msg.sandbox_note = (
                f"Simulated reply; intent=promise; source=backfill; "
                f"promise_date={promise_date.isoformat()}; promise_id={result.get('promise_id')}"
            )
            db.commit()
            created.append(
                {
                    "message_id": msg.id,
                    "invoice_id": inv.invoice_number,
                    "promise_id": result.get("promise_id"),
                    "promise_date": promise_date.isoformat(),
                }
            )
        else:
            skipped.append({"message_id": msg.id, "reason": result.get("error")})

    return {"ok": True, "created": created, "skipped": skipped, "created_count": len(created)}


SEED_REPLIES = [
    "I will pay it by tomorrow",
    "Will be paying 2 days later",
    "Haan bhai, Friday tak clear kar dunga. UPI se bhej dunga.",
    "I have already paid, sending screenshot",
    "Okay I cannot pay it",
]
