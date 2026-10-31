import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import DATA_DIR, PROJECT_ROOT, get_settings
from app.database import SessionLocal, init_db
from app.routes import api_router

FRONTEND_DIST = PROJECT_ROOT / "frontend" / "dist"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    init_db()
    settings = get_settings()
    # Serverless /tmp is empty on cold start — seed demo so the live link is usable
    try:
        from sqlalchemy import select

        from app.models import Invoice
        from app.services.demo import load_demo_data

        db = SessionLocal()
        try:
            has_invoices = db.scalar(select(Invoice.id).limit(1))
            if has_invoices is None:
                load_demo_data(db, reset=True)
                logging.getLogger("vyapar").info("Seeded demo ledger on empty database")
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001
        logging.getLogger("vyapar").warning("Demo auto-seed skipped: %s", exc)
    logging.getLogger("vyapar").info(
        "Vyapar AI ready | sarvam=%s inngest=%s langfuse=%s db=%s",
        settings.sarvam_configured,
        settings.inngest_configured,
        settings.langfuse_configured,
        settings.DATABASE_URL.split(":", 1)[0],
    )
    yield


app = FastAPI(title="Paytm Vyapar AI", version="1.0.0", lifespan=lifespan)
settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list or ["*"],
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router, prefix="/api")

# Optional Inngest serve endpoint when configured
try:
    from app.scheduler.inngest_app import create_inngest_functions, get_inngest_client

    client = get_inngest_client()
    if client is not None:
        import inngest.fast_api

        inngest.fast_api.serve(app, client, create_inngest_functions(client))
except Exception as exc:  # noqa: BLE001
    logging.getLogger("vyapar").warning("Inngest serve skipped: %s", exc)


@app.get("/health")
def health():
    s = get_settings()
    return {
        "ok": True,
        "service": "vyapar-ai",
        "sarvam": s.sarvam_configured,
        "inngest": s.inngest_configured,
        "langfuse": s.langfuse_configured,
    }


if FRONTEND_DIST.is_dir():
    assets = FRONTEND_DIST / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")

    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        """Serve the Vite SPA after API routes (production / Vercel)."""
        if full_path.startswith("api/") or full_path in {"health", "docs", "openapi.json", "redoc"}:
            return {"ok": False, "error": "Not found"}
        candidate = (FRONTEND_DIST / full_path).resolve()
        try:
            candidate.relative_to(FRONTEND_DIST.resolve())
        except ValueError:
            return FileResponse(FRONTEND_DIST / "index.html")
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(FRONTEND_DIST / "index.html")
