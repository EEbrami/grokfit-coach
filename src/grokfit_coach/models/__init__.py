"""Domain models for coaching workflows (Pydantic v2).

All models used by the agent, RAG, tools, and plans live here.
"""

from .exercise import Exercise
from .nutrition import FoodItem
from .plan import WeeklyWorkoutPlan, WorkoutDay, ExercisePrescription, DEFAULT_DISCLAIMER
from .profile import UserProfile, EXAMPLE_USER_PROFILE, Goal, FitnessLevel

__all__ = [
    "UserProfile",
    "EXAMPLE_USER_PROFILE",
    "Goal",
    "FitnessLevel",
    "Exercise",
    "FoodItem",
    "WeeklyWorkoutPlan",
    "WorkoutDay",
    "ExercisePrescription",
    "DEFAULT_DISCLAIMER",
]
