"""LLM provider layer: local Ollama by default, optional opt-in cloud via API key."""

from .factory import (
    RECOMMENDED_LOCAL_MODELS,
    egress_warning,
    get_chat_model,
    is_known_weak_for_plans,
    is_tool_reliable,
    plan_capability_warning,
    resolve_api_key,
    resolve_default_local_model,
)

__all__ = [
    "RECOMMENDED_LOCAL_MODELS",
    "get_chat_model",
    "egress_warning",
    "is_tool_reliable",
    "is_known_weak_for_plans",
    "plan_capability_warning",
    "resolve_api_key",
    "resolve_default_local_model",
]
