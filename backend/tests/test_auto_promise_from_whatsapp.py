from datetime import date, timedelta

from sqlalchemy import select

from app.config import get_settings
from app.database import Base, SessionLocal, engine, init_db
from app.models import CollectionCase, Customer, Invoice, Message, PaymentPromise
from app.services.demo import load_demo_data
from app.services.reply_intent import analyze_debtor_reply, classify_debtor_reply, parse_promise_date
from app.services.whatsapp_mock import simulate_customer_reply


def setup_module(_module=None):
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_parse_relative_promise_dates():
    today = date(2026, 10, 31)
    assert parse_promise_date("I will pay it by tommorow", today=today) == today + timedelta(days=1)
    assert parse_promise_date("Will be paying 2 days later", today=today) == today + timedelta(days=2)
    assert classify_debtor_reply("I have already paid") == "payment_claim"
    a = analyze_debtor_reply("Will be paying 2 days later", use_sarvam=False)
    assert a["intent"] == "promise"
    assert a["promise_date"] is not None


def test_whatsapp_auto_records_promise():
    db = SessionLocal()
    try:
        load_demo_data(db, reset=True)
        mid = get_settings().DEMO_MERCHANT_ID
        inv = db.scalar(select(Invoice).where(Invoice.invoice_number == "R-104"))
        assert inv is not None
        cust = db.get(Customer, inv.customer_id)
        db.add(
            Message(
                merchant_id=mid,
                collection_case_id=inv.collection_case.id if inv.collection_case else None,
                invoice_id=inv.id,
                customer_id=cust.id,
                language="en",
                tone="polite",
                body="Reminder",
                status="sandbox_sent",
                channel="whatsapp_mock",
                is_demo=True,
            )
        )
        db.commit()

        result = simulate_customer_reply(
            db, mid, cust.id, "I will pay it by tomorrow", invoice_id="R-104"
        )
        assert result["ok"] is True
        assert result["intent"] == "promise"
        assert result["promise_recorded"] is True

        case = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == inv.id))
        assert case.status == "promised"
        promises = list(
            db.scalars(select(PaymentPromise).where(PaymentPromise.invoice_id == inv.id))
        )
        assert len(promises) >= 1
        assert promises[-1].promise_date == date.today() + timedelta(days=1)
    finally:
        db.close()
