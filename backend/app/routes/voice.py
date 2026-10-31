"""Voice-to-browse: interpret transcripts; execute via existing agent when safe."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.orchestrator import run_agent
from app.config import get_settings
from app.database import get_db
from app.services.speech_providers import get_speech_provider
from app.services.voice_intent import ALLOWED_ROUTES, interpret_voice_command, normalize_route

router = APIRouter(prefix="/voice")


class VoiceCommandRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=2000)
    language: str = "en-IN"
    confirmed: bool = False
    conversation_id: int | None = None
    execute_agent: bool = True


@router.get("/capabilities")
def capabilities():
    settings = get_settings()
    provider = get_speech_provider()
    return {
        "stt_provider": provider.name,
        "stt_configured": provider.is_configured(),
        "preferred_client_stt": "web_speech",
        "languages": [
            {"code": "en-IN", "label": "English (India)"},
            {"code": "hi-IN", "label": "Hindi"},
        ],
        "allowed_routes": sorted(set(ALLOWED_ROUTES.values())),
        "sarvam_chat": settings.sarvam_configured,
        "notes": [
            "Primary STT is browser Web Speech API (no extra API key).",
            "Sensitive actions require confirmed=true after merchant review.",
            "Navigation is allowlisted only — model cannot invent URLs or JavaScript.",
        ],
    }


@router.post("/command")
def voice_command(payload: VoiceCommandRequest, db: Session = Depends(get_db)):
    """
    Interpret spoken/edited transcript.
    - navigate → frontend uses allowlisted route
    - needs_confirmation → UI shows confirm; resubmit with confirmed=true
    - agent_query → optionally runs existing run_agent (Sarvam tools)
    """
    mid = get_settings().DEMO_MERCHANT_ID
    interpreted = interpret_voice_command(payload.transcript, confirmed=payload.confirmed)

    if not interpreted.get("ok"):
        return interpreted

    action = interpreted.get("action")

    if action == "navigate":
        route = normalize_route(interpreted.get("route") or "")
        if not route:
            return {
                "ok": False,
                "action": "unsupported",
                "error": "Navigation target not in allowlist",
            }
        interpreted["route"] = route
        return interpreted

    if action == "needs_confirmation":
        return interpreted

    if action == "agent_query":
        if not payload.execute_agent:
            return interpreted
        agent_result = run_agent(
            db,
            merchant_id=mid,
            user_message=interpreted["agent_message"],
            conversation_id=payload.conversation_id,
        )
        return {
            **interpreted,
            "agent": agent_result,
            "assistant_message": agent_result.get("assistant_message") or agent_result.get("error"),
            "conversation_id": agent_result.get("conversation_id"),
            "tool_calls": agent_result.get("tool_calls") or [],
        }

    return interpreted


@router.post("/transcribe")
async def transcribe_audio(
    language: str = Form("hi-IN"),
    file: UploadFile = File(...),
):
    """Optional server STT (Saaras when enabled). Web Speech clients should not need this."""
    provider = get_speech_provider()
    content = await file.read()
    return provider.transcribe(
        audio_bytes=content,
        filename=file.filename or "audio.webm",
        language=language,
    )
