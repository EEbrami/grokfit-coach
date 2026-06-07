"""Basic local JSON persistence for user profile and last generated plan.

All data stays on the user's machine ( ~/.grokfit/ by default ).
Uses Pydantic for (de)serialization. Graceful handling of missing/invalid files.
"""

from __future__ import annotations

import json
from pathlib import Path

from grokfit_coach.config.settings import ensure_user_data_dirs, get_settings
from grokfit_coach.models import EXAMPLE_USER_PROFILE, UserProfile, WeeklyWorkoutPlan


def _ensure_dirs() -> None:
    ensure_user_data_dirs()


def save_profile(profile: UserProfile) -> Path:
    """Save the given profile to the configured JSON path. Returns the path."""
    _ensure_dirs()
    settings = get_settings()
    path = settings.profile_path
    path.write_text(profile.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_profile() -> UserProfile:
    """Load profile from disk if present and valid; otherwise return EXAMPLE_USER_PROFILE."""
    settings = get_settings()
    path = settings.profile_path
    if not path.exists():
        return EXAMPLE_USER_PROFILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return UserProfile.model_validate(data)
    except Exception:
        # Corrupt or incompatible file -> fall back safely
        return EXAMPLE_USER_PROFILE


def save_plan(plan: WeeklyWorkoutPlan) -> Path:
    """Save the last generated plan to disk. Returns the path."""
    _ensure_dirs()
    settings = get_settings()
    path = settings.last_plan_path
    path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_plan() -> WeeklyWorkoutPlan | None:
    """Load the last saved plan if present and valid; otherwise None."""
    settings = get_settings()
    path = settings.last_plan_path
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return WeeklyWorkoutPlan.model_validate(data)
    except Exception:
        return None


def get_current_profile() -> UserProfile:
    """Convenience: load persisted profile or fall back to example."""
    return load_profile()
