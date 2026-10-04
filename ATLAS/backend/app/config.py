"""Settings read from environment variables / the root .env file (found via this file's location,
so it works no matter which folder Uvicorn is started from)."""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]  # ATLAS/
load_dotenv(ROOT_DIR / ".env")

PLACEHOLDER_KEY = "put_your_key_here"


@dataclass
class Settings:
    llm_api_key: str
    llm_base_url: str
    llm_model: str
    llm_timeout_seconds: float
    database_url: str
    cors_origins: list[str]
    upload_dir: Path


def _resolve_sqlite_url(url: str) -> str:
    """Make relative sqlite paths (sqlite:///./atlas.db) relative to the project root, not the cwd."""
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:////") and url != "sqlite://":
        path = Path(url[len(prefix):])
        if not path.is_absolute() and not (len(url) > 11 and url[11] == ":"):
            return prefix + str((ROOT_DIR / path).resolve())
    return url


def load_settings() -> Settings:
    origins = os.getenv("CORS_ORIGINS") or os.getenv("FRONTEND_ORIGIN") or "http://localhost:5173,http://127.0.0.1:5173"
    return Settings(
        llm_api_key=os.getenv("LLM_API_KEY", "").strip(),
        llm_base_url=os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1").strip(),
        llm_model=os.getenv("LLM_MODEL", "llama-3.3-70b-versatile").strip(),
        llm_timeout_seconds=float(os.getenv("LLM_TIMEOUT_SECONDS", "30")),
        database_url=_resolve_sqlite_url(os.getenv("DATABASE_URL", "sqlite:///./atlas.db")),
        cors_origins=[o.strip() for o in origins.split(",") if o.strip()],
        upload_dir=Path(os.getenv("UPLOAD_DIR", str(ROOT_DIR / "uploads"))),
    )


settings = load_settings()
