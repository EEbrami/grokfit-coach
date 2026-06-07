"""Tests for deterministic, allergen-safe nutrition plan generation (M4)."""

from __future__ import annotations

from grokfit_coach.models import EXAMPLE_USER_PROFILE
from grokfit_coach.nutrition import food_db, meal_planner


def test_compute_targets_calorie_floor_and_macros():
    t = meal_planner.compute_daily_targets(EXAMPLE_USER_PROFILE)
    assert t.calories >= 1200  # safety floor
    assert t.protein_g > 0 and t.carbs_g >= 0 and t.fat_g > 0


def test_nutrition_plan_respects_allergens_and_diet(tmp_path):
    db = tmp_path / "n.sqlite"
    food_db.build_from_seed(db_path=db)
    profile = EXAMPLE_USER_PROFILE.model_copy(
        update={"allergens": ["milk", "tree_nut"], "dietary_pattern": "omnivore", "meals_per_day": 3}
    )
    plan = meal_planner.generate_nutrition_plan(profile, db_path=db)

    assert plan.daily_targets and plan.daily_targets.calories >= 1200
    assert plan.days and plan.days[0].meals, "should produce at least one meal"

    names = " ".join(
        it.name.lower() for d in plan.days for m in d.meals for it in m.items
    )
    # allergen foods must never appear
    assert "yogurt" not in names and "milk" not in names and "almond" not in names
    # every food item carries real macros
    items = [it for d in plan.days for m in d.meals for it in m.items]
    assert items and all(it.calories is not None for it in items)


def test_nutrition_plan_vegan_excludes_animal_products(tmp_path):
    db = tmp_path / "n.sqlite"
    food_db.build_from_seed(db_path=db)
    profile = EXAMPLE_USER_PROFILE.model_copy(update={"dietary_pattern": "vegan", "allergens": []})
    plan = meal_planner.generate_nutrition_plan(profile, db_path=db)
    names = " ".join(it.name.lower() for d in plan.days for m in d.meals for it in m.items)
    for animal in ("chicken", "salmon", "egg", "beef", "yogurt", "shrimp", "milk"):
        assert animal not in names, f"{animal} should not be in a vegan plan"
