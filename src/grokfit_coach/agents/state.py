"""LangGraph state definition for the single coach agent."""

from __future__ import annotations

from typing import Annotated, TypedDict

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

from grokfit_coach.models import UserProfile, WeeklyWorkoutPlan


class AgentState(TypedDict, total=False):
    """Shared state passed between nodes in the coach graph.

    messages: conversation history (uses LangGraph's add_messages reducer)
    profile: the current UserProfile (injected early, read by tools/prompt)
    plan: optional structured weekly plan produced during the turn
    safety_refusal: if set, the preflight decided this request is unsafe
    """

    messages: Annotated[list[BaseMessage], add_messages]
    profile: UserProfile | None
    plan: WeeklyWorkoutPlan | None
    safety_refusal: str | None
