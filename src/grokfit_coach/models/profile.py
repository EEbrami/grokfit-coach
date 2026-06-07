"""Pydantic v2 models for user profile (core personalization input to the agent)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Goal = Literal["fat_loss", "muscle_gain", "strength", "general_health", "endurance", "body_recomposition"]
FitnessLevel = Literal["beginner", "novice", "intermediate", "advanced"]


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

    workout_days_per_week: int = Field(3, ge=1, le=7)
    session_duration_min: int = Field(45, ge=15, le=120)

    model_config = {"extra": "ignore", "validate_default": True}

    @field_validator("available_equipment", "dietary_restrictions", "injuries_or_limitations", mode="before")
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
    name="Alex Rivera",
    age=34,
    gender="male",
    height_cm=178.0,
    weight_kg=82.0,
    goal="fat_loss",
    fitness_level="intermediate",
    available_equipment=["dumbbells", "none", "resistance_bands"],
    dietary_restrictions=["none"],
    injuries_or_limitations=[],
    workout_days_per_week=4,
    session_duration_min=50,
)
