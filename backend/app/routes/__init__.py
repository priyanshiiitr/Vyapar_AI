from fastapi import APIRouter

from app.routes import (
    agent,
    collections,
    dashboard,
    demo,
    doc_ai,
    evaluation,
    invoices,
    reconciliation,
    scheduler,
    settings,
    synthetic,
    voice,
    whatsapp,
)


api_router = APIRouter()
api_router.include_router(dashboard.router, tags=["dashboard"])
api_router.include_router(demo.router, tags=["demo"])
api_router.include_router(invoices.router, tags=["invoices"])
api_router.include_router(reconciliation.router, tags=["reconciliation"])
api_router.include_router(collections.router, tags=["collections"])
api_router.include_router(agent.router, tags=["agent"])
api_router.include_router(scheduler.router, tags=["scheduler"])
api_router.include_router(evaluation.router, tags=["evaluation"])
api_router.include_router(settings.router, tags=["settings"])
api_router.include_router(doc_ai.router, tags=["doc-ai"])
api_router.include_router(synthetic.router, tags=["synthetic"])
api_router.include_router(whatsapp.router, tags=["whatsapp-mock"])
api_router.include_router(voice.router, tags=["voice"])
