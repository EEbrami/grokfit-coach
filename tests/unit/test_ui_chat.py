"""Hermetic test for the Gradio chat format (Gradio 6 uses the messages/dict format)."""

from __future__ import annotations

from unittest.mock import patch

from grokfit_coach.ui.app import chat_response


def test_chat_response_returns_messages_format():
    """chat_response must return Gradio-6 messages dicts ({'role','content'}), not tuples."""
    fake_result = {"messages": [type("M", (), {"content": "Do push-ups."})()], "plan": None}
    with patch("grokfit_coach.ui.app.invoke_coach", return_value=fake_result):
        history, _ = chat_response("hi", [], None)
    assert isinstance(history, list) and len(history) == 2
    assert history[0]["role"] == "user" and history[0]["content"] == "hi"
    assert history[1]["role"] == "assistant"
    assert "push-ups" in history[1]["content"]


def test_chat_response_error_path_is_messages_format():
    """Even on agent error, history stays in messages format (no tuple leakage)."""
    with patch("grokfit_coach.ui.app.invoke_coach", side_effect=RuntimeError("ollama down")):
        history, _ = chat_response("hi", [], None)
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant" and "Error" in history[1]["content"]
