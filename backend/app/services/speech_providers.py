"""Speech recognition provider interface (Web Speech on client; Saaras-ready on server)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.config import get_settings


class SpeechRecognitionProvider(ABC):
    name: str

    @abstractmethod
    def is_configured(self) -> bool:
        ...

    @abstractmethod
    def transcribe(self, *, audio_bytes: bytes, filename: str, language: str) -> dict[str, Any]:
        """Return {ok, transcript, provider, error?}."""
        ...


class WebSpeechClientProvider(SpeechRecognitionProvider):
    """Browser Web Speech API — recognition happens on the client; server only documents capability."""

    name = "web_speech"

    def is_configured(self) -> bool:
        return True

    def transcribe(self, *, audio_bytes: bytes, filename: str, language: str) -> dict[str, Any]:
        return {
            "ok": False,
            "provider": self.name,
            "error": (
                "Web Speech runs in the browser. Send transcript via /api/voice/command. "
                "Do not upload audio to this provider."
            ),
        }


class SarvamSaarasProvider(SpeechRecognitionProvider):
    """
    Future-compatible Sarvam Saaras v4 hook.
    Enable by setting SARVAM_API_KEY (already used) + VOICE_STT_PROVIDER=saaras when wiring the API.
    """

    name = "sarvam_saaras_v4"

    def is_configured(self) -> bool:
        return get_settings().sarvam_configured

    def transcribe(self, *, audio_bytes: bytes, filename: str, language: str) -> dict[str, Any]:
        if not self.is_configured():
            return {
                "ok": False,
                "provider": self.name,
                "error": "SARVAM_API_KEY not configured for Saaras STT",
            }
        # Placeholder — keep credentials server-side; wire Sarvam Saaras when product enables it.
        return {
            "ok": False,
            "provider": self.name,
            "error": (
                "Sarvam Saaras v4 STT endpoint not enabled in this build. "
                "UI already uses Web Speech; switch VOICE_STT_PROVIDER when Saaras is activated."
            ),
            "bytes_received": len(audio_bytes),
            "filename": filename,
            "language": language,
        }


def get_speech_provider(name: str | None = None) -> SpeechRecognitionProvider:
    settings = get_settings()
    chosen = (name or getattr(settings, "VOICE_STT_PROVIDER", None) or "web_speech").lower()
    if chosen in {"saaras", "sarvam", "sarvam_saaras", "sarvam_saaras_v4"}:
        return SarvamSaarasProvider()
    return WebSpeechClientProvider()
