"""Nutrition plan models (structured-output target, mirrors WeeklyWorkoutPlan).

A NutritionPlan is daily macro/calorie targets plus per-day meals built from real foods
(each carrying its nutrient contribution). Foods are grounded in the local nutrition DB
(USDA FoodData Central) in later milestones; the model itself is generation-agnostic.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .plan import DEFAULT_DISCLAIMER


class DailyTargets(BaseModel):
    """Daily energy + macro targets (from Mifflin-St Jeor / calculate_macros)."""

    calories: float
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0


class FoodChoice(BaseModel):
    """A single food in a meal, with its (optional) nutrient contribution."""

    name: str
    grams: float | None = Field(default=None, description="Portion in grams")
    fdc_id: int | None = Field(default=None, description="USDA FoodData Central id, when grounded in the local DB")
    calories: float | None = None
    protein_g: float | None = None
    carbs_g: float | None = None
    fat_g: float | None = None

    model_config = {"extra": "ignore"}


class Meal(BaseModel):
    name: str = Field(description="e.g. Breakfast, Lunch, Snack")
    items: list[FoodChoice] = Field(default_factory=list)


class NutritionDay(BaseModel):
    day: str
    meals: list[Meal] = Field(default_factory=list)


class NutritionPlan(BaseModel):
    """A weekly (or daily-template) nutrition plan grounded in real foods."""

    athlete_name: str
    goal: str
    daily_targets: DailyTargets | None = None
    days: list[NutritionDay] = Field(default_factory=list)
    notes: str = ""
    disclaimer: str = Field(default=DEFAULT_DISCLAIMER)

    model_config = {"extra": "ignore"}
