"""Domain models for coaching workflows (Pydantic v2).

All models used by the agent, RAG, tools, and plans live here.
"""

from .exercise import Exercise
from .nutrition import FoodItem
from .plan import DEFAULT_DISCLAIMER, ExercisePrescription, WeeklyWorkoutPlan, WorkoutDay
from .profile import EXAMPLE_USER_PROFILE, FitnessLevel, Goal, UserProfile

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
