"""Tests for the LangGraph coach agent (compile + safety + respond nodes).

The full ReAct + tool loop is exercised manually and via the CLI when Ollama is available.
Unit tests here focus on the parts that are easy to test without a live model.
"""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage

from grokfit_coach.agents.graph import build_coach_graph
from grokfit_coach.agents.state import AgentState
from grokfit_coach.models import EXAMPLE_USER_PROFILE


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


def test_maybe_generate_plan_fills_all_days(monkeypatch):
    """Every requested day must be present and filled (>=4 exercises), even with no LLM."""
    from grokfit_coach.agents import graph
    from grokfit_coach.models import EXAMPLE_USER_PROFILE, Exercise

    pool = [
        Exercise(id=f"ex_{i}", name=f"Move {i}", description="bodyweight move", equipment=["none"], muscle_groups=["full"])
        for i in range(8)
    ]

    def _boom(*a, **k):
        raise RuntimeError("no llm in test")

    monkeypatch.setattr("grokfit_coach.rag.retriever.retrieve_exercises", lambda *a, **k: pool)
    monkeypatch.setattr(graph, "get_chat_model", _boom)  # force the deterministic assembly path

    profile = EXAMPLE_USER_PROFILE.model_copy(update={"workout_days_per_week": 4})
    state: AgentState = {
        "messages": [HumanMessage(content="create a weekly workout plan")],
        "profile": profile,
        "plan": None,
        "safety_refusal": None,
    }
    out = graph.maybe_generate_plan(state)
    plan = out["plan"]
    assert plan is not None
    assert len(plan.days) == 4
    assert all(len(d.exercises) >= 4 for d in plan.days)
    assert all(ex.sets and ex.reps for d in plan.days for ex in d.exercises)


def test_maybe_generate_plan_fallback():
    from unittest.mock import patch

    from grokfit_coach.agents.graph import maybe_generate_plan
    from grokfit_coach.models import Exercise, WeeklyWorkoutPlan

    mock_exercises = [
        Exercise(id="ex_1", name="Pushups", description="Push up", equipment=["none"], muscle_groups=["chest"]),
        Exercise(id="ex_2", name="Squats", description="Squat down", equipment=["none"], muscle_groups=["legs"]),
    ]

    with patch("grokfit_coach.rag.retriever.retrieve_exercises", return_value=mock_exercises):
        state: AgentState = {
            "messages": [HumanMessage(content="create a weekly workout plan")],
            "profile": EXAMPLE_USER_PROFILE,
            "plan": None,
            "safety_refusal": None,
        }
        out = maybe_generate_plan(state)
        plan = out.get("plan")
        assert plan is not None
        assert isinstance(plan, WeeklyWorkoutPlan)
        assert len(plan.days) == EXAMPLE_USER_PROFILE.workout_days_per_week
        assert plan.athlete_name == EXAMPLE_USER_PROFILE.name


