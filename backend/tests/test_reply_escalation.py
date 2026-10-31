from app.config import get_settings
from app.database import Base, SessionLocal, engine, init_db
from app.models import CollectionCase, Message
from app.services.demo import load_demo_data
from app.services.reply_intent import classify_debtor_reply
from app.services.whatsapp_mock import simulate_customer_reply
from sqlalchemy import select


def setup_module(_module=None):
    Base.metadata.drop_all(bind=engine)
    init_db()


def test_classify_cannot_pay():
    assert classify_debtor_reply("Okay I cannot paay it") == "refusal"
    assert classify_debtor_reply("Haan bhai, Friday tak clear kar dunga") == "promise"
    assert classify_debtor_reply("This is a wrong invoice") == "dispute"


def test_refusal_escalates_to_merchant():
    db = SessionLocal()
    try:
        load_demo_data(db, reset=True)
        mid = get_settings().DEMO_MERCHANT_ID
        # Use ABC Stores from demo (customer on R-104)
        from app.models import Customer, Invoice

        inv = db.scalar(select(Invoice).where(Invoice.invoice_number == "R-104"))
        assert inv is not None
        cust = db.get(Customer, inv.customer_id)
        assert cust is not None

        # Seed an outbound sandbox message so reply attaches to invoice
        db.add(
            Message(
                merchant_id=mid,
                collection_case_id=inv.collection_case.id if inv.collection_case else None,
                invoice_id=inv.id,
                customer_id=cust.id,
                language="hinglish",
                tone="polite",
                body="Reminder for R-104",
                status="sandbox_sent",
                channel="whatsapp_mock",
                is_demo=True,
            )
        )
        db.commit()

        result = simulate_customer_reply(
            db, mid, cust.id, "Okay I cannot paay it", invoice_id="R-104"
        )
        assert result["ok"] is True
        assert result["intent"] == "refusal"
        assert result["escalated"] is True

        case = db.scalar(select(CollectionCase).where(CollectionCase.invoice_id == inv.id))
        assert case is not None
        assert case.status == "escalated"

        alert = db.scalar(
            select(Message).where(
                Message.merchant_id == mid, Message.status == "merchant_escalation"
            )
        )
        assert alert is not None
        assert "ESCALATION" in alert.body
    finally:
        db.close()
