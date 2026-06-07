"""LLM provider factory.

Design goals (from PHASE_3_PLAN, Milestone 2):
- **Local by default**: an unconfigured profile uses Ollama → 100% on-device.
- **Optional cloud**: opt-in per profile; provider package is lazy-imported (extras ``[cloud]``);
  the API key is read from an ENV VAR (or OS keyring), **never** from the profile/DB.
- **Egress warning**: any non-local provider triggers a clear data-egress warning.
- **Plan path gated to tool-reliable models** (structured output): weak models are flagged.

The same factory output is used everywhere, so plan/chat code is provider-agnostic and still
calls ``.with_structured_output(...)`` exactly as before.
"""

from __future__ import annotations

import os
import re
import warnings
from typing import Any

from grokfit_coach.config.settings import get_settings
from grokfit_coach.models.llm_config import LLMConfig

# Curated local menu, ordered by structured-output reliability (best first).
# RAM is an approximate q4_K_M footprint incl. context headroom (~0.6 GB / 1B params).
RECOMMENDED_LOCAL_MODELS: list[dict[str, str]] = [
    {"model": "qwen2.5", "ram": "~5-6 GB", "note": "Recommended default. Reliable structured output at 7B."},
    {"model": "qwen2.5:14b", "ram": "~9-10 GB", "note": "Stronger tool selection for nested plans."},
    {"model": "llama3.1", "ram": "~6-7 GB", "note": "Broad-compatibility baseline (current default)."},
    {"model": "qwen3", "ram": "~9-10 GB", "note": "Newer; opt-in upgrade (disable thinking for plans)."},
    {"model": "qwen3.5", "ram": "~18-24 GB", "note": "Newer; opt-in upgrade. 256K context."},
    {"model": "gemma4", "ram": "~9-18 GB", "note": "Apache-2.0, native function-calling. (Gemma 2/3 are NOT usable for plans.)"},
    {"model": "mistral-nemo", "ram": "~8-10 GB", "note": "Decent tool calling."},
]

# Base model names (the part before any ':tag') known to do structured output well.
_TOOL_RELIABLE_BASES = {
    "qwen2.5",
    "qwen3",
    "qwen3.5",
    "llama3.1",
    "llama3.3",
    "gemma4",
    "mistral-nemo",
    "mistral-small",
}

# Base names known to be WEAK at tool/structured output -> keep out of the plan path.
_WEAK_BASES = {"gemma", "gemma2", "gemma3", "phi", "phi3", "phi4", "llama3.2", "tinyllama", "mistral"}


def _base(model: str) -> str:
    return model.split(":", 1)[0].strip().lower()


def _tag(model: str) -> str:
    return model.split(":", 1)[1].lower() if ":" in model else ""


def is_tool_reliable(model: str) -> bool:
    """True if the model is on the curated tool-reliable allowlist."""
    return _base(model) in _TOOL_RELIABLE_BASES


_SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*b")


def is_known_weak_for_plans(model: str) -> bool:
    """True if the model is known to be unreliable for structured plan generation."""
    if _base(model) in _WEAK_BASES:
        return True
    tag = _tag(model)
    # very low quants degrade tool-calling before chat quality
    if any(s in tag for s in ("q2", "q3", "iq2", "iq3")):
        return True
    # sub-7B parameter counts are unreliable for nested structured output
    m = _SIZE_RE.search(tag)
    if m:
        try:
            return float(m.group(1)) < 7
        except ValueError:
            return False
    return False


# --------------------------------------------------------------------------- #
# Warnings / capability messages
# --------------------------------------------------------------------------- #
EGRESS_WARNING_TEMPLATE = (
    "DATA EGRESS WARNING: provider '{provider}' is a CLOUD service. Your messages — including "
    "profile details, injuries, and dietary/allergen info — will be sent to {provider} and leave "
    "your device. This breaks grokfit-coach's local-only guarantee, and some free tiers may use "
    "your data for training. Set the provider back to 'ollama' for fully local operation."
)


def egress_warning(config: LLMConfig) -> str | None:
    """Return a data-egress warning string for cloud providers, else None."""
    if config.is_local:
        return None
    return EGRESS_WARNING_TEMPLATE.format(provider=config.provider)


def plan_capability_warning(config: LLMConfig) -> str | None:
    """Return a message if the configured model is a poor fit for structured plan generation."""
    if not config.is_local:
        return None  # cloud models are generally strong at structured output
    if is_known_weak_for_plans(config.model):
        return (
            f"Model '{config.model}' is weak at structured output and may fail to produce valid "
            f"plans (the app will fall back to a deterministic plan). For reliable plans pick one of: "
            f"{', '.join(m['model'] for m in RECOMMENDED_LOCAL_MODELS)}."
        )
    if not is_tool_reliable(config.model):
        return (
            f"Model '{config.model}' is not on the verified tool-reliable list; structured plan "
            f"generation may be unreliable. Recommended: {RECOMMENDED_LOCAL_MODELS[0]['model']}."
        )
    return None


# --------------------------------------------------------------------------- #
# API key resolution (env var or OS keyring — never the raw key in the profile)
# --------------------------------------------------------------------------- #
def resolve_api_key(api_key_ref: str | None) -> str | None:
    """Resolve an API key from the named env var, falling back to the OS keyring."""
    if not api_key_ref:
        return None
    val = os.environ.get(api_key_ref)
    if val:
        return val
    try:
        import keyring  # optional dependency

        return keyring.get_password("grokfit-coach", api_key_ref)
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Default local model (auto-detect already-pulled models, else configured default)
# --------------------------------------------------------------------------- #
def resolve_default_local_model(settings: Any | None = None) -> str:
    """Pick the best already-installed tool-reliable Ollama model, else the configured default.

    Best-effort and fully offline-safe: if Ollama isn't reachable, returns settings.ollama_model.
    """
    s = settings or get_settings()
    try:
        import json as _json
        import urllib.request

        with urllib.request.urlopen(f"{s.ollama_host}/api/tags", timeout=1.5) as resp:  # noqa: S310
            payload = _json.loads(resp.read())
        installed = [m.get("name", "") for m in payload.get("models", [])]
        for cand in (m["model"] for m in RECOMMENDED_LOCAL_MODELS):
            for inst in installed:
                if inst == cand or inst.startswith(cand + ":"):
                    return cand
    except Exception:
        pass
    return s.ollama_model


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def _config_from(profile: Any | None, settings: Any) -> LLMConfig:
    cfg = getattr(profile, "llm_config", None)
    if isinstance(cfg, LLMConfig):
        return cfg
    return LLMConfig(provider="ollama", model=settings.ollama_model)


def get_chat_model(
    profile: Any | None = None,
    settings: Any | None = None,
    *,
    temperature: float | None = None,
):
    """Return a LangChain chat model for the profile's LLMConfig (local Ollama by default)."""
    s = settings or get_settings()
    config = _config_from(profile, s)
    temp = config.temperature if temperature is None else temperature

    if config.is_local:
        from langchain_ollama import ChatOllama

        model = config.model or resolve_default_local_model(s)
        # Construction does not open a connection; failures surface at .invoke() time.
        return ChatOllama(model=model, base_url=s.ollama_host, temperature=temp)

    # --- cloud (opt-in) ---
    warn = egress_warning(config)
    if warn:
        warnings.warn(warn, stacklevel=2)

    api_key = resolve_api_key(config.api_key_ref)
    if not api_key:
        raise RuntimeError(
            f"No API key for cloud provider '{config.provider}'. Set the environment variable "
            f"'{config.api_key_ref or '<set api_key_ref to an env var name>'}' (or store it via the "
            f"'keyring' package). Keys are never stored in your profile."
        )

    try:
        from langchain.chat_models import init_chat_model
    except Exception as e:  # pragma: no cover - langchain always present
        raise RuntimeError("init_chat_model is unavailable; upgrade langchain.") from e

    try:
        return init_chat_model(
            config.model,
            model_provider=config.provider,
            api_key=api_key,
            temperature=temp,
        )
    except ImportError as e:
        raise RuntimeError(
            f"Cloud provider '{config.provider}' requires its integration package. "
            f"Install the optional extras with:  pip install 'grokfit-coach[cloud]'"
        ) from e
