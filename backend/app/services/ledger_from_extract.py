"""Confirm Document AI (or manual review) fields into the payment ledger."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Customer, Invoice
from app.services.audit import log_audit
from app.services.money import format_inr, parse_amount_to_paise
from app.services.reconciliation import ensure_collection_case, refresh_invoice_status


def _parse_flexible_date(value: str) -> date:
    value = (value or "").strip()
    if not value:
        raise ValueError("Date is required")
    for fmt in (
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d %b %Y",
        "%d-%B-%Y",
        "%d %B %Y",
    ):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")


def _rupees_to_paise(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return parse_amount_to_paise(str(value))


def create_ledger_invoice_from_fields(
    db: Session,
    merchant_id: str,
    fields: dict[str, Any],
    *,
    is_demo: bool = True,
) -> dict[str, Any]:
    invoice_id = (fields.get("invoice_id") or "").strip()
    customer_name = (fields.get("customer_name") or "").strip()
    if not invoice_id:
        return {"ok": False, "error": "invoice_id is required"}
    if not customer_name:
        return {"ok": False, "error": "customer_name is required"}

    amount_raw = fields.get("amount")
    if amount_raw is None or str(amount_raw).strip() == "":
        return {"ok": False, "error": "amount (invoice total) is required"}
    try:
        amount_paise = parse_amount_to_paise(str(amount_raw))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}
    if amount_paise <= 0:
        return {"ok": False, "error": "amount must be positive"}

    paid_paise = 0
    paid_raw = fields.get("amount_paid")
    balance_raw = fields.get("balance_due")
    try:
        if paid_raw is not None and str(paid_raw).strip() != "":
            paid_paise = max(0, _rupees_to_paise(paid_raw) or 0)
        elif balance_raw is not None and str(balance_raw).strip() != "":
            balance_paise = max(0, _rupees_to_paise(balance_raw) or 0)
            paid_paise = max(0, amount_paise - balance_paise)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if paid_paise > amount_paise:
        paid_paise = amount_paise

    try:
        invoice_date = _parse_flexible_date(str(fields.get("invoice_date") or ""))
        due_date = _parse_flexible_date(str(fields.get("due_date") or ""))
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    existing = db.scalar(
        select(Invoice).where(
            Invoice.merchant_id == merchant_id,
            Invoice.invoice_number == invoice_id,
        )
    )
    if existing:
        return {
            "ok": False,
            "error": f"Invoice {invoice_id} already exists in the ledger. Change invoice_id or use a different number.",
            "existing_invoice_id": invoice_id,
        }

    phone = (fields.get("customer_phone") or "").strip() or None
    external_key = f"{customer_name}|{phone or 'nophone'}"
    customer = db.scalar(
        select(Customer).where(
            Customer.merchant_id == merchant_id,
            Customer.external_key == external_key,
        )
    )
    if not customer:
        customer = Customer(
            merchant_id=merchant_id,
            external_key=external_key,
            name=customer_name,
            phone=phone,
            is_demo=is_demo,
        )
        db.add(customer)
        db.flush()

    invoice = Invoice(
        merchant_id=merchant_id,
        customer_id=customer.id,
        invoice_number=invoice_id,
        description=(fields.get("description") or "").strip() or "Imported from Document AI review",
        amount_paise=amount_paise,
        paid_paise=paid_paise,
        invoice_date=invoice_date,
        due_date=due_date,
        status="unpaid",
        is_demo=is_demo,
    )
    refresh_invoice_status(invoice)
    db.add(invoice)
    db.flush()
    case = ensure_collection_case(db, invoice)

    today = date.today()
    days_overdue = (today - due_date).days if invoice.outstanding_paise > 0 else 0
    overdue = days_overdue > 0

    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="invoice",
        entity_id=invoice.id,
        action="doc_ai_confirm_ledger",
        detail=(
            f"{invoice_id} amount={format_inr(amount_paise)} "
            f"paid={format_inr(paid_paise)} outstanding={format_inr(invoice.outstanding_paise)} "
            f"overdue={overdue}"
        ),
        actor="merchant",
    )
    db.commit()
    db.refresh(invoice)

    return {
        "ok": True,
        "invoice_id": invoice.invoice_number,
        "customer": customer.name,
        "customer_id": customer.id,
        "amount": format_inr(invoice.amount_paise),
        "paid": format_inr(invoice.paid_paise),
        "outstanding": format_inr(invoice.outstanding_paise),
        "status": invoice.status,
        "due_date": invoice.due_date.isoformat(),
        "days_overdue": max(0, days_overdue),
        "overdue": overdue,
        "collection_case_id": case.id if case else None,
        "collection_case_status": case.status if case else None,
        "note": (
            "Ledger invoice created from reviewed Document AI fields. "
            + (
                f"Open overdue case ({days_overdue} days)."
                if overdue
                else "Outstanding but not yet overdue."
                if invoice.outstanding_paise > 0
                else "No outstanding balance."
            )
        ),
    }
