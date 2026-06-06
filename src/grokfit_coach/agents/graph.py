"""LangGraph scaffold for future multi-agent orchestration."""

from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, StateGraph


class CoachState(TypedDict):
    """Shared state across fitness coaching agents."""

    user_message: str


def route_user_message(state: CoachState) -> CoachState:
    """Initial router node placeholder."""
    return state


def build_graph() -> StateGraph:
    """Create a minimal LangGraph state graph scaffold."""

    graph = StateGraph(CoachState)
    graph.add_node("router", route_user_message)
    graph.set_entry_point("router")
    graph.add_edge("router", END)
    return graph
