"""Hermetic tests for the LLM provider factory (M2). No network / no Ollama required."""

from __future__ import annotations

import pytest
from langchain_ollama import ChatOllama

from grokfit_coach.llm import factory
from grokfit_coach.models import EXAMPLE_USER_PROFILE, LLMConfig


def test_recommended_menu_default_is_qwen():
    assert factory.RECOMMENDED_LOCAL_MODELS, "menu must not be empty"
    assert factory.RECOMMENDED_LOCAL_MODELS[0]["model"] == "qwen2.5"


@pytest.mark.parametrize("model", ["qwen2.5", "qwen2.5:14b", "llama3.1", "gemma4", "mistral-nemo"])
def test_tool_reliable_true(model):
    assert factory.is_tool_reliable(model)


@pytest.mark.parametrize("model", ["gemma2", "gemma3", "phi4", "llama3.2", "llama3.2:3b", "mistral"])
def test_known_weak_for_plans(model):
    assert factory.is_known_weak_for_plans(model)


@pytest.mark.parametrize("model", ["qwen2.5", "qwen2.5:14b", "llama3.1", "gemma4", "mistral-nemo"])
def test_reliable_models_not_flagged_weak(model):
    assert not factory.is_known_weak_for_plans(model)


def test_low_quant_and_tiny_sizes_flagged_weak():
    assert factory.is_known_weak_for_plans("qwen2.5:0.5b")  # tiny tag
    assert factory.is_known_weak_for_plans("llama3.1:8b-instruct-q2_K")  # low quant


def test_egress_warning_local_is_none():
    assert factory.egress_warning(LLMConfig(provider="ollama", model="qwen2.5")) is None


def test_egress_warning_cloud_mentions_provider():
    msg = factory.egress_warning(LLMConfig(provider="groq", model="llama-3.3-70b-versatile"))
    assert msg is not None and "groq" in msg and "leave your device" in msg


def test_plan_capability_warning():
    assert factory.plan_capability_warning(LLMConfig(provider="ollama", model="qwen2.5")) is None
    weak = factory.plan_capability_warning(LLMConfig(provider="ollama", model="gemma3"))
    assert weak is not None and "gemma3" in weak


def test_resolve_api_key_from_env(monkeypatch):
    monkeypatch.setenv("GROKFIT_TEST_KEY", "secret-123")
    assert factory.resolve_api_key("GROKFIT_TEST_KEY") == "secret-123"


def test_resolve_api_key_missing_returns_none(monkeypatch):
    monkeypatch.delenv("GROKFIT_NOPE", raising=False)
    # keyring (if installed) has no entry for this service/name -> None
    assert factory.resolve_api_key("GROKFIT_NOPE") is None
    assert factory.resolve_api_key(None) is None


def test_get_chat_model_local_returns_chatollama():
    llm = factory.get_chat_model(EXAMPLE_USER_PROFILE)  # default config -> ollama/llama3.1
    assert isinstance(llm, ChatOllama)
    assert llm.model == "llama3.1"


def test_get_chat_model_none_profile_is_local():
    llm = factory.get_chat_model(None)
    assert isinstance(llm, ChatOllama)


def test_ensure_local_available_falls_back_to_installed(monkeypatch):
    monkeypatch.setattr(factory, "installed_ollama_models", lambda *a, **k: ["llama3.1:latest"])
    # requested model not installed -> fall back to an installed, tool-reliable model
    assert factory.ensure_local_available("qwen2.5") == "llama3.1"
    # installed model is returned unchanged
    assert factory.ensure_local_available("llama3.1") == "llama3.1"


def test_ensure_local_available_passthrough_when_ollama_down(monkeypatch):
    monkeypatch.setattr(factory, "installed_ollama_models", lambda *a, **k: [])
    # can't verify -> return the request unchanged (let it try / fail at invoke)
    assert factory.ensure_local_available("qwen3.5") == "qwen3.5"


def test_get_chat_model_cloud_without_key_raises(monkeypatch):
    monkeypatch.delenv("GROKFIT_MISSING_OPENAI", raising=False)
    profile = EXAMPLE_USER_PROFILE.model_copy(
        update={"llm_config": LLMConfig(provider="openai", model="gpt-4o-mini", api_key_ref="GROKFIT_MISSING_OPENAI")}
    )
    with pytest.warns(UserWarning):  # egress warning fires first
        with pytest.raises(RuntimeError, match="No API key"):
            factory.get_chat_model(profile)
