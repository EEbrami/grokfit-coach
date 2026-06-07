"""SQLite storage layer for grokfit-coach (local-first, privacy-preserving).

A single SQLite file (``~/.grokfit/grokfit.sqlite`` by default) holds:
- ``profiles``  : versioned snapshots of the UserProfile (append a new row per save)
- ``events``    : append-only, timestamped log of every input (the tracking backbone)
- ``plans``     : timestamped generated plans (kind = 'workout' | 'nutrition')

On first use it migrates any legacy JSON (``profile.json`` / ``last_plan.json``) that
lives in the same directory as the DB, so existing Phase 1/2 data is preserved.

All public functions accept an optional ``db_path`` for hermetic testing; in production
they resolve the path from Settings.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from grokfit_coach.config.settings import get_settings
from grokfit_coach.models import UserProfile, WeeklyWorkoutPlan
from grokfit_coach.models.nutrition_plan import NutritionPlan

_SCHEMA = """
CREATE TABLE IF NOT EXISTS profiles (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version    INTEGER NOT NULL,
    json       TEXT    NOT NULL,
    created_ts TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    type         TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}'
);
CREATE TABLE IF NOT EXISTS plans (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    ts   TEXT NOT NULL,
    kind TEXT NOT NULL,
    json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_plans_kind_id ON plans(kind, id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _resolve_path(db_path: Path | str | None) -> Path:
    if db_path is not None:
        return Path(db_path)
    return get_settings().db_path


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open (creating if needed) the SQLite DB, ensure schema, run one-time migration."""
    path = _resolve_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    _migrate_legacy_json(conn, path.parent)
    return conn


# --------------------------------------------------------------------------- #
# Migration
# --------------------------------------------------------------------------- #
def _migrate_legacy_json(conn: sqlite3.Connection, base_dir: Path) -> None:
    """Import legacy profile.json / last_plan.json from base_dir on first use (idempotent)."""
    if conn.execute("SELECT COUNT(*) AS c FROM profiles").fetchone()["c"] == 0:
        legacy_profile = base_dir / "profile.json"
        if legacy_profile.exists():
            try:
                profile = UserProfile.model_validate_json(legacy_profile.read_text(encoding="utf-8"))
                _insert_profile(conn, profile, event_type="migration")
            except Exception:
                pass

    if conn.execute("SELECT COUNT(*) AS c FROM plans").fetchone()["c"] == 0:
        legacy_plan = base_dir / "last_plan.json"
        if legacy_plan.exists():
            try:
                plan = WeeklyWorkoutPlan.model_validate_json(legacy_plan.read_text(encoding="utf-8"))
                conn.execute(
                    "INSERT INTO plans (ts, kind, json) VALUES (?, ?, ?)",
                    (_now(), "workout", plan.model_dump_json()),
                )
            except Exception:
                pass
    conn.commit()


# --------------------------------------------------------------------------- #
# Profiles (versioned)
# --------------------------------------------------------------------------- #
def _insert_profile(conn: sqlite3.Connection, profile: UserProfile, event_type: str = "intake") -> int:
    version = conn.execute("SELECT COALESCE(MAX(version), 0) AS v FROM profiles").fetchone()["v"] + 1
    conn.execute(
        "INSERT INTO profiles (version, json, created_ts) VALUES (?, ?, ?)",
        (version, profile.model_dump_json(), _now()),
    )
    conn.execute(
        "INSERT INTO events (ts, type, payload_json) VALUES (?, ?, ?)",
        (_now(), event_type, json.dumps({"profile_version": version, "name": profile.name, "goal": profile.goal})),
    )
    conn.commit()
    return version


def save_profile(profile: UserProfile, db_path: Path | str | None = None) -> int:
    """Append a new versioned profile snapshot + an 'intake' event. Returns the new version."""
    conn = get_connection(db_path)
    try:
        return _insert_profile(conn, profile, event_type="intake")
    finally:
        conn.close()


def load_latest_profile(db_path: Path | str | None = None) -> UserProfile | None:
    """Return the most recent profile snapshot, or None if none stored."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT json FROM profiles ORDER BY version DESC LIMIT 1").fetchone()
        return UserProfile.model_validate_json(row["json"]) if row else None
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Events (append-only tracking log)
# --------------------------------------------------------------------------- #
def append_event(event_type: str, payload: dict[str, Any] | None = None, db_path: Path | str | None = None) -> None:
    """Append a timestamped event to the log."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO events (ts, type, payload_json) VALUES (?, ?, ?)",
            (_now(), event_type, json.dumps(payload or {})),
        )
        conn.commit()
    finally:
        conn.close()


def list_events(
    event_type: str | None = None,
    db_path: Path | str | None = None,
) -> list[dict[str, Any]]:
    """Return events (optionally filtered by type), oldest first."""
    conn = get_connection(db_path)
    try:
        if event_type:
            rows = conn.execute(
                "SELECT ts, type, payload_json FROM events WHERE type = ? ORDER BY id", (event_type,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT ts, type, payload_json FROM events ORDER BY id").fetchall()
        return [{"ts": r["ts"], "type": r["type"], "payload": json.loads(r["payload_json"])} for r in rows]
    finally:
        conn.close()


# --------------------------------------------------------------------------- #
# Plans (timestamped, by kind)
# --------------------------------------------------------------------------- #
def save_plan(kind: str, plan: WeeklyWorkoutPlan | NutritionPlan, db_path: Path | str | None = None) -> int:
    """Append a timestamped plan ('workout' or 'nutrition'). Returns the plan row id."""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO plans (ts, kind, json) VALUES (?, ?, ?)",
            (_now(), kind, plan.model_dump_json()),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def load_latest_plan(kind: str, db_path: Path | str | None = None) -> WeeklyWorkoutPlan | NutritionPlan | None:
    """Return the most recent plan of the given kind, or None."""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT json FROM plans WHERE kind = ? ORDER BY id DESC LIMIT 1", (kind,)).fetchone()
        if not row:
            return None
        model = WeeklyWorkoutPlan if kind == "workout" else NutritionPlan
        return model.model_validate_json(row["json"])
    finally:
        conn.close()
