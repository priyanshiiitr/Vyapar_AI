from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Transaction
from app.services.money import format_inr
from app.services.reconciliation import (
    import_invoices,
    import_transactions,
    preview_csv,
    run_reconciliation,
)

router = APIRouter(prefix="/reconciliation")


@router.post("/preview")
async def preview(kind: str = Form(...), file: UploadFile = File(...)):
    content = (await file.read()).decode("utf-8-sig")
    return preview_csv(content, kind)


@router.post("/upload-invoices")
async def upload_invoices(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = (await file.read()).decode("utf-8-sig")
    mid = get_settings().DEMO_MERCHANT_ID
    return import_invoices(
        db,
        merchant_id=mid,
        content=content,
        filename=file.filename or "invoices.csv",
        is_demo=True,
    )


@router.post("/upload-transactions")
async def upload_transactions(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = (await file.read()).decode("utf-8-sig")
    mid = get_settings().DEMO_MERCHANT_ID
    return import_transactions(
        db,
        merchant_id=mid,
        content=content,
        filename=file.filename or "transactions.csv",
        is_demo=True,
    )


@router.post("/run")
def reconcile(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return run_reconciliation(db, mid)


@router.get("/transactions")
def list_transactions(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    rows = list(db.scalars(select(Transaction).where(Transaction.merchant_id == mid)))
    return {
        "transactions": [
            {
                "transaction_id": t.transaction_id,
                "reference": t.reference,
                "amount": format_inr(t.amount_paise),
                "amount_paise": t.amount_paise,
                "date": t.transaction_date.isoformat(),
                "customer_name": t.customer_name,
                "status": t.status,
                "evidence_source": t.evidence_source,
                "notes": t.notes,
            }
            for t in rows
        ]
    }
