"""Profile form round-trip must preserve safety-critical fields (allergen-wipe gate, M4)."""

from __future__ import annotations

from pathlib import Path

from grokfit_coach.models import EXAMPLE_USER_PROFILE
from grokfit_coach.ui.app import (
    _form_values_to_profile,
    _profile_to_form_values,
    _write_plan_markdown,
)


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


def test_write_plan_markdown_creates_downloadable_file(tmp_path, monkeypatch):
    import grokfit_coach.config.settings as settings_mod

    class _S:
        user_data_dir = tmp_path

    monkeypatch.setattr(settings_mod, "get_settings", lambda: _S())
    path = _write_plan_markdown("## 🏋️ Workout Plan\n- Push-up: 3 × 12-15", "Abraham Test")
    text = Path(path).read_text(encoding="utf-8")
    assert path.endswith("grokfit_plan_Abraham_Test.md")
    assert "GrokFit Coach — Plan for Abraham Test" in text
    assert "Push-up" in text
