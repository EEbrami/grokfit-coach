"""Basic plan models. WeeklyWorkoutPlan is intentionally simple for Phase 1."""

from __future__ import annotations

from pydantic import BaseModel, Field

# Basic disclaimer used by plans (will be aligned with safety/guardrails in later steps)
DEFAULT_DISCLAIMER: str = (
    "IMPORTANT DISCLAIMER: This is general educational information only and is NOT a "
    "substitute for professional medical, nutritional, or fitness advice. Consult a "
    "qualified healthcare provider or certified trainer before beginning any new "
    "exercise or diet program. Stop immediately if you experience pain or discomfort."
)


class ExercisePrescription(BaseModel):
    """One exercise in a workout day (kept minimal for Phase 1)."""

    name: str
    sets: str | None = None
    reps: str | None = None
    notes: str | None = None


class WorkoutDay(BaseModel):
    day: str
    focus: str
    exercises: list[ExercisePrescription] = Field(default_factory=list)


class WeeklyWorkoutPlan(BaseModel):
    """A simple weekly workout plan. Structured output target for the agent."""

    athlete_name: str
    goal: str
    days: list[WorkoutDay] = Field(default_factory=list)
    notes: str = ""
    disclaimer: str = Field(default=DEFAULT_DISCLAIMER)

    model_config = {"extra": "ignore"}
