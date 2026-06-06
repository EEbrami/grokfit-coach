"""Single LangGraph coach agent.

Safety preflight + tool-using loop (via ToolNode) + basic plan generation path.
Designed to be the foundation for future multi-agent work while staying simple for Phase 1.
"""

from __future__ import annotations

from typing import Any, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from grokfit_coach.agents.prompts import SYSTEM_PROMPT
from grokfit_coach.agents.state import AgentState
from grokfit_coach.config.settings import get_settings
from grokfit_coach.models import UserProfile, WeeklyWorkoutPlan
from grokfit_coach.safety.guardrails import (
    apply_output_guardrails,
    is_unsafe_request,
)
from grokfit_coach.tools import TOOLS


def _get_llm(settings: Any | None = None):
    s = settings or get_settings()
    return ChatOllama(model=s.ollama_model, base_url=s.ollama_host, temperature=0.2)


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

    llm = _get_llm()
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
    """Basic structured plan path (intentionally simple for Phase 1).

    If the user asked for a plan, we do a quick RAG lookup for suitable exercises
    and ask the LLM for a structured WeeklyWorkoutPlan using with_structured_output.
    This is "basic" on purpose.
    """
    profile: UserProfile | None = state.get("profile")
    if not profile:
        return state

    # Quick relevant exercises from RAG (using the last user query if possible)
    last_query = ""
    for m in reversed(state.get("messages", [])):
        if isinstance(m, HumanMessage):
            last_query = str(m.content)
            break

    from grokfit_coach.rag.retriever import retrieve_exercises

    relevant = retrieve_exercises(last_query or "full body beginner", k=6)
    ex_names = [ex.name for ex in relevant]

    llm = _get_llm()
    structured_llm = llm.with_structured_output(WeeklyWorkoutPlan)

    prompt = (
        f"Create a simple {profile.workout_days_per_week}-day weekly workout plan "
        f"for {profile.name} (goal: {profile.goal}, level: {profile.fitness_level}). "
        f"Available equipment: {profile.available_equipment or 'bodyweight/minimal'}. "
        f"Respect any injuries: {profile.injuries_or_limitations}. "
        f"Use only exercises from this list when possible: {ex_names}. "
        f"Keep it realistic and safe. Output a valid WeeklyWorkoutPlan."
    )

    try:
        plan: WeeklyWorkoutPlan = structured_llm.invoke([HumanMessage(content=prompt)])
        # ensure disclaimer
        if not plan.disclaimer or "IMPORTANT" not in plan.disclaimer:
            from grokfit_coach.safety.guardrails import DISCLAIMER

            plan.disclaimer = DISCLAIMER
        state["plan"] = plan
    except Exception:
        # If structured output fails on the local model, we still let the normal respond path run
        state["plan"] = None
    return state


def respond(state: AgentState) -> AgentState:
    """Final response node. Applies output guardrails (disclaimer)."""
    from grokfit_coach.safety.guardrails import apply_output_guardrails

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
