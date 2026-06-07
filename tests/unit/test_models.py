"""Unit tests for Pydantic data models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from grokfit_coach.models import (
    EXAMPLE_USER_PROFILE,
    Exercise,
    ExercisePrescription,
    FoodItem,
    UserProfile,
    WeeklyWorkoutPlan,
    WorkoutDay,
)


def test_example_profile_is_valid():
    p = EXAMPLE_USER_PROFILE
    assert p.name
    assert p.age >= 13
    assert p.goal in {"fat_loss", "muscle_gain", "strength", "general_health", "endurance"}


def test_user_profile_validation_errors():
    with pytest.raises(ValidationError):
        UserProfile(name="X", age=10, height_cm=170, weight_kg=70, goal="fat_loss")  # age too low

    with pytest.raises(ValidationError):
        UserProfile(name="X", age=30, height_cm=170, weight_kg=70, goal="impossible_goal")


def test_user_profile_list_normalization():
    p = UserProfile(
        name="Test",
        age=30,
        height_cm=170,
        weight_kg=70,
        goal="general_health",
        available_equipment="dumbbells, none",
    )
    assert p.available_equipment == ["dumbbells", "none"]


def test_exercise_and_food_models():
    ex = Exercise(id="ex_t", name="Test Move", description="A test move", muscle_groups=["core"])
    assert ex.id == "ex_t"

    food = FoodItem(name="Test Food", calories=100, protein_g=10, serving_desc="100g")
    assert food.protein_g == 10


def test_weekly_workout_plan_basic():
    day = WorkoutDay(
        day="Day 1",
        focus="Full Body",
        exercises=[ExercisePrescription(name="Push-up", sets="3", reps="8-12")],
    )
    plan = WeeklyWorkoutPlan(athlete_name="Test", goal="general_health", days=[day])
    assert len(plan.days) == 1
    assert "IMPORTANT DISCLAIMER" in plan.disclaimer
