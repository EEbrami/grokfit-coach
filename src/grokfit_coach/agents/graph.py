"""Single LangGraph coach agent.

Safety preflight + tool-using loop (via ToolNode) + basic plan generation path.
Designed to be the foundation for future multi-agent work while staying simple for Phase 1.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from grokfit_coach.agents.prompts import PLAN_GENERATION_PROMPT, SYSTEM_PROMPT
from grokfit_coach.agents.state import AgentState
from grokfit_coach.llm import get_chat_model
from grokfit_coach.models import (
    ExercisePrescription,
    UserProfile,
    WeeklyWorkoutPlan,
    WorkoutDay,
)
from grokfit_coach.safety.guardrails import (
    apply_output_guardrails,
    is_unsafe_request,
)
from grokfit_coach.tools import TOOLS


def _get_llm(settings: Any | None = None):
    """Backward-compatible wrapper around the provider factory (local Ollama by default)."""
    return get_chat_model(None, settings)


def safety_preflight(state: AgentState) -> AgentState:
    """Hard stop for obviously unsafe requests before any LLM call."""
    # Look at the latest human message
    last_human = None
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            last_human = m.content
            break
    if last_human:
        reason = is_unsafe_request(str(last_human))
        if reason:
            state["safety_refusal"] = reason
    return state


def prepare_context(state: AgentState) -> AgentState:
    """Inject the system prompt and a compact profile summary (if present)."""
    profile: UserProfile | None = state.get("profile")
    messages: list[BaseMessage] = state.get("messages", [])

    profile_text = ""
    if profile:
        profile_text = (
            f"\nCurrent user profile:\n"
            f"- Name: {profile.name}, Goal: {profile.goal}, Level: {profile.fitness_level}\n"
            f"- Equipment: {profile.available_equipment or 'minimal/none'}\n"
            f"- Restrictions / injuries: {profile.dietary_restrictions + profile.injuries_or_limitations}\n"
            f"- Training days: {profile.workout_days_per_week}, typical session: {profile.session_duration_min} min\n"
        )

    # Only add the system message once per turn if not already present
    has_system = any(isinstance(m, SystemMessage) for m in messages)
    if not has_system:
        sys = SystemMessage(content=SYSTEM_PROMPT + profile_text)
        messages = [sys] + messages
        state["messages"] = messages
    return state


def call_model(state: AgentState) -> AgentState:
    """Call the LLM (with tools bound)."""
    if state.get("safety_refusal"):
        # Short-circuit; the refusal node will handle output
        return state

    llm = get_chat_model(state.get("profile"))
    llm_with_tools = llm.bind_tools(TOOLS)

    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    state["messages"] = messages + [response]
    return state


def should_use_tools(state: AgentState) -> Literal["tools", "maybe_plan", "respond"]:
    if state.get("safety_refusal"):
        return "respond"
    last = state["messages"][-1] if state.get("messages") else None
    if isinstance(last, AIMessage) and getattr(last, "tool_calls", None):
        return "tools"
    # Very lightweight plan trigger (kept basic per Phase 1 guidance)
    last_human = ""
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            last_human = str(m.content).lower()
            break
    if any(word in last_human for word in ["plan", "weekly", "schedule", "workout plan"]):
        return "maybe_plan"
    return "respond"


def maybe_generate_plan(state: AgentState) -> AgentState:
    """Improved plan generation for Phase 2.

    - Uses profile-aware RAG retrieval + client-side filtering for equipment/injuries.
    - Richer prompt with explicit rules (from PLAN_GENERATION_PROMPT).
    - Post-validation: keeps only exercises whose names are in the retrieved set.
    - Robust fallback: if LLM fails or produces invalid plan, builds a safe deterministic
      plan by distributing the filtered retrieved exercises across the requested days.
    """
    profile: UserProfile | None = state.get("profile")
    if not profile:
        return state

    # Get context from conversation or default
    last_query = ""
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            last_query = str(m.content)
            break

    from grokfit_coach.rag.retriever import retrieve_exercises

    # Retrieve more candidates
    candidates = retrieve_exercises(last_query or "balanced full body workout", k=10)

    # Client-side filter for basic compatibility (equipment + avoid obvious injury aggravators)
    user_equip = set(e.lower() for e in (profile.available_equipment or []))
    injury_keywords = [kw.lower() for kw in (profile.injuries_or_limitations or [])]

    filtered = []
    for ex in candidates:
        ex_equip = set(e.lower() for e in (ex.equipment or []))
        # Allow if user has the gear OR the exercise is bodyweight/none
        compatible_equip = bool(user_equip & ex_equip) or not ex_equip or "none" in ex_equip or "bodyweight" in ex_equip
        # Crude injury avoidance (real safety is in guardrails + prompt)
        aggravates = any(kw in " ".join((ex.contraindications or []) + [ex.description]).lower() for kw in injury_keywords)
        if compatible_equip and not aggravates:
            filtered.append(ex)

    if not filtered:
        filtered = candidates[:6]  # fallback to whatever we got

    ex_names = [ex.name for ex in filtered]
    ex_list_str = "\n".join(f"- {ex.name}: {ex.description[:80]} (equip: {', '.join(ex.equipment or ['bodyweight'])})" for ex in filtered)

    llm = get_chat_model(profile)
    structured_llm = llm.with_structured_output(WeeklyWorkoutPlan)

    prompt = PLAN_GENERATION_PROMPT.format(
        workout_days_per_week=profile.workout_days_per_week,
        fitness_level=profile.fitness_level,
        goal=profile.goal,
        name=profile.name,
        available_equipment=profile.available_equipment or "bodyweight / minimal",
        injuries_or_limitations=profile.injuries_or_limitations or "none",
        session_duration_min=profile.session_duration_min,
        exercise_list=ex_list_str,
    )

    plan: WeeklyWorkoutPlan | None = None
    try:
        candidate_plan: WeeklyWorkoutPlan = structured_llm.invoke([HumanMessage(content=prompt)])
        # Post-validation: keep only exercises that were in our filtered list
        valid_names = set(ex_names)
        cleaned_days = []
        for day in candidate_plan.days:
            cleaned_exs = [ex for ex in day.exercises if ex.name in valid_names]
            if cleaned_exs:
                cleaned_days.append(type(day)(day=day.day, focus=day.focus, exercises=cleaned_exs))
        if cleaned_days:
            plan = WeeklyWorkoutPlan(
                athlete_name=candidate_plan.athlete_name or profile.name,
                goal=candidate_plan.goal or profile.goal,
                days=cleaned_days,
                notes=candidate_plan.notes or "",
                disclaimer=candidate_plan.disclaimer,
            )
    except Exception:
        plan = None

    if plan is None or not plan.days:
        # Deterministic safe fallback using retrieved exercises
        days = []
        per_day = max(3, min(6, len(filtered) // max(1, profile.workout_days_per_week)))
        for i in range(profile.workout_days_per_week):
            start = (i * per_day) % len(filtered)
            day_exs = filtered[start : start + per_day]
            if not day_exs:
                day_exs = filtered[:per_day]
            ex_prescriptions = [
                ExercisePrescription(
                    name=ex.name,
                    sets="3",
                    reps="8-12",
                    notes=ex.cues[:60] if ex.cues else None,
                )
                for ex in day_exs
            ]
            days.append(
                WorkoutDay(
                    day=f"Day {i+1}",
                    focus="Full body / balanced",
                    exercises=ex_prescriptions,
                )
            )
        plan = WeeklyWorkoutPlan(
            athlete_name=profile.name,
            goal=profile.goal,
            days=days,
            notes="Fallback plan generated from available knowledge base exercises. Adjust as needed.",
        )

    # Final disclaimer enforcement
    from grokfit_coach.safety.guardrails import DISCLAIMER
    if not plan.disclaimer or "IMPORTANT" not in plan.disclaimer:
        plan.disclaimer = DISCLAIMER

    state["plan"] = plan
    return state


def respond(state: AgentState) -> AgentState:
    """Final response node. Applies output guardrails (disclaimer)."""

    if state.get("safety_refusal"):
        refusal = state["safety_refusal"]
        state["messages"] = state.get("messages", []) + [
            AIMessage(content=apply_output_guardrails(refusal))
        ]
        return state

    # Apply guardrails to the last AI message if present
    messages = state.get("messages", [])
    if messages:
        last = messages[-1]
        if isinstance(last, AIMessage):
            safe_content = apply_output_guardrails(last.content)
            messages[-1] = AIMessage(content=safe_content, tool_calls=getattr(last, "tool_calls", None))
    state["messages"] = messages
    return state


def build_coach_graph():
    """Build and return the compiled coach agent graph."""
    graph = StateGraph(AgentState)

    graph.add_node("safety_preflight", safety_preflight)
    graph.add_node("prepare_context", prepare_context)
    graph.add_node("agent", call_model)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("maybe_plan", maybe_generate_plan)
    graph.add_node("respond", respond)

    graph.set_entry_point("safety_preflight")
    graph.add_edge("safety_preflight", "prepare_context")
    graph.add_edge("prepare_context", "agent")

    graph.add_conditional_edges(
        "agent",
        should_use_tools,
        {
            "tools": "tools",
            "maybe_plan": "maybe_plan",
            "respond": "respond",
        },
    )

    graph.add_edge("tools", "agent")  # ReAct loop
    graph.add_edge("maybe_plan", "respond")
    graph.add_edge("respond", END)

    return graph.compile()


# Convenience for CLI and tests
def invoke_coach(
    profile: UserProfile,
    user_message: str,
    history: list[BaseMessage] | None = None,
) -> AgentState:
    """Simple helper to run one turn of the coach."""
    graph = build_coach_graph()
    init: AgentState = {
        "messages": (history or []) + [HumanMessage(content=user_message)],
        "profile": profile,
        "plan": None,
        "safety_refusal": None,
    }
    return graph.invoke(init)
