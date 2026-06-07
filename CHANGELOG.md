# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Phase 3 roadmap** (`PHASE_3_PLAN.md`): intake-driven dual workout+nutrition coaching, open nutrition DB (USDA FoodData Central), longitudinal tracking, and multi-LLM support (local + opt-in API).
- **GitHub Actions CI** (`.github/workflows/ci.yml`): ruff + pytest on Python 3.11/3.12 for pushes and PRs to `main`.
- **Phase 3 / M1 — data-model spine & SQLite storage:**
  - SQLite storage layer (`storage/db.py`): versioned `profiles`, append-only timestamped `events` log, timestamped `plans` (kind = workout/nutrition); auto-migrates legacy `profile.json`/`last_plan.json`.
  - Expanded `UserProfile`: `dietary_pattern`, `food_preferences`, `disliked_foods`, `allergens` (safety-critical), `meals_per_day`, `cooking_effort`, `activity_level`, nested `llm_config`, `profile_version`.
  - New models: `LLMConfig`, `NutritionPlan`/`NutritionDay`/`Meal`/`FoodChoice`/`DailyTargets`, `TrackingEvent`; extended `FoodItem` with `fdc_id`/`grams`/`diet_flags`/`allergen_flags`.
  - `persistence.py` rewired onto SQLite (same public API → CLI/UI unchanged); added nutrition-plan save/load.
  - Hermetic `tests/unit/test_storage.py` (versioning, events, plan round-trip, idempotent migration).
- `"body_recomposition"` training goal option to models, macro calculation tool, and Gradio UI.
- Unit tests verifying model validation and macro calculations for the new body recomposition goal.
- Hermetic unit test `test_maybe_generate_plan_fallback` to verify agent's plan fallback path.

### Fixed
- Pydantic ValidationError in agent fallback path (`maybe_generate_plan`) by importing and using actual `WorkoutDay` and `ExercisePrescription` models instead of dynamic classes constructed with `type()`.
- Gradio UI Chatbot crash by removing `type="messages"` from `gr.Chatbot` to match callback history's tuple format.
- Cleaned up Ruff linting errors (unused imports, sorting, unused variables) across the package.

- Phase 1 foundation: full Pydantic v2 models (UserProfile + Exercise + FoodItem + WeeklyWorkoutPlan), local FAISS RAG over curated seeds, 3 LangChain tools, single LangGraph coach agent with explicit safety nodes, thin terminal CLI (REPL + one-shot).
- Comprehensive pytest suite (models, safety/guardrails, RAG with fakes, tools, graph) + retrieval_eval script.
- Strong rule-based guardrails (pre-filter + forced disclaimer on every output) + tests that attempt unsafe requests.
- pyproject.toml (modern packaging, console script `grokfit-coach`, dev extras, pyright/pytest config).
- `PHASE_1_HANDOFF.md` with architecture, run instructions, extension guidance, and Phase 2 roadmap.
- Curated seed data (`data/seeds/*.json`) + ingestion that produces gitignored FAISS indexes.

### Changed
- Evolved the original skeleton `AthleteProfile` + no-op graph into production-minded, type-safe, testable components.
- Updated README with accurate Phase 1 status, exact Ollama commands, and terminal usage examples.
- Expanded requirements.txt for compatibility while preferring `pip install -e ".[dev]"`.

## [0.1.0] - Phase 1 Terminal Agent

Initial functional release of the local coach (terminal only). See PHASE_1_HANDOFF.md.
