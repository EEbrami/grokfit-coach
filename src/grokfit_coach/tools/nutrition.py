"""Nutrition lookup and macro calculation tools."""

from __future__ import annotations

from langchain_core.tools import tool

from grokfit_coach.config.settings import get_settings
from grokfit_coach.models.nutrition import FoodItem


def _load_foods() -> list[FoodItem]:
    # Lazy load to avoid import-time side effects
    import json

    s = get_settings()
    path = s.seeds_dir / "foods.json"
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    return [FoodItem.model_validate(item) for item in raw]


@tool("lookup_nutrition", return_direct=False)
def lookup_nutrition(food_query: str) -> str:
    """Look up nutrition information (per 100 g) for a common food.

    Use when the user asks about protein, calories, or macros for specific foods
    (chicken, eggs, oats, yogurt, etc.). Data comes from the local nutrition database
    (USDA FoodData Central-derived); falls back to a small curated set if unavailable.
    """
    matches: list = []
    try:
        from grokfit_coach.nutrition import food_db

        matches = food_db.search_foods(food_query, limit=3)
    except Exception:
        matches = []

    if not matches:
        # fallback to the small curated list
        foods = _load_foods()
        q = food_query.lower()
        matches = [f for f in foods if q in f.name.lower()][:3] or foods[:3]

    lines = []
    for f in matches[:3]:
        allergens = getattr(f, "allergen_flags", None) or []
        allergen_note = f" [allergens: {', '.join(allergens)}]" if allergens else ""
        lines.append(
            f"{f.name} ({f.serving_desc}): ~{f.calories:.0f} kcal, "
            f"P {f.protein_g:.1f}g / C {f.carbs_g:.1f}g / F {f.fat_g:.1f}g{allergen_note}"
        )
    return (
        "Approximate per-100g nutrition (USDA FoodData Central-derived; general guidance only):\n"
        + "\n".join(lines)
    )


@tool("calculate_macros", return_direct=False)
def calculate_macros(
    age: int,
    gender: str,
    weight_kg: float,
    height_cm: float,
    activity_level: str = "moderate",
    goal: str = "general_health",
) -> str:
    """Estimate daily calorie target and rough macro ranges based on the Mifflin-St Jeor equation.

    activity_level: sedentary | light | moderate | active | very
    goal: fat_loss | muscle_gain | strength | general_health | endurance
    """
    # BMR
    if gender.lower() in ("male", "m"):
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    mult = {
        "sedentary": 1.2,
        "light": 1.375,
        "moderate": 1.55,
        "active": 1.725,
        "very": 1.9,
    }.get(activity_level.lower(), 1.55)

    tdee = bmr * mult

    if goal == "fat_loss":
        target = tdee - 400
        protein_g = weight_kg * 2.0
        note = "Modest deficit for fat loss."
    elif goal == "body_recomposition":
        target = tdee - 150
        protein_g = weight_kg * 2.2
        note = "Slight deficit with high protein for simultaneous muscle gain and fat loss."
    elif goal in ("muscle_gain", "strength"):
        target = tdee + 300
        protein_g = weight_kg * 1.8
        note = "Surplus for muscle/strength building."
    else:
        target = tdee
        protein_g = weight_kg * 1.6
        note = "Maintenance / general health."

    carbs_g = (target * 0.45) / 4
    fat_g = (target * 0.25) / 9

    return (
        f"Estimated TDEE ~{tdee:.0f} kcal. Suggested daily target ~{target:.0f} kcal ({note})\n"
        f"Rough macros: Protein {protein_g:.0f}g | Carbs {carbs_g:.0f}g | Fat {fat_g:.0f}g\n"
        "These are estimates only. Adjust based on progress and how you feel."
    )
