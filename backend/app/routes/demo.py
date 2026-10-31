from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.config import PROJECT_ROOT
from app.database import get_db
from app.services.demo import load_demo_data, reset_demo_data, txn_803_csv

router = APIRouter(prefix="/demo")

SAMPLES = PROJECT_ROOT / "data" / "samples"


@router.post("/load")
def load(reset: bool = True, db: Session = Depends(get_db)):
    return load_demo_data(db, reset=reset)


@router.post("/reset")
def reset(db: Session = Depends(get_db)):
    reset_demo_data(db)
    return {"ok": True}


@router.get("/txn-803.csv")
def get_txn_803():
    return PlainTextResponse(txn_803_csv(), media_type="text/csv")


def _sample_file(name: str) -> Path:
    path = SAMPLES / name
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Sample not found: {name}")
    return path


@router.get("/payment-proof/r104")
def payment_proof_r104():
    """Customer-side UPI success screenshot for R-104 (₹15,000)."""
    path = _sample_file("payment_proof_R104_ABC_Stores.png")
    return FileResponse(path, media_type="image/png", filename=path.name)


@router.get("/payment-proof/sbh104")
def payment_proof_sbh104():
    """Customer-side UPI success screenshot for SBH/26-27/104 (₹15,000)."""
    path = _sample_file("payment_proof_SBH_Sharma_Electrical.png")
    return FileResponse(path, media_type="image/png", filename=path.name)


@router.get("/txn-r104-clear.csv")
def txn_r104_clear():
    path = _sample_file("txn_r104_clear.csv")
    return FileResponse(path, media_type="text/csv", filename=path.name)


@router.get("/txn-sbh104-clear.csv")
def txn_sbh104_clear():
    path = _sample_file("txn_sbh_104_clear.csv")
    return FileResponse(path, media_type="text/csv", filename=path.name)


@router.get("/payment-proof/r106")
def payment_proof_r106():
    """Customer-side UPI success screenshot for R-106 Kumar Mart (₹18,000)."""
    path = _sample_file("payment_proof_R106_Kumar_Mart.png")
    return FileResponse(path, media_type="image/png", filename=path.name)


@router.get("/txn-r106-clear.csv")
def txn_r106_clear():
    path = _sample_file("txn_r106_clear.csv")
    return FileResponse(path, media_type="text/csv", filename=path.name)
