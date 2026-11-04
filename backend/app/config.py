"""Settings, read from environment variables and backend/.env.

Real environment variables win over backend/.env, so a deployment (or a test run) can override any value.
"""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_DIR = BACKEND_DIR.parent

load_dotenv(BACKEND_DIR / ".env", override=False)


def _database_url(raw: str) -> str:
    """Normalise DATABASE_URL.

    - A relative SQLite path ("sqlite:///./leadops.db") lands inside backend/, whichever folder uvicorn runs from.
    - Postgres URLs as Neon/Supabase print them ("postgres://...") get the psycopg driver SQLAlchemy needs.
    """
    if raw.startswith("sqlite:///"):
        path = raw.removeprefix("sqlite:///")
        if path and path != ":memory:" and not path.startswith("/") and not Path(path).is_absolute():
            return "sqlite:///" + (BACKEND_DIR / path).resolve().as_posix()
        return raw
    for prefix in ("postgres://", "postgresql://"):
        if raw.startswith(prefix):
            return "postgresql+psycopg://" + raw.removeprefix(prefix)
    return raw


def _env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


@dataclass(frozen=True)
class Settings:
    database_url: str
    cors_origins: list[str]
    llm_provider: str  # auto | anthropic | gemini | groq | none
    llm_model: str  # empty means the provider's default model
    anthropic_api_key: str
    gemini_api_key: str
    groq_api_key: str


settings = Settings(
    database_url=_database_url(_env("DATABASE_URL", "sqlite:///./leadops.db")),
    cors_origins=[origin.strip() for origin in _env("CORS_ORIGINS", "*").split(",") if origin.strip()],
    llm_provider=_env("LLM_PROVIDER", "auto").lower(),
    llm_model=_env("LLM_MODEL"),
    anthropic_api_key=_env("ANTHROPIC_API_KEY"),
    gemini_api_key=_env("GEMINI_API_KEY"),
    groq_api_key=_env("GROQ_API_KEY"),
)
