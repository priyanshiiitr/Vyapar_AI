import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent


def _writable_data_dir() -> Path:
    """Vercel functions can only write to /tmp; local/dev uses repo data/."""
    if os.environ.get("VERCEL"):
        path = Path("/tmp/vyapar-data")
    else:
        path = PROJECT_ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATA_DIR = _writable_data_dir()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_ENV: str = "development"
    DATABASE_URL: str = f"sqlite:///{(_writable_data_dir() / 'vyapar.db').as_posix()}"
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,https://*.vercel.app"
    )
    DEMO_MERCHANT_ID: str = "demo-merchant"

    SARVAM_API_KEY: str = ""
    SARVAM_CHAT_MODEL: str = "sarvam-105b"
    SARVAM_TIMEOUT_SECONDS: int = 60
    SARVAM_MAX_TOKENS: int = 4096
    # web_speech (browser) | saaras (future Sarvam Saaras v4 server STT)
    VOICE_STT_PROVIDER: str = "web_speech"

    INNGEST_EVENT_KEY: str = ""
    INNGEST_SIGNING_KEY: str = ""
    INNGEST_DEV: int = 1

    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def sarvam_configured(self) -> bool:
        return bool(self.SARVAM_API_KEY.strip())

    @property
    def inngest_configured(self) -> bool:
        return bool(self.INNGEST_EVENT_KEY.strip() and self.INNGEST_SIGNING_KEY.strip())

    @property
    def langfuse_configured(self) -> bool:
        return bool(self.LANGFUSE_PUBLIC_KEY.strip() and self.LANGFUSE_SECRET_KEY.strip())


@lru_cache
def get_settings() -> Settings:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    settings = Settings()
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        raw = url.removeprefix("sqlite:///")
        # Treat relative paths as project-root data files
        is_absolute = raw.startswith("/") or (len(raw) > 2 and raw[1] == ":")
        if not is_absolute:
            name = Path(raw).name or "vyapar.db"
            settings = settings.model_copy(
                update={"DATABASE_URL": f"sqlite:///{(DATA_DIR / name).as_posix()}"}
            )
    return settings


