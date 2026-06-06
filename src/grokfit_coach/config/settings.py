"""Central settings for grokfit-coach using pydantic-settings.

All configuration can be overridden via environment variables with the
GROKFIT_ prefix (e.g. GROKFIT_OLLAMA_MODEL=llama3.2) or a .env file.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings for local Ollama + RAG paths."""

    # Ollama connection
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"

    # Embeddings for local RAG (sentence-transformers, downloaded on first use)
    embed_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Base directories (computed relative to project root)
    # src/grokfit_coach/config/settings.py -> parents[3] == repo root
    project_root: Path = Path(__file__).resolve().parents[3]
    seeds_dir: Path = Path(__file__).resolve().parents[3] / "data" / "seeds"
    index_dir: Path = Path(__file__).resolve().parents[3] / "data" / "indexes"

    # User data / persistence (Phase 2 - local JSON files)
    user_data_dir: Path = Path.home() / ".grokfit"
    profile_path: Path = Path.home() / ".grokfit" / "profile.json"
    last_plan_path: Path = Path.home() / ".grokfit" / "last_plan.json"

    model_config = SettingsConfigDict(
        env_prefix="GROKFIT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        validate_default=True,
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (singleton-like)."""
    return Settings()


def ensure_data_dirs(settings: Settings | None = None) -> None:
    """Ensure the local data directories for seeds and indexes exist."""
    s = settings or get_settings()
    s.seeds_dir.mkdir(parents=True, exist_ok=True)
    s.index_dir.mkdir(parents=True, exist_ok=True)


def ensure_user_data_dirs(settings: Settings | None = None) -> None:
    """Ensure the user data directory for persistence (profile/plan JSON) exists."""
    s = settings or get_settings()
    s.user_data_dir.mkdir(parents=True, exist_ok=True)
