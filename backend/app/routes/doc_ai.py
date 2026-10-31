from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT, get_settings
from app.database import get_db
from app.services.doc_ai import extract_invoice_fields, write_sample_invoice_pdf
from app.services.ledger_from_extract import create_ledger_invoice_from_fields

router = APIRouter(prefix="/doc-ai")

SAMPLE_PDF = PROJECT_ROOT / "data" / "samples" / "demo_invoice_r204.pdf"
COMPLEX_GST_PDF = PROJECT_ROOT / "data" / "samples" / "vyapar_ai_complex_indian_gst_invoice_1.pdf"


class ConfirmLedgerRequest(BaseModel):
    invoice_id: str = Field(min_length=1, max_length=64)
    customer_name: str = Field(min_length=1, max_length=255)
    customer_phone: str | None = None
    amount: str | float | int
    amount_paid: str | float | int | None = None
    balance_due: str | float | int | None = None
    invoice_date: str
    due_date: str
    description: str | None = None


@router.get("/sample")
def sample_invoice():
    if not SAMPLE_PDF.exists():
        write_sample_invoice_pdf(SAMPLE_PDF)
    return FileResponse(
        SAMPLE_PDF,
        media_type="application/pdf",
        filename="demo_invoice_r204.pdf",
    )


@router.get("/sample-complex")
def sample_complex_invoice():
    if not COMPLEX_GST_PDF.exists():
        return {"ok": False, "error": "Complex GST sample PDF not found in data/samples"}
    return FileResponse(
        COMPLEX_GST_PDF,
        media_type="application/pdf",
        filename="vyapar_ai_complex_indian_gst_invoice_1.pdf",
    )


@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    settings = get_settings()
    if not settings.sarvam_configured:
        return {
            "ok": False,
            "error": "SARVAM_API_KEY not configured",
        }
    content = await file.read()
    if not content:
        return {"ok": False, "error": "Empty file"}
    if len(content) > 8_000_000:
        return {"ok": False, "error": "File too large for demo (max ~8MB)"}
    return extract_invoice_fields(
        filename=file.filename or "document.pdf",
        content=content,
        content_type=file.content_type,
    )


@router.post("/confirm-ledger")
def confirm_ledger(payload: ConfirmLedgerRequest, db: Session = Depends(get_db)):
    """Merchant-reviewed Document AI fields → real ledger invoice (+ overdue case if due)."""
    mid = get_settings().DEMO_MERCHANT_ID
    return create_ledger_invoice_from_fields(
        db,
        mid,
        payload.model_dump(),
        is_demo=True,
    )
