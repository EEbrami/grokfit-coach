"""Local persistence facade for user profile and plans.

Phase 3: backed by SQLite (``grokfit_coach.storage.db``) instead of single JSON files.
- Profiles are versioned (a new snapshot per save) and every save logs an 'intake' event.
- Plans are timestamped by kind ('workout' | 'nutrition').
- Legacy ``~/.grokfit/profile.json`` / ``last_plan.json`` are migrated automatically on first use.

The public function names/signatures are unchanged so the CLI and Gradio UI keep working.
All data stays on the user's machine.
"""

from __future__ import annotations

from pathlib import Path

from grokfit_coach.config.settings import ensure_user_data_dirs, get_settings
from grokfit_coach.models import EXAMPLE_USER_PROFILE, NutritionPlan, UserProfile, WeeklyWorkoutPlan
from grokfit_coach.storage import db


def _ensure_dirs() -> None:
    ensure_user_data_dirs()


# --------------------------------------------------------------------------- #
# Profile
# --------------------------------------------------------------------------- #
def save_profile(profile: UserProfile) -> Path:
    """Save a new versioned profile snapshot (+ intake event). Returns the DB path."""
    _ensure_dirs()
    db.save_profile(profile)
    return get_settings().db_path


def load_profile() -> UserProfile:
    """Load the latest profile, or fall back to the example profile."""
    profile = db.load_latest_profile()
    return profile if profile is not None else EXAMPLE_USER_PROFILE


def get_current_profile() -> UserProfile:
    """Convenience: latest persisted profile or the example fallback."""
    return load_profile()


# --------------------------------------------------------------------------- #
# Plans
# --------------------------------------------------------------------------- #
def save_plan(plan: WeeklyWorkoutPlan) -> Path:
    """Save a timestamped workout plan. Returns the DB path."""
    _ensure_dirs()
    db.save_plan("workout", plan)
    return get_settings().db_path


def load_plan() -> WeeklyWorkoutPlan | None:
    """Load the most recent workout plan, if any."""
    plan = db.load_latest_plan("workout")
    return plan if isinstance(plan, WeeklyWorkoutPlan) else None


def save_nutrition_plan(plan: NutritionPlan) -> Path:
    """Save a timestamped nutrition plan. Returns the DB path."""
    _ensure_dirs()
    db.save_plan("nutrition", plan)
    return get_settings().db_path


def load_nutrition_plan() -> NutritionPlan | None:
    """Load the most recent nutrition plan, if any."""
    plan = db.load_latest_plan("nutrition")
    return plan if isinstance(plan, NutritionPlan) else None
