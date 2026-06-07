"""LLM provider configuration (part of the user profile).

Lets the user pick a provider + model. Local Ollama is the default so an unconfigured
profile stays 100% on-device. For cloud providers the API key is referenced BY ENV-VAR
NAME (``api_key_ref``) — the raw secret is NEVER stored in the profile/JSON/DB.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

LLMProvider = Literal[
    "ollama",  # local, default, private
    "google_genai",
    "groq",
    "openai",
    "anthropic",
    "mistralai",
    "openrouter",
]


class LLMConfig(BaseModel):
    """Per-profile LLM selection. Defaults keep the app fully local."""

    provider: LLMProvider = "ollama"
    model: str = Field(default="llama3.1", description="Model id, e.g. 'qwen2.5', 'llama3.1', or a cloud model name")
    api_key_ref: str | None = Field(
        default=None,
        description="Name of the ENVIRONMENT VARIABLE holding the API key (e.g. 'GEMINI_API_KEY'). "
        "Never the raw key. Only used for non-ollama providers.",
    )
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)

    model_config = {"extra": "ignore"}

    @property
    def is_local(self) -> bool:
        return self.provider == "ollama"
