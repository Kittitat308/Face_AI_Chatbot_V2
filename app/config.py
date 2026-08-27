import os

from dataclasses import dataclass
from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg://postgres:postgres@localhost:5432/face_ai_chatbot",
    )

    gemini_api_key: str = os.getenv(
        "GEMINI_API_KEY",
        "",
    )

    gemini_model: str = os.getenv(
        "GEMINI_MODEL",
        "gemini-2.5-flash",
    )

    face_match_threshold: float = float(
        os.getenv(
            "FACE_MATCH_THRESHOLD",
            "0.45",
        )
    )

    camera_index: int = int(
        os.getenv(
            "CAMERA_INDEX",
            "0",
        )
    )

    app_name: str = os.getenv(
        "APP_NAME",
        "Face AI Chatbot",
    )

    login_scan_interval_ms: int = int(os.getenv("LOGIN_SCAN_INTERVAL_MS", "5000"))
    presence_scan_interval_ms: int = int(os.getenv("PRESENCE_SCAN_INTERVAL_MS", "30000"))
    max_login_attempts: int = int(os.getenv("MAX_LOGIN_ATTEMPTS", "5"))
    lockout_minutes: int = int(os.getenv("LOCKOUT_MINUTES", "5"))
    whisper_record_seconds: int = int(os.getenv("WHISPER_RECORD_SECONDS", "6"))


settings = Settings()
