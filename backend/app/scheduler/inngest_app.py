"""Inngest integration for delayed follow-ups (optional; DB remains source of truth)."""

from __future__ import annotations

from typing import Any

from app.config import get_settings
from app.services.observability import structured_log

_inngest_client = None


def get_inngest_client():
    global _inngest_client
    settings = get_settings()
    if not settings.inngest_configured:
        return None
    if _inngest_client is not None:
        return _inngest_client
    try:
        import inngest

        _inngest_client = inngest.Inngest(
            app_id="vyapar-ai",
            event_key=settings.INNGEST_EVENT_KEY or None,
            is_production=not bool(settings.INNGEST_DEV),
        )
        return _inngest_client
    except Exception as exc:  # noqa: BLE001
        structured_log("inngest_client_failed", error=str(exc))
        return None


def send_followup_event(
    *, followup_id: int, merchant_id: str, invoice_number: str, followup_date: str
) -> str | None:
    client = get_inngest_client()
    if client is None:
        return None
    try:
        import inngest

        result = client.send_sync(
            inngest.Event(
                name="vyapar/followup.scheduled",
                data={
                    "followup_id": followup_id,
                    "merchant_id": merchant_id,
                    "invoice_number": invoice_number,
                    "followup_date": followup_date,
                },
            )
        )
        # SDK may return list of ids
        if isinstance(result, list) and result:
            return str(result[0])
        return str(result) if result else f"evt-local-{followup_id}"
    except Exception as exc:  # noqa: BLE001
        structured_log("inngest_send_failed", error=str(exc))
        return None


def create_inngest_functions(client) -> list[Any]:
    """Register Inngest functions that re-check ledger before creating approval drafts."""
    import inngest

    @client.create_function(
        fn_id="process-followup",
        trigger=inngest.TriggerEvent(event="vyapar/followup.scheduled"),
    )
    async def process_followup_fn(ctx: inngest.Context, step: inngest.Step) -> dict:
        data = ctx.event.data
        followup_id = int(data["followup_id"])

        async def _run():
            from app.database import SessionLocal
            from app.scheduler.service import process_followup

            db = SessionLocal()
            try:
                return process_followup(db, followup_id)
            finally:
                db.close()

        return await step.run("process-followup-ledger-check", _run)

    return [process_followup_fn]
