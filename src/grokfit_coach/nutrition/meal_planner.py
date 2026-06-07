"""Deterministic, allergen-safe nutrition plan generation grounded in the local food DB.

Why deterministic (not LLM-authored): a nutrition plan that touches allergens is a real-harm
bug, and small local models are unreliable at structured output. So we compute macro targets
(Mifflin-St Jeor) and assemble meals from foods that have ALREADY passed the fail-closed
allergen + dietary-pattern SQL filter (see food_db). The result is reproducible and safe.
"""

from __future__ import annotations

from grokfit_coach.models import (
    DailyTargets,
    FoodChoice,
    FoodItem,
    Meal,
    NutritionDay,
    NutritionPlan,
    UserProfile,
)
from grokfit_coach.nutrition import food_db
from grokfit_coach.safety.guardrails import DISCLAIMER

_ACTIVITY_MULT = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725, "very": 1.9}
_CALORIE_FLOOR = 1200  # safety floor — never prescribe an aggressive/crash deficit
_DENSE_KCAL = 500  # kcal/100g threshold: calorie-dense foods (nuts, oils, nut butters) get tiny portions

_MEAL_NAMES = ["Breakfast", "Lunch", "Dinner", "Snack", "Second Snack", "Pre-Workout", "Post-Workout", "Evening Snack"]


def compute_daily_targets(profile: UserProfile) -> DailyTargets:
    """Daily energy + macro targets via Mifflin-St Jeor, adjusted by goal. Calorie-floored."""
    w, h, age = profile.weight_kg, profile.height_cm, profile.age
    if str(profile.gender).lower() in ("male", "m"):
        bmr = 10 * w + 6.25 * h - 5 * age + 5
    else:
        bmr = 10 * w + 6.25 * h - 5 * age - 161
    tdee = bmr * _ACTIVITY_MULT.get(profile.activity_level, 1.55)

    goal = profile.goal
    if goal == "fat_loss":
        cals, protein = tdee - 400, w * 2.0
    elif goal == "body_recomposition":
        cals, protein = tdee - 150, w * 2.2
    elif goal in ("muscle_gain", "strength"):
        cals, protein = tdee + 300, w * 1.8
    else:
        cals, protein = tdee, w * 1.6

    cals = max(cals, _CALORIE_FLOOR)
    fat = (cals * 0.25) / 9
    carbs = max((cals - protein * 4 - fat * 9) / 4, 0)
    return DailyTargets(
        calories=round(cals), protein_g=round(protein), carbs_g=round(carbs), fat_g=round(fat)
    )


def _bias_by_preferences(foods: list[FoodItem], profile: UserProfile) -> list[FoodItem]:
    """Drop disliked foods; sort preferred foods first (soft preferences)."""
    dislikes = [d.lower() for d in (profile.disliked_foods or [])]
    prefs = [p.lower() for p in (profile.food_preferences or [])]
    kept = [f for f in foods if not any(d in f.name.lower() for d in dislikes)]
    kept.sort(key=lambda f: (0 if any(p in f.name.lower() for p in prefs) else 1, f.name))
    return kept


def _pick(items: list[FoodItem], idx: int) -> FoodItem | None:
    return items[idx % len(items)] if items else None


def _portion_grams(food: FoodItem, role: str) -> float:
    """Sensible serving size (grams) by role; calorie-dense foods get a small topping portion."""
    if food.calories >= _DENSE_KCAL:
        return 15.0
    return {"protein": 150.0, "carb": 110.0, "veg": 150.0}.get(role, 100.0)


def _choice(item: FoodItem, grams: float) -> FoodChoice:
    m = food_db.macros_for_grams(item, grams)
    return FoodChoice(
        name=item.name, grams=grams, fdc_id=item.fdc_id,
        calories=m["calories"], protein_g=m["protein_g"], carbs_g=m["carbs_g"], fat_g=m["fat_g"],
    )


def generate_nutrition_plan(profile: UserProfile, db_path=None) -> NutritionPlan:
    """Build a one-day meal template hitting ~daily targets, using only allergen-safe foods."""
    targets = compute_daily_targets(profile)

    # Foods that pass the fail-closed allergen + dietary filter (safety happens here).
    safe = food_db.filter_foods(
        allergens=profile.allergens, dietary_pattern=profile.dietary_pattern, limit=200, db_path=db_path
    )
    safe = _bias_by_preferences(safe, profile)

    # Calorie-dense foods (nuts, oils, nut butters) are used as small toppings, not mains.
    dense = [f for f in safe if f.calories >= _DENSE_KCAL]
    proteins = [f for f in safe if f.protein_g >= 15 and f.calories < _DENSE_KCAL]
    carbs = [f for f in safe if f.carbs_g >= 15 and f.calories < _DENSE_KCAL]
    veg_fruit = [f for f in safe if f.calories <= 100 and f.carbs_g < 25]
    # graceful fallbacks if a bucket is empty (e.g. restrictive diet)
    proteins = proteins or [f for f in safe if f.protein_g >= 8] or safe
    carbs = carbs or [f for f in safe if f.carbs_g >= 10] or safe
    veg_fruit = veg_fruit or safe

    n_meals = max(1, min(profile.meals_per_day, 6))
    meals: list[Meal] = []
    for i in range(n_meals):
        items: list[FoodChoice] = []
        used: set[str] = set()
        for role, source in (("protein", proteins), ("carb", carbs), ("veg", veg_fruit)):
            food = _pick(source, i)
            if food and food.name not in used:
                items.append(_choice(food, _portion_grams(food, role)))
                used.add(food.name)
        # round out fats/flavor with a small portion of a calorie-dense food, when available
        ex = _pick(dense, i)
        if ex and ex.name not in used:
            items.append(_choice(ex, _portion_grams(ex, "extra")))
            used.add(ex.name)
        if items:
            meals.append(Meal(name=_MEAL_NAMES[i] if i < len(_MEAL_NAMES) else f"Meal {i+1}", items=items))

    # Day totals (so the user sees actual macros vs target)
    tot = {"calories": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0}
    for meal in meals:
        for it in meal.items:
            tot["calories"] += it.calories or 0
            tot["protein_g"] += it.protein_g or 0
            tot["carbs_g"] += it.carbs_g or 0
            tot["fat_g"] += it.fat_g or 0

    note = (
        f"Target ~{targets.calories} kcal (P {targets.protein_g} / C {targets.carbs_g} / F {targets.fat_g} g). "
        f"This template totals ~{round(tot['calories'])} kcal "
        f"(P {round(tot['protein_g'])} / C {round(tot['carbs_g'])} / F {round(tot['fat_g'])} g). "
        f"Adjust portions to fine-tune. All foods respect your allergens "
        f"({', '.join(profile.allergens) or 'none'}) and pattern ({profile.dietary_pattern})."
    )

    return NutritionPlan(
        athlete_name=profile.name,
        goal=profile.goal,
        daily_targets=targets,
        days=[NutritionDay(day="Daily Template", meals=meals)],
        notes=note,
        disclaimer=DISCLAIMER,
    )
