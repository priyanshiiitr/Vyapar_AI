"""WhatsApp-style sandbox mock for demo reminders — no real WhatsApp."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Message
from app.services import whatsapp_mock as wa

router = APIRouter(prefix="/whatsapp")


class SimulateReplyRequest(BaseModel):
    customer_id: int
    body: str = Field(min_length=1, max_length=2000)
    invoice_id: str | None = None


@router.get("/threads")
def threads(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return {"threads": wa.list_threads(db, mid), "disclaimer": "Mock WhatsApp only"}


@router.get("/threads/{customer_id}")
def thread(customer_id: int, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return wa.get_thread(db, mid, customer_id)


@router.post("/simulate-reply")
def simulate_reply(payload: SimulateReplyRequest, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return wa.simulate_customer_reply(
        db,
        mid,
        payload.customer_id,
        payload.body,
        payload.invoice_id,
    )


@router.post("/upload-evidence")
async def upload_evidence(
    customer_id: int = Form(...),
    note: str = Form(""),
    invoice_id: str | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    mid = get_settings().DEMO_MERCHANT_ID
    content = await file.read()
    return wa.attach_payment_evidence(
        db,
        merchant_id=mid,
        customer_id=customer_id,
        filename=file.filename or "proof.bin",
        content=content,
        note=note,
        invoice_id=invoice_id or None,
    )


@router.get("/suggested-replies")
def suggested_replies():
    return {
        "replies": wa.SEED_REPLIES,
        "notes": {
            "promise": "Auto-records payment promise + follow-up (does not mark paid).",
            "payment_claim": "Escalates to merchant; upload screenshot as evidence; match CSV to close.",
            "refusal": "Escalates to merchant inbox.",
        },
    }


@router.post("/sync-promises")
def sync_promises(db: Session = Depends(get_db)):
    """Re-scan WhatsApp mock chats and create any missing payment promises."""
    mid = get_settings().DEMO_MERCHANT_ID
    return wa.sync_promises_from_chat(db, mid)


@router.get("/payment-evidence")
def payment_evidence(db: Session = Depends(get_db)):
    """List WhatsApp payment proofs — customer name is always the chat customer."""
    mid = get_settings().DEMO_MERCHANT_ID
    return {"evidence": wa.list_payment_evidence(db, mid)}


@router.get("/evidence-file/{message_id}")
def evidence_file(message_id: int, db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    msg = db.get(Message, message_id)
    if not msg or msg.merchant_id != mid or msg.status != "payment_claim_evidence":
        raise HTTPException(status_code=404, detail="Evidence not found")
    if not msg.sandbox_note or not msg.sandbox_note.startswith("evidence_file:"):
        raise HTTPException(status_code=404, detail="File missing")
    name = msg.sandbox_note.replace("evidence_file:", "", 1)
    path = wa.EVIDENCE_DIR / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")
    return FileResponse(path, filename=name)
