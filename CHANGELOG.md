# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Phase 3 / M4 — intake-driven dual plan generation (workout + nutrition):**
  - **Nutrition plan generation** (`nutrition/meal_planner.py`): deterministic, reproducible meal plans built ONLY from foods that pass the fail-closed allergen + dietary-pattern filter; Mifflin-St Jeor macro targets with a calorie floor; respects food preferences/dislikes. Shown in the Plans tab alongside the workout plan and persisted.
  - **Robust workout plan generation**: rewrote `maybe_generate_plan` to guarantee a full plan — exactly `workout_days_per_week` days, each filled to ~5 exercises from the equipment/injury-filtered pool, with fuzzy name matching (LLM used for day structure, never trusted for completeness) and goal-based sets/reps. Fixes the "1 day / 1 exercise" collapse.
  - **Exercise database expanded 10 → 33** across all major muscle groups and equipment types (bodyweight, dumbbell, barbell, bands, pull-up bar, machines/cables, cardio) for real plan variety.
  - **Profile tab now captures nutrition inputs**: dietary pattern, **allergens** (safety-critical), preferred/disliked foods, meals per day — and fixes the form round-trip so saving never silently wipes allergens.
  - Tests: `test_meal_planner.py`, `test_ui_profile.py`, and a hermetic workout day-fill test.
- **Phase 3 roadmap** (`PHASE_3_PLAN.md`): intake-driven dual workout+nutrition coaching, open nutrition DB (USDA FoodData Central), longitudinal tracking, and multi-LLM support (local + opt-in API).
- **GitHub Actions CI** (`.github/workflows/ci.yml`): ruff + pytest on Python 3.11/3.12 for pushes and PRs to `main`.
- **Phase 3 / M3 — nutrition data backbone (open food→nutrient DB):**
  - Local SQLite nutrition DB (`nutrition/food_db.py`): per-100g macros, portions, and structured allergen/diet tables; auto-built from a committed seed (`data/seeds/nutrition/seed_foods.json`, ~18 USDA-derived generic foods) so it works offline out of the box.
  - **Fail-closed allergen filtering** + dietary-pattern filtering done in pure SQL (never embeddings); a food passes only if positively known free of every listed allergen; user allergen synonyms normalized (e.g. dairy→milk, gluten→wheat, nuts→tree_nut).
  - Full **USDA FoodData Central CSV ingest** (`nutrition/ingest_fdc.py`, CC0 data) deriving allergen/diet flags from a curated keyword map (`data/seeds/nutrition/allergen_diet_map.json`); runnable via `python -m grokfit_coach.nutrition.ingest_fdc <dir>` (download is a documented manual step; degrades gracefully offline).
  - `lookup_nutrition` tool now queries the grounded DB (curated fallback retained).
  - Hermetic `tests/unit/test_nutrition_db.py` (seed build, search, fail-closed exclusion incl. unknown foods, synonyms, vegan filter, CSV ingest).
- **Phase 3 / M2 — multi-LLM provider layer:**
  - `llm/factory.py`: `get_chat_model(profile)` returns a LangChain chat model from the profile's `LLMConfig` — local Ollama by default, optional cloud via `init_chat_model` (lazy-imported, opt-in `[cloud]` extras).
  - Data-egress warning whenever a non-local provider is used; API keys resolved from an **env var / OS keyring**, never stored in the profile/DB.
  - Tool-reliability gating: curated local menu (default `qwen2.5`; `llama3.1`, `gemma4`, etc.), with weak models (Gemma 2/3, Phi, sub-7B, low quants) flagged for the plan path; `resolve_default_local_model` auto-detects already-pulled models.
  - Wired into the agent graph (provider-driven chat + plan generation), CLI (`--provider`/`--model`/`--api-key-env`), and the Gradio Profile tab (provider/model/API-key fields).
  - `pyproject` `[cloud]` optional extras (google-genai, groq, openai, anthropic, mistralai, keyring). Hermetic `tests/unit/test_llm_factory.py`.
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
- **Missing local model no longer breaks plan generation**: if the profile selects an Ollama model that isn't installed, the factory falls back to an installed tool-reliable model (with a warning) instead of a 404; the Plans tab also generates the workout via a direct, deterministic-fallback path so a missing/failing LLM never blocks it.
- **Sane nutrition portions**: calorie-dense foods (nuts, oils, nut butters) are now used as small toppings (~15 g) instead of 150 g mains, fixing absurd entries like "150 g almonds = 868 kcal".
- **Gradio 6 compatibility**: the Coach Chat tab now uses the messages format (list of `{role, content}` dicts) required by Gradio 6 (the old tuple format and the `Chatbot(type=...)` arg were removed). Added hermetic `tests/unit/test_ui_chat.py`. The app now launches and chats correctly on Gradio 6.16.
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
