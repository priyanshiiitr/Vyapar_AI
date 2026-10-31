from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import (
    AuditLog,
    ChatMessage,
    CollectionCase,
    Conversation,
    Customer,
    FollowUp,
    Invoice,
    Merchant,
    Message,
    PaymentPromise,
    Transaction,
    TransactionMatch,
    UploadBatch,
)
from app.services.audit import log_audit
from app.services.reconciliation import ensure_collection_case, match_transaction, refresh_invoice_status


def reset_demo_data(db: Session) -> None:
    """
    Hard-reset everything for the demo merchant.

    Important: after a full demo, CSV uploads (e.g. TXN-R106-CLEAR) are often
    is_demo=False. Old reset only deleted is_demo=True rows, left TransactionMatch
    rows pointing at demo invoices, then DELETE invoices → FK error → Internal Server Error.
    """
    settings = get_settings()
    mid = settings.DEMO_MERCHANT_ID

    invoice_ids = [i.id for i in db.scalars(select(Invoice).where(Invoice.merchant_id == mid))]
    txn_ids = [t.id for t in db.scalars(select(Transaction).where(Transaction.merchant_id == mid))]
    case_ids = [
        c.id for c in db.scalars(select(CollectionCase).where(CollectionCase.merchant_id == mid))
    ]

    # FK-safe wipe (matches → messages/promises/followups → cases/txns → invoices → customers)
    if txn_ids:
        db.execute(delete(TransactionMatch).where(TransactionMatch.transaction_id.in_(txn_ids)))
    if invoice_ids:
        db.execute(delete(TransactionMatch).where(TransactionMatch.invoice_id.in_(invoice_ids)))

    db.execute(delete(Message).where(Message.merchant_id == mid))
    if case_ids:
        db.execute(delete(FollowUp).where(FollowUp.collection_case_id.in_(case_ids)))
        db.execute(delete(PaymentPromise).where(PaymentPromise.collection_case_id.in_(case_ids)))
        db.execute(delete(CollectionCase).where(CollectionCase.id.in_(case_ids)))
    if txn_ids:
        db.execute(delete(Transaction).where(Transaction.id.in_(txn_ids)))
    if invoice_ids:
        db.execute(delete(Invoice).where(Invoice.id.in_(invoice_ids)))

    db.execute(delete(Customer).where(Customer.merchant_id == mid))
    db.execute(delete(UploadBatch).where(UploadBatch.merchant_id == mid))
    db.execute(delete(AuditLog).where(AuditLog.merchant_id == mid))

    conv_ids = [
        c.id for c in db.scalars(select(Conversation).where(Conversation.merchant_id == mid))
    ]
    if conv_ids:
        db.execute(delete(ChatMessage).where(ChatMessage.conversation_id.in_(conv_ids)))
        db.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
    db.commit()


def load_demo_data(db: Session, *, reset: bool = True) -> dict:
    settings = get_settings()
    mid = settings.DEMO_MERCHANT_ID
    if reset:
        reset_demo_data(db)

    merchant = db.get(Merchant, mid)
    if not merchant:
        merchant = Merchant(id=mid, name="Demo Kirana Merchant", is_demo=True)
        db.add(merchant)
        db.flush()

    today = date.today()

    customers = {
        "ABC Stores": Customer(
            merchant_id=mid,
            external_key="ABC Stores|9999900001",
            name="ABC Stores",
            phone="9999900001",
            is_demo=True,
        ),
        "XYZ Traders": Customer(
            merchant_id=mid,
            external_key="XYZ Traders|9999900002",
            name="XYZ Traders",
            phone="9999900002",
            is_demo=True,
        ),
        "Kumar Mart": Customer(
            merchant_id=mid,
            external_key="Kumar Mart|9999900003",
            name="Kumar Mart",
            phone="9999900003",
            is_demo=True,
        ),
    }
    for c in customers.values():
        db.add(c)
    db.flush()

    invoices = [
        Invoice(
            merchant_id=mid,
            customer_id=customers["ABC Stores"].id,
            invoice_number="R-104",
            description="Wholesale grocery stock",
            amount_paise=2_500_000,
            paid_paise=0,
            invoice_date=today - timedelta(days=20),
            due_date=today - timedelta(days=12),
            status="unpaid",
            is_demo=True,
        ),
        Invoice(
            merchant_id=mid,
            customer_id=customers["XYZ Traders"].id,
            invoice_number="R-105",
            description="Festival order",
            amount_paise=4_000_000,
            paid_paise=0,
            invoice_date=today - timedelta(days=15),
            due_date=today - timedelta(days=5),
            status="unpaid",
            is_demo=True,
        ),
        Invoice(
            merchant_id=mid,
            customer_id=customers["Kumar Mart"].id,
            invoice_number="R-106",
            description="Monthly supplies",
            amount_paise=1_800_000,
            paid_paise=0,
            invoice_date=today - timedelta(days=10),
            due_date=today - timedelta(days=2),
            status="unpaid",
            is_demo=True,
        ),
    ]
    for inv in invoices:
        db.add(inv)
    db.flush()

    for inv in invoices:
        ensure_collection_case(db, inv)

    txns = [
        Transaction(
            merchant_id=mid,
            transaction_id="TXN-801",
            reference="R-104",
            amount_paise=1_000_000,
            transaction_date=today - timedelta(days=3),
            customer_name="ABC Stores",
            notes="Partial UPI",
            status="unmatched",
            evidence_source="csv_import",
            is_demo=True,
        ),
        Transaction(
            merchant_id=mid,
            transaction_id="TXN-802",
            reference="R-105",
            amount_paise=4_000_000,
            transaction_date=today - timedelta(days=2),
            customer_name="XYZ Traders",
            notes="Full payment",
            status="unmatched",
            evidence_source="csv_import",
            is_demo=True,
        ),
    ]
    for t in txns:
        db.add(t)
    db.flush()

    for t in txns:
        match_transaction(db, mid, t)

    db.flush()
    for inv in invoices:
        refresh_invoice_status(inv)
        ensure_collection_case(db, inv)

    log_audit(
        db,
        merchant_id=mid,
        entity_type="demo",
        entity_id=mid,
        action="load_demo_data",
        detail="Seeded R-104/105/106 and TXN-801/802",
        actor="merchant",
    )
    db.commit()

    outstanding = sum(i.outstanding_paise for i in invoices)
    return {
        "merchant_id": mid,
        "invoices": 3,
        "outstanding_paise": outstanding,
        "outstanding_display": "₹33,000.00" if outstanding == 3_300_000 else outstanding,
        "paid": sum(1 for i in invoices if i.status == "paid"),
        "partial": sum(1 for i in invoices if i.status == "partial"),
        "unpaid": sum(1 for i in invoices if i.status == "unpaid"),
    }


TXN_803_CSV = """transaction_id,reference,amount,transaction_date,customer_name,notes
TXN-803,R-104,15000,{today},ABC Stores,Remaining balance
""".strip()


def txn_803_csv() -> str:
    return TXN_803_CSV.format(today=date.today().isoformat())
