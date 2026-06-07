# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
