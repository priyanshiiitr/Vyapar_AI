from datetime import date, timedelta

from app.config import get_settings
from app.database import Base, SessionLocal, engine, init_db
from app.services.demo import load_demo_data
from app.services.ledger_from_extract import create_ledger_invoice_from_fields


def setup_module(_module=None):
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_confirm_extract_creates_overdue():
    db = SessionLocal()
    try:
        load_demo_data(db, reset=True)
        mid = get_settings().DEMO_MERCHANT_ID
        due = (date.today() - timedelta(days=12)).isoformat()
        inv_date = (date.today() - timedelta(days=30)).isoformat()
        result = create_ledger_invoice_from_fields(
            db,
            mid,
            {
                "invoice_id": "SBH/26-27/104",
                "customer_name": "Aarav Sharma - Sharma Electrical Works",
                "customer_phone": "9000000002",
                "amount": "25000",
                "amount_paid": "10000",
                "balance_due": "15000",
                "invoice_date": inv_date,
                "due_date": due,
                "description": "Electrical supplies",
            },
        )
        assert result["ok"] is True
        assert result["outstanding"] == "₹15,000.00"
        assert result["status"] == "partial"
        assert result["overdue"] is True
        assert result["collection_case_id"] is not None

        dup = create_ledger_invoice_from_fields(
            db,
            mid,
            {
                "invoice_id": "SBH/26-27/104",
                "customer_name": "Aarav Sharma - Sharma Electrical Works",
                "amount": "25000",
                "invoice_date": inv_date,
                "due_date": due,
            },
        )
        assert dup["ok"] is False
    finally:
        db.close()
