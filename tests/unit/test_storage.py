"""Hermetic tests for the SQLite storage layer (M1)."""

from __future__ import annotations

from grokfit_coach.models import (
    EXAMPLE_USER_PROFILE,
    ExercisePrescription,
    WeeklyWorkoutPlan,
    WorkoutDay,
)
from grokfit_coach.storage import db


def _sample_plan() -> WeeklyWorkoutPlan:
    return WeeklyWorkoutPlan(
        athlete_name="Tester",
        goal="fat_loss",
        days=[
            WorkoutDay(
                day="Day 1",
                focus="Full body",
                exercises=[ExercisePrescription(name="Push-up", sets="3", reps="8-12")],
            )
        ],
    )


def test_save_and_load_profile(tmp_path):
    p = tmp_path / "t.sqlite"
    version = db.save_profile(EXAMPLE_USER_PROFILE, db_path=p)
    assert version == 1
    loaded = db.load_latest_profile(db_path=p)
    assert loaded is not None
    assert loaded.name == EXAMPLE_USER_PROFILE.name


def test_load_profile_empty_returns_none(tmp_path):
    assert db.load_latest_profile(db_path=tmp_path / "t.sqlite") is None


def test_profile_versioning_and_intake_event(tmp_path):
    p = tmp_path / "t.sqlite"
    db.save_profile(EXAMPLE_USER_PROFILE, db_path=p)
    v2 = db.save_profile(EXAMPLE_USER_PROFILE, db_path=p)
    assert v2 == 2
    intake = db.list_events(event_type="intake", db_path=p)
    assert len(intake) == 2
    assert intake[0]["payload"]["profile_version"] == 1
    assert intake[1]["payload"]["profile_version"] == 2


def test_plan_save_and_load(tmp_path):
    p = tmp_path / "t.sqlite"
    pid = db.save_plan("workout", _sample_plan(), db_path=p)
    assert pid >= 1
    loaded = db.load_latest_plan("workout", db_path=p)
    assert loaded is not None
    assert loaded.athlete_name == "Tester"
    assert loaded.days[0].exercises[0].name == "Push-up"
    # nutrition kind is empty
    assert db.load_latest_plan("nutrition", db_path=p) is None


def test_append_and_filter_events(tmp_path):
    p = tmp_path / "t.sqlite"
    db.append_event("weight", {"kg": 92.5}, db_path=p)
    db.append_event("note", {"text": "felt good"}, db_path=p)
    assert len(db.list_events(db_path=p)) == 2
    weights = db.list_events(event_type="weight", db_path=p)
    assert len(weights) == 1
    assert weights[0]["payload"]["kg"] == 92.5


def test_legacy_json_migration(tmp_path):
    # legacy profile.json + last_plan.json next to the (not-yet-created) DB
    (tmp_path / "profile.json").write_text(EXAMPLE_USER_PROFILE.model_dump_json(), encoding="utf-8")
    (tmp_path / "last_plan.json").write_text(_sample_plan().model_dump_json(), encoding="utf-8")
    p = tmp_path / "grokfit.sqlite"

    loaded = db.load_latest_profile(db_path=p)
    assert loaded is not None and loaded.name == EXAMPLE_USER_PROFILE.name
    plan = db.load_latest_plan("workout", db_path=p)
    assert plan is not None and plan.days[0].exercises[0].name == "Push-up"

    migration_events = db.list_events(event_type="migration", db_path=p)
    assert len(migration_events) == 1

    # migration is idempotent: opening again does not duplicate
    db.load_latest_profile(db_path=p)
    assert len(db.list_events(event_type="migration", db_path=p)) == 1
