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

    # Retrieve a broad candidate set, then filter for equipment + injuries.
    candidates = retrieve_exercises(last_query or "balanced full body workout", k=24)

    user_equip = {e.lower() for e in (profile.available_equipment or [])}
    injury_keywords = [kw.lower() for kw in (profile.injuries_or_limitations or [])]

    def _compatible(ex) -> bool:
        ex_equip = {e.lower() for e in (ex.equipment or [])}
        ok_equip = bool(user_equip & ex_equip) or not ex_equip or "none" in ex_equip or "bodyweight" in ex_equip
        aggravates = any(
            kw in " ".join((ex.contraindications or []) + [ex.description]).lower() for kw in injury_keywords
        )
        return ok_equip and not aggravates

    # Compatible, de-duplicated exercise pool (the safe set the plan is built from).
    pool: list = []
    seen_names: set = set()
    for ex in [e for e in candidates if _compatible(e)] or candidates[:8]:
        if ex.name not in seen_names:
            seen_names.add(ex.name)
            pool.append(ex)

    days_target = max(1, min(7, profile.workout_days_per_week))
    per_day = 5  # aim for ~5 exercises/day (clamped to 6)
    sets_reps = {
        "fat_loss": ("3", "12-15"),
        "endurance": ("2-3", "15-20"),
        "muscle_gain": ("3-4", "8-12"),
        "body_recomposition": ("3", "10-12"),
        "strength": ("4", "4-6"),
        "general_health": ("3", "10-12"),
    }.get(profile.goal, ("3", "10-12"))

    def _norm(s: str) -> str:
        return "".join(ch for ch in s.lower() if ch.isalnum())

    by_norm = {_norm(ex.name): ex for ex in pool}

    def _match(name: str):
        # fuzzy match an LLM-suggested name back to a real pool exercise (avoids over-stripping)
        n = _norm(name)
        if n in by_norm:
            return by_norm[n]
        for key, ex in by_norm.items():
            if n and (n in key or key in n):
                return ex
        return None

    def _prescribe(ex) -> ExercisePrescription:
        return ExercisePrescription(
            name=ex.name,
            sets=sets_reps[0],
            reps=sets_reps[1],
            notes=(ex.cues[:60] if getattr(ex, "cues", "") else None),
        )

    # Ask the LLM for structure (day focuses + selection); tolerate any failure.
    ex_list_str = "\n".join(
        f"- {ex.name}: {ex.description[:80]} (equip: {', '.join(ex.equipment or ['bodyweight'])})" for ex in pool
    )
    llm_days: list = []
    try:
        prompt = PLAN_GENERATION_PROMPT.format(
            workout_days_per_week=days_target,
            fitness_level=profile.fitness_level,
            goal=profile.goal,
            name=profile.name,
            available_equipment=profile.available_equipment or "bodyweight / minimal",
            injuries_or_limitations=profile.injuries_or_limitations or "none",
            session_duration_min=profile.session_duration_min,
            exercise_list=ex_list_str,
        )
        llm = get_chat_model(profile)
        candidate_plan = llm.with_structured_output(WeeklyWorkoutPlan).invoke([HumanMessage(content=prompt)])
        llm_days = list(candidate_plan.days or [])
    except Exception:
        llm_days = []

    default_focuses = ["Full Body", "Upper Body", "Lower Body", "Push", "Pull", "Core & Conditioning", "Full Body"]

    # Assemble exactly days_target days, each filled to ~per_day exercises from the pool.
    days: list[WorkoutDay] = []
    cursor = 0
    for i in range(days_target):
        focus = default_focuses[i % len(default_focuses)]
        chosen: list = []
        chosen_names: set = set()

        if i < len(llm_days):
            ld = llm_days[i]
            if getattr(ld, "focus", ""):
                focus = ld.focus
            for pres in getattr(ld, "exercises", []) or []:
                m = _match(getattr(pres, "name", ""))
                if m and m.name not in chosen_names:
                    chosen.append(m)
                    chosen_names.add(m.name)

        guard = 0
        while len(chosen) < per_day and pool and guard < len(pool) * 2:
            ex = pool[cursor % len(pool)]
            cursor += 1
            guard += 1
            if ex.name not in chosen_names:
                chosen.append(ex)
                chosen_names.add(ex.name)

        days.append(
            WorkoutDay(day=f"Day {i+1}", focus=focus, exercises=[_prescribe(ex) for ex in chosen[:6]])
        )

    from grokfit_coach.safety.guardrails import DISCLAIMER

    plan = WeeklyWorkoutPlan(
        athlete_name=profile.name,
        goal=profile.goal,
        days=days,
        notes=(
            f"{days_target}-day plan for {profile.goal} using your available equipment. "
            f"Progressive overload: add reps or weight when the top of the rep range feels easy."
        ),
        disclaimer=DISCLAIMER,
    )
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


def generate_workout_plan(profile: UserProfile) -> WeeklyWorkoutPlan | None:
    """Generate a workout plan directly and robustly.

    Runs only the plan node (with its deterministic fallback), bypassing the conversational
    chat node — so a missing or failing local model never blocks plan generation.
    """
    state: AgentState = {
        "messages": [HumanMessage(content="Create a weekly workout plan based on my profile.")],
        "profile": profile,
        "plan": None,
        "safety_refusal": None,
    }
    return maybe_generate_plan(state).get("plan")
