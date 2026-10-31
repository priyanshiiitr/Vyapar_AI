from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models import (
    CollectionCase,
    FollowUp,
    Invoice,
    Message,
    Transaction,
    TransactionMatch,
    UploadBatch,
)
from app.services.audit import log_audit
from app.services.money import parse_amount_to_paise


INVOICE_REQUIRED = [
    "invoice_id",
    "customer_name",
    "customer_phone",
    "amount",
    "invoice_date",
    "due_date",
    "description",
]
TXN_REQUIRED = [
    "transaction_id",
    "reference",
    "amount",
    "transaction_date",
    "customer_name",
    "notes",
]


def _parse_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Invalid date: {value}")


def preview_csv(content: str, kind: str) -> dict[str, Any]:
    required = INVOICE_REQUIRED if kind == "invoices" else TXN_REQUIRED
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        return {"ok": False, "errors": ["CSV has no header row"], "rows": [], "columns": []}
    columns = [c.strip() for c in reader.fieldnames]
    missing = [c for c in required if c not in columns]
    rows = []
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        clean = {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items() if k}
        rows.append(clean)
        if i > 52:
            break
    if missing:
        errors.append(f"Missing columns: {', '.join(missing)}")
    return {
        "ok": not missing,
        "errors": errors,
        "columns": columns,
        "required": required,
        "preview_rows": rows[:50],
        "row_count_preview": len(rows),
    }


def refresh_invoice_status(invoice: Invoice) -> None:
    if invoice.paid_paise <= 0:
        invoice.status = "unpaid"
    elif invoice.paid_paise >= invoice.amount_paise:
        invoice.status = "paid"
        invoice.paid_paise = invoice.amount_paise  # clamp overpay allocation already reviewed
    else:
        invoice.status = "partial"


def ensure_collection_case(db: Session, invoice: Invoice) -> CollectionCase | None:
    existing = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == invoice.id))
    outstanding = invoice.outstanding_paise
    if outstanding <= 0:
        if existing and existing.status != "closed":
            existing.status = "closed"
            existing.outstanding_paise = 0
            existing.closed_at = datetime.utcnow()
            existing.close_reason = "ledger_zero_outstanding"
            cancel_pending_for_invoice(db, invoice)
        return existing

    if existing is None:
        case = CollectionCase(
            merchant_id=invoice.merchant_id,
            invoice_id=invoice.id,
            customer_id=invoice.customer_id,
            status="open",
            outstanding_paise=outstanding,
            is_demo=invoice.is_demo,
        )
        db.add(case)
        db.flush()
        return case

    if existing.status == "closed":
        existing.status = "open"
        existing.closed_at = None
        existing.close_reason = None
    existing.outstanding_paise = outstanding
    return existing


def cancel_pending_for_invoice(db: Session, invoice: Invoice) -> None:
    case = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == invoice.id))
    if not case:
        return
    for msg in db.scalars(
        select(Message).where(
            Message.collection_case_id == case.id,
            Message.status.in_(["draft", "pending_approval"]),
        )
    ):
        msg.status = "cancelled"
    for fu in db.scalars(
        select(FollowUp).where(
            FollowUp.collection_case_id == case.id,
            FollowUp.status == "pending",
        )
    ):
        fu.status = "cancelled"
        fu.skip_reason = "invoice_paid_or_closed"
        fu.processed_at = datetime.utcnow()
    for promise in case.promises:
        if promise.status == "active":
            promise.status = "fulfilled" if invoice.outstanding_paise == 0 else "cancelled"


def import_invoices(
    db: Session,
    *,
    merchant_id: str,
    content: str,
    filename: str,
    is_demo: bool = False,
) -> dict[str, Any]:
    from app.models import Customer

    preview = preview_csv(content, "invoices")
    if not preview["ok"]:
        return {"ok": False, "errors": preview["errors"]}

    batch = UploadBatch(
        merchant_id=merchant_id, kind="invoices", filename=filename, row_count=0
    )
    db.add(batch)
    db.flush()

    reader = csv.DictReader(io.StringIO(content))
    created = 0
    skipped = 0
    errors: list[str] = []
    for i, row in enumerate(reader, start=2):
        try:
            inv_no = row["invoice_id"].strip()
            exists = db.scalar(
                select(Invoice).where(
                    Invoice.merchant_id == merchant_id, Invoice.invoice_number == inv_no
                )
            )
            if exists:
                skipped += 1
                continue
            name = row["customer_name"].strip()
            phone = (row.get("customer_phone") or "").strip() or None
            external_key = f"{name}|{phone or 'nophone'}"
            customer = db.scalar(
                select(Customer).where(
                    Customer.merchant_id == merchant_id, Customer.external_key == external_key
                )
            )
            if not customer:
                customer = Customer(
                    merchant_id=merchant_id,
                    external_key=external_key,
                    name=name,
                    phone=phone,
                    is_demo=is_demo,
                )
                db.add(customer)
                db.flush()
            amount_paise = parse_amount_to_paise(row["amount"])
            invoice = Invoice(
                merchant_id=merchant_id,
                customer_id=customer.id,
                invoice_number=inv_no,
                description=(row.get("description") or "").strip() or None,
                amount_paise=amount_paise,
                paid_paise=0,
                invoice_date=_parse_date(row["invoice_date"]),
                due_date=_parse_date(row["due_date"]),
                status="unpaid",
                is_demo=is_demo,
            )
            db.add(invoice)
            db.flush()
            ensure_collection_case(db, invoice)
            created += 1
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {i}: {exc}")
    batch.row_count = created
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="upload",
        entity_id=batch.id,
        action="import_invoices",
        detail=f"created={created} skipped={skipped} file={filename}",
    )
    db.commit()
    return {"ok": True, "created": created, "skipped": skipped, "errors": errors, "batch_id": batch.id}


def _open_invoices(db: Session, merchant_id: str) -> list[Invoice]:
    return list(
        db.scalars(
            select(Invoice)
            .options(joinedload(Invoice.customer))
            .where(Invoice.merchant_id == merchant_id, Invoice.status != "paid")
        ).unique()
    )


def _apply_match(
    db: Session,
    *,
    merchant_id: str,
    txn: Transaction,
    invoice: Invoice,
    match_reason: str,
    confidence: str = "high",
    auto_accepted: bool = True,
) -> dict[str, Any]:
    allocate = min(txn.amount_paise, invoice.outstanding_paise)
    overpay = txn.amount_paise > invoice.outstanding_paise
    if overpay and invoice.outstanding_paise == 0:
        txn.status = "overpayment"
        log_audit(
            db,
            merchant_id=merchant_id,
            entity_type="transaction",
            entity_id=txn.id,
            action="overpayment_review",
            detail=f"{txn.transaction_id} vs {invoice.invoice_number}",
        )
        return {"status": "overpayment", "invoice": invoice.invoice_number}

    match = TransactionMatch(
        merchant_id=merchant_id,
        transaction_id=txn.id,
        invoice_id=invoice.id,
        allocated_paise=allocate,
        confidence=confidence,
        match_reason=match_reason,
        auto_accepted=auto_accepted,
    )
    db.add(match)
    invoice.paid_paise += allocate
    refresh_invoice_status(invoice)
    txn.status = "matched"
    db.flush()
    ensure_collection_case(db, invoice)
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="transaction",
        entity_id=txn.id,
        action="auto_matched",
        detail=f"{txn.transaction_id} -> {invoice.invoice_number} allocated={allocate} reason={match_reason}",
    )
    if invoice.outstanding_paise == 0:
        log_audit(
            db,
            merchant_id=merchant_id,
            entity_type="invoice",
            entity_id=invoice.invoice_number,
            action="case_closed_ledger",
            detail="outstanding reached zero via verified CSV evidence",
        )
    return {
        "status": "matched",
        "invoice": invoice.invoice_number,
        "allocated_paise": allocate,
        "outstanding_paise": invoice.outstanding_paise,
        "overpayment": overpay,
        "match_reason": match_reason,
        "confidence": confidence,
    }


def match_transaction(db: Session, merchant_id: str, txn: Transaction) -> dict[str, Any]:
    from app.services.matching import select_fuzzy_auto_match

    if txn.status == "matched":
        return {"status": "already_matched", "transaction_id": txn.transaction_id}

    invoices = _open_invoices(db, merchant_id)
    ref = (txn.reference or "").strip()

    # 1) Exact unique invoice reference → auto-match
    if ref:
        exact = [i for i in invoices if i.invoice_number.lower() == ref.lower()]
        if len(exact) == 1:
            return _apply_match(
                db,
                merchant_id=merchant_id,
                txn=txn,
                invoice=exact[0],
                match_reason="exact_invoice_reference",
            )
        if len(exact) > 1:
            txn.status = "ambiguous"
            return {
                "status": "ambiguous",
                "reason": "duplicate_invoice_numbers",
                "candidates": [i.invoice_number for i in exact],
            }

    # 2) Exact customer name (case-insensitive)
    name = (txn.customer_name or "").strip()
    if name:
        exact_name = [i for i in invoices if i.customer and i.customer.name.lower() == name.lower()]
        if len(exact_name) == 1:
            return _apply_match(
                db,
                merchant_id=merchant_id,
                txn=txn,
                invoice=exact_name[0],
                match_reason="exact_customer_name",
            )
        if len(exact_name) > 1:
            txn.status = "ambiguous"
            log_audit(
                db,
                merchant_id=merchant_id,
                entity_type="transaction",
                entity_id=txn.id,
                action="ambiguous_match",
                detail=f"exact_name_candidates={[c.invoice_number for c in exact_name]}",
            )
            return {
                "status": "ambiguous",
                "reason": "multiple_exact_customer_name",
                "candidates": [c.invoice_number for c in exact_name],
            }

        # 3) RapidFuzz fuzzy name — auto only if high unique score + exact amount
        winner, ranked, reason = select_fuzzy_auto_match(
            txn_customer_name=name,
            txn_amount_paise=txn.amount_paise,
            invoices=invoices,
        )
        top = [
            {
                "invoice": c.invoice_number,
                "customer": c.customer_name,
                "score": round(c.score, 1),
            }
            for c in ranked[:5]
        ]
        if winner is not None:
            invoice = next(i for i in invoices if i.id == winner.invoice_id)
            result = _apply_match(
                db,
                merchant_id=merchant_id,
                txn=txn,
                invoice=invoice,
                match_reason=f"rapidfuzz_name:{winner.score:.1f}",
                confidence="high",
            )
            result["fuzzy_scores"] = top
            return result

        if ranked and ranked[0].score >= 60:
            txn.status = "ambiguous"
            log_audit(
                db,
                merchant_id=merchant_id,
                entity_type="transaction",
                entity_id=txn.id,
                action="ambiguous_match",
                detail=f"fuzzy_review reason={reason} top={top}",
            )
            return {
                "status": "ambiguous",
                "reason": reason,
                "candidates": [c["invoice"] for c in top],
                "fuzzy_scores": top,
            }

    txn.status = "unmatched"
    return {"status": "unmatched"}



def import_transactions(
    db: Session,
    *,
    merchant_id: str,
    content: str,
    filename: str,
    is_demo: bool = False,
    auto_reconcile: bool = True,
) -> dict[str, Any]:
    preview = preview_csv(content, "transactions")
    if not preview["ok"]:
        return {"ok": False, "errors": preview["errors"]}

    batch = UploadBatch(
        merchant_id=merchant_id, kind="transactions", filename=filename, row_count=0
    )
    db.add(batch)
    db.flush()

    reader = csv.DictReader(io.StringIO(content))
    created = 0
    duplicates = 0
    errors: list[str] = []
    results: list[dict[str, Any]] = []
    for i, row in enumerate(reader, start=2):
        try:
            txn_id = row["transaction_id"].strip()
            exists = db.scalar(
                select(Transaction).where(
                    Transaction.merchant_id == merchant_id,
                    Transaction.transaction_id == txn_id,
                )
            )
            if exists:
                duplicates += 1
                errors.append(f"Row {i}: duplicate transaction_id {txn_id}")
                continue
            txn = Transaction(
                merchant_id=merchant_id,
                transaction_id=txn_id,
                reference=(row.get("reference") or "").strip() or None,
                amount_paise=parse_amount_to_paise(row["amount"]),
                transaction_date=_parse_date(row["transaction_date"]),
                customer_name=(row.get("customer_name") or "").strip() or None,
                notes=(row.get("notes") or "").strip() or None,
                status="unmatched",
                evidence_source="csv_import",
                upload_batch_id=batch.id,
                is_demo=is_demo,
            )
            db.add(txn)
            db.flush()
            created += 1
            if auto_reconcile:
                results.append(match_transaction(db, merchant_id, txn))
        except Exception as exc:  # noqa: BLE001
            errors.append(f"Row {i}: {exc}")

    batch.row_count = created
    log_audit(
        db,
        merchant_id=merchant_id,
        entity_type="upload",
        entity_id=batch.id,
        action="import_transactions",
        detail=f"created={created} duplicates={duplicates} file={filename}",
    )
    db.commit()
    return {
        "ok": True,
        "created": created,
        "duplicates": duplicates,
        "errors": errors,
        "match_results": results,
        "batch_id": batch.id,
    }


def run_reconciliation(db: Session, merchant_id: str) -> dict[str, Any]:
    open_txns = list(
        db.scalars(
            select(Transaction).where(
                Transaction.merchant_id == merchant_id,
                Transaction.status.in_(["unmatched", "ambiguous"]),
            )
        )
    )
    results = [match_transaction(db, merchant_id, t) for t in open_txns]
    db.commit()
    return {"processed": len(results), "results": results}
