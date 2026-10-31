from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.evaluation.runner import run_evaluation
from app.models import EvaluationResult, EvaluationRun

router = APIRouter(prefix="/evaluation")


@router.post("/run")
def run(db: Session = Depends(get_db)):
    return run_evaluation(db)


@router.get("/latest")
def latest(db: Session = Depends(get_db)):
    mid = get_settings().DEMO_MERCHANT_ID
    run = db.scalar(
        select(EvaluationRun)
        .where(EvaluationRun.merchant_id.in_([mid, f"{mid}-eval"]))
        .order_by(EvaluationRun.id.desc())
        .limit(1)
    )
    # Prefer latest overall
    run = db.scalar(select(EvaluationRun).order_by(EvaluationRun.id.desc()).limit(1))
    if not run:
        return {"run": None, "metrics": []}
    results = list(db.scalars(select(EvaluationResult).where(EvaluationResult.run_id == run.id)))
    return {
        "run": {
            "id": run.id,
            "status": run.status,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            "summary_json": run.summary_json,
        },
        "metrics": [
            {
                "metric_key": r.metric_key,
                "metric_name": r.metric_name,
                "numerator": r.numerator,
                "denominator": r.denominator,
                "value": r.value,
                "target": r.target,
                "passed": r.passed,
            }
            for r in results
        ],
    }
