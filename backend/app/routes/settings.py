from fastapi import APIRouter

from app.config import get_settings

router = APIRouter(prefix="/settings")


@router.get("/status")
def status():
    s = get_settings()
    return {
        "sarvam_configured": s.sarvam_configured,
        "sarvam_model": s.SARVAM_CHAT_MODEL,
        "inngest_configured": s.inngest_configured,
        "langfuse_configured": s.langfuse_configured,
        "database_url_scheme": s.DATABASE_URL.split(":", 1)[0],
        "demo_merchant_id": s.DEMO_MERCHANT_ID,
        "notes": {
            "sarvam": "Required for AI Teammate. Paste SARVAM_API_KEY in backend/.env",
            "inngest": "Optional. Without keys, DB-backed scheduler is used.",
            "langfuse": "Optional. Without keys, structured local logs are used.",
        },
    }
