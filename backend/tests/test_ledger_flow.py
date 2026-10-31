from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.database import Base, SessionLocal, engine, init_db
from app.main import app
from app.services.demo import load_demo_data, txn_803_csv
from app.services.reconciliation import import_transactions
from app.config import get_settings
from app.models import CollectionCase, FollowUp, Invoice, Message
from sqlalchemy import select


client = TestClient(app)


def setup_module(_module=None):
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_demo_partial_then_full_payment_closes_case():
    db = SessionLocal()
    try:
        result = load_demo_data(db, reset=True)
        assert result["outstanding_paise"] == 3_300_000

        mid = get_settings().DEMO_MERCHANT_ID
        r104 = db.scalar(
            select(Invoice).where(Invoice.merchant_id == mid, Invoice.invoice_number == "R-104")
        )
        assert r104 is not None
        assert r104.outstanding_paise == 1_500_000
        assert r104.status == "partial"

        import_transactions(
            db,
            merchant_id=mid,
            content=txn_803_csv(),
            filename="txn_803.csv",
            is_demo=True,
        )
        db.expire_all()
        r104 = db.scalar(
            select(Invoice).where(Invoice.merchant_id == mid, Invoice.invoice_number == "R-104")
        )
        assert r104.outstanding_paise == 0
        assert r104.status == "paid"
        case = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == r104.id))
        assert case is not None
        assert case.status == "closed"
    finally:
        db.close()


def test_duplicate_transaction_rejected():
    db = SessionLocal()
    try:
        load_demo_data(db, reset=True)
        mid = get_settings().DEMO_MERCHANT_ID
        csv = """transaction_id,reference,amount,transaction_date,customer_name,notes
TXN-801,R-104,10000,2026-10-01,ABC Stores,dup
"""
        res = import_transactions(db, merchant_id=mid, content=csv, filename="dup.csv", is_demo=True)
        assert res["duplicates"] >= 1
    finally:
        db.close()


def test_api_demo_and_dashboard():
    r = client.post("/api/demo/load")
    assert r.status_code == 200
    body = r.json()
    assert body["outstanding_paise"] == 3_300_000
    dash = client.get("/api/dashboard")
    assert dash.status_code == 200
    assert dash.json()["outstanding_paise"] == 3_300_000


def test_reminder_approval_sandbox():
    client.post("/api/demo/load")
    rem = client.post(
        "/api/collections/reminders",
        json={"invoice_id": "R-104", "language": "hinglish", "tone": "polite"},
    )
    assert rem.status_code == 200
    mid = rem.json()["message_id"]
    appr = client.post(f"/api/collections/approvals/{mid}/approve", json={})
    assert appr.status_code == 200
    assert "No external message was sent" in appr.json()["note"]


def test_promise_persists():
    client.post("/api/demo/load")
    friday = (date.today() + timedelta(days=(4 - date.today().weekday()) % 7 or 7)).isoformat()
    res = client.post(
        "/api/collections/promises",
        json={"invoice_id": "R-104", "promise_date": friday, "customer_statement": "Friday"},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    fus = client.get("/api/collections/followups")
    assert any(f["status"] == "pending" for f in fus.json()["followups"])
