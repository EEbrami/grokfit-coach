"""Pydantic v2 models for user profile (core personalization input to the agent)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .llm_config import LLMConfig

Goal = Literal["fat_loss", "muscle_gain", "strength", "general_health", "endurance", "body_recomposition"]
FitnessLevel = Literal["beginner", "novice", "intermediate", "advanced"]
DietaryPattern = Literal[
    "omnivore", "vegetarian", "vegan", "pescatarian", "keto", "paleo", "halal", "kosher", "other"
]
ActivityLevel = Literal["sedentary", "light", "moderate", "active", "very"]
CookingEffort = Literal["minimal", "moderate", "involved"]


class UserProfile(BaseModel):
    """Comprehensive user profile used by the coach agent for personalization."""

    name: str = Field(..., min_length=1, max_length=60, description="Display name")
    age: int = Field(..., ge=13, le=80, description="Age in years")
    gender: Literal["male", "female", "other", "prefer_not"] = "prefer_not"
    height_cm: float = Field(..., gt=100, lt=250)
    weight_kg: float = Field(..., gt=30, lt=300)

    goal: Goal = Field(..., description="Primary training goal")
    fitness_level: FitnessLevel = "novice"
    available_equipment: list[str] = Field(
        default_factory=list,
        description="What the user has access to, e.g. ['dumbbells', 'none', 'resistance_bands']",
    )
    dietary_restrictions: list[str] = Field(
        default_factory=list, description="e.g. ['vegan', 'gluten_free', 'lactose_intolerant']"
    )
    injuries_or_limitations: list[str] = Field(
        default_factory=list, description="e.g. ['knee pain', 'shoulder impingement']"
    )

    # --- Nutrition personalization (Phase 3) ---
    dietary_pattern: DietaryPattern = Field(default="omnivore", description="Overall eating pattern")
    food_preferences: list[str] = Field(
        default_factory=list, description="Liked foods/cuisines, used to bias suggestions"
    )
    disliked_foods: list[str] = Field(default_factory=list, description="Soft exclusions")
    allergens: list[str] = Field(
        default_factory=list,
        description="SAFETY-CRITICAL hard exclusions, e.g. ['peanut', 'shellfish']. Never recommended.",
    )
    meals_per_day: int = Field(3, ge=1, le=8)
    cooking_effort: CookingEffort = "moderate"
    activity_level: ActivityLevel = Field(default="moderate", description="Feeds TDEE / macro targets")

    workout_days_per_week: int = Field(3, ge=1, le=7)
    session_duration_min: int = Field(45, ge=15, le=120)

    # --- Model selection (Phase 3) ---
    llm_config: LLMConfig = Field(default_factory=LLMConfig, description="Local-by-default LLM provider/model")

    profile_version: int = Field(default=1, description="Schema version for migrations")

    model_config = {"extra": "ignore", "validate_default": True}

    @field_validator(
        "available_equipment",
        "dietary_restrictions",
        "injuries_or_limitations",
        "food_preferences",
        "disliked_foods",
        "allergens",
        mode="before",
    )
    @classmethod
    def _normalize_lists(cls, v):
        if v is None:
            return []
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v

    @model_validator(mode="after")
    def _sanity_checks(self) -> UserProfile:
        # Very basic cross-field sanity (more can be added later)
        if self.weight_kg / ((self.height_cm / 100) ** 2) > 60:
            # Extremely high BMI — still allow but we could warn in future
            pass
        return self


# Convenience example for demos, tests, and the terminal CLI
EXAMPLE_USER_PROFILE = UserProfile(
    name="Abraham",
    age=30,
    gender="male",
    height_cm=178.0,
    weight_kg=93.0,
    goal="fat_loss",
    fitness_level="intermediate",
    available_equipment=["dumbbells", "none", "resistance_bands"],
    dietary_restrictions=[],
    injuries_or_limitations=[],
    workout_days_per_week=4,
    session_duration_min=50,
)
