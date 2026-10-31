from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.scheduler.service import process_due_followups

router = APIRouter(prefix="/scheduler")


@router.post("/process-due")
def process_due(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    return process_due_followups(db, mid)
