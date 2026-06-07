"""Domain models for coaching workflows (Pydantic v2).

All models used by the agent, RAG, tools, and plans live here.
"""

from .exercise import Exercise
from .llm_config import LLMConfig, LLMProvider
from .nutrition import FoodItem
from .nutrition_plan import DailyTargets, FoodChoice, Meal, NutritionDay, NutritionPlan
from .plan import DEFAULT_DISCLAIMER, ExercisePrescription, WeeklyWorkoutPlan, WorkoutDay
from .profile import (
    EXAMPLE_USER_PROFILE,
    ActivityLevel,
    CookingEffort,
    DietaryPattern,
    FitnessLevel,
    Goal,
    UserProfile,
)
from .tracking import EventType, TrackingEvent

__all__ = [
    "UserProfile",
    "EXAMPLE_USER_PROFILE",
    "Goal",
    "FitnessLevel",
    "DietaryPattern",
    "ActivityLevel",
    "CookingEffort",
    "Exercise",
    "FoodItem",
    "WeeklyWorkoutPlan",
    "WorkoutDay",
    "ExercisePrescription",
    "DEFAULT_DISCLAIMER",
    "LLMConfig",
    "LLMProvider",
    "NutritionPlan",
    "NutritionDay",
    "Meal",
    "FoodChoice",
    "DailyTargets",
    "TrackingEvent",
    "EventType",
]
