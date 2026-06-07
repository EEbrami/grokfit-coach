"""Direct tests for the three core tools (with minimal mocking where needed)."""

from __future__ import annotations

from unittest.mock import patch

from grokfit_coach.tools import calculate_macros, lookup_nutrition, search_exercises


def test_calculate_macros_pure_function():
    out = calculate_macros.invoke(
        {"age": 30, "gender": "male", "weight_kg": 80, "height_cm": 180, "activity_level": "moderate", "goal": "fat_loss"}
    )
    assert "kcal" in out
    assert "Protein" in out or "protein" in out.lower()


def test_calculate_macros_recomposition():
    out = calculate_macros.invoke(
        {
            "age": 30,
            "gender": "male",
            "weight_kg": 80,
            "height_cm": 180,
            "activity_level": "moderate",
            "goal": "body_recomposition",
        }
    )
    assert "kcal" in out
    assert "Protein" in out or "protein" in out.lower()
    assert "simultaneous muscle gain" in out



def test_lookup_nutrition_uses_curated_data():
    out = lookup_nutrition.invoke({"food_query": "chicken"})
    assert "Chicken" in out
    assert "kcal" in out or "protein" in out.lower()


def test_search_exercises_uses_retriever(monkeypatch):
    # We don't want to depend on a real index in this unit test
    fake_results = [
        type("E", (), {"name": "Push-up", "equipment": ["none"], "muscle_groups": ["chest"], "description": "Bodyweight push", "difficulty": "beginner"})(),
        type("E", (), {"name": "Dumbbell Bench Press", "equipment": ["dumbbells"], "muscle_groups": ["chest"], "description": "Chest press", "difficulty": "novice"})(),
    ]

    with patch("grokfit_coach.tools.exercise.retrieve_exercises", return_value=fake_results):
        out = search_exercises.invoke({"query": "chest dumbbell"})
        assert "Push-up" in out or "Dumbbell" in out
        assert "knowledge base" in out
