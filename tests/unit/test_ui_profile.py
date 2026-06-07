"""Profile form round-trip must preserve safety-critical fields (allergen-wipe gate, M4)."""

from __future__ import annotations

from grokfit_coach.models import EXAMPLE_USER_PROFILE
from grokfit_coach.ui.app import _form_values_to_profile, _profile_to_form_values


def test_form_roundtrip_preserves_allergens_and_nutrition_fields():
    profile = EXAMPLE_USER_PROFILE.model_copy(
        update={
            "allergens": ["peanut", "shellfish"],
            "dietary_pattern": "vegan",
            "food_preferences": ["rice", "tofu"],
            "disliked_foods": ["liver"],
            "meals_per_day": 4,
        }
    )
    values = _profile_to_form_values(profile)
    rebuilt = _form_values_to_profile(values)

    # The Profile-tab save must NOT silently wipe these (they are safety/personalization fields)
    assert rebuilt.allergens == ["peanut", "shellfish"]
    assert rebuilt.dietary_pattern == "vegan"
    assert rebuilt.food_preferences == ["rice", "tofu"]
    assert rebuilt.disliked_foods == ["liver"]
    assert rebuilt.meals_per_day == 4
