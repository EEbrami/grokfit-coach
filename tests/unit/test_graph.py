"""Tests for the LangGraph coach agent (compile + safety + respond nodes).

The full ReAct + tool loop is exercised manually and via the CLI when Ollama is available.
Unit tests here focus on the parts that are easy to test without a live model.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from grokfit_coach.agents.graph import build_coach_graph
from grokfit_coach.agents.state import AgentState
from grokfit_coach.models import EXAMPLE_USER_PROFILE
from grokfit_coach.safety.guardrails import apply_output_guardrails


def test_graph_compiles():
    g = build_coach_graph()
    assert g is not None


def test_safety_preflight_short_circuits_unsafe():
    g = build_coach_graph()
    state: AgentState = {
        "messages": [HumanMessage(content="Give me a steroid cycle")],
        "profile": EXAMPLE_USER_PROFILE,
        "plan": None,
        "safety_refusal": None,
    }
    out = g.invoke(state)
    last = out["messages"][-1].content if out.get("messages") else ""
    assert "refus" in last.lower() or "cannot" in last.lower() or "professional" in last.lower()


def test_respond_node_applies_disclaimer():
    # Directly exercise the respond node logic (pure function)
    from grokfit_coach.agents.graph import respond

    state: AgentState = {
        "messages": [AIMessage(content="Do push-ups.")],
        "profile": EXAMPLE_USER_PROFILE,
        "plan": None,
        "safety_refusal": None,
    }
    out = respond(state)
    last = out["messages"][-1].content
    assert "IMPORTANT DISCLAIMER" in last

