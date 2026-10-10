"""Runtime configuration, read from environment variables (.env in local dev)."""

import os
from pathlib import Path

from dotenv import load_dotenv


class Settings:
    """All configuration in one place; nothing else in the app reads os.environ."""

    DEFAULT_DATABASE_URL = "sqlite:///./patients.db"
    # Local secrets live in env/.env (git-ignored). In production the host injects real
    # environment variables, which always win over the file.
    ENV_FILE = Path(__file__).resolve().parents[2] / "env" / ".env"

    def __init__(self) -> None:
        load_dotenv(self.ENV_FILE)
        self.database_url = self._normalize_database_url(
            os.getenv("DATABASE_URL") or self.DEFAULT_DATABASE_URL
        )
        self.public_base_url = os.getenv("PUBLIC_BASE_URL", "").strip().rstrip("/")
        self.vapi_api_key = os.getenv("VAPI_API_KEY", "").strip()
        self.vapi_webhook_secret = os.getenv("VAPI_WEBHOOK_SECRET", "").strip()
        self.clinic_name = os.getenv("CLINIC_NAME", "Lakeside Family Health")
        self.seed_demo_data = self._flag(os.getenv("SEED_DEMO_DATA", "true"))
        self.vapi_model_provider = os.getenv("VAPI_MODEL_PROVIDER", "openai")
        self.vapi_model = os.getenv("VAPI_MODEL", "gpt-4.1")
        self.vapi_voice_provider = os.getenv("VAPI_VOICE_PROVIDER", "vapi")
        self.vapi_voice_id = os.getenv("VAPI_VOICE_ID", "Paige")
        self.vapi_area_code = os.getenv("VAPI_AREA_CODE", "415")

    @staticmethod
    def _normalize_database_url(url: str) -> str:
        # Railway hands out postgres:// or postgresql:// URLs; point SQLAlchemy at psycopg 3.
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return "postgresql+psycopg://" + url[len(prefix):]
        return url

    @staticmethod
    def _flag(value: str) -> bool:
        return value.strip().lower() in ("1", "true", "yes")
