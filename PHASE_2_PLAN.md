# Phase 2 Plan: Gradio UI + Persistence + Improved Plans

**Branch**: `feat/phase-2-ui` (branched from `feat/phase-1-foundation`)
**Goal**: Deliver a usable Gradio UI on top of the solid Phase 1 foundation, add basic persistence, improve plan quality, without breaking the CLI or safety.

## 1. Analysis of Phase 1 State (Summary)

**Successfully Implemented (from PHASE_1_HANDOFF and verification):**
- Clean, installable Python package (`pyproject.toml`, console script `grokfit-coach`).
- Comprehensive Pydantic v2 domain models (`UserProfile` with validators, `Exercise`, `FoodItem`, basic `WeeklyWorkoutPlan`).
- Local RAG (FAISS + sentence-transformers): 10 curated exercises + foods in `data/seeds/`, `ingest.py`, `retriever.py` with simple metadata boosting, `retrieval_eval.py`.
- 3 LangChain tools: `search_exercises` (RAG-backed), `lookup_nutrition`, `calculate_macros` (pure).
- Single LangGraph agent (`agents/graph.py`): safety_preflight (rule-based), prepare_context (profile injection), ReAct-style agent + ToolNode loop, `maybe_plan` node (RAG + `with_structured_output(WeeklyWorkoutPlan)`), respond (guardrails + disclaimer).
- Strong rule-based safety (`safety/guardrails.py`): `is_unsafe_request`, `apply_output_guardrails`, comprehensive tests.
- Functional terminal CLI (`cli.py`): profile loading (JSON or default), interactive REPL with history, one-shot mode, plan pretty-printing, graceful Ollama errors. Does **not** break existing usage.
- Solid unit tests (pytest, hermetic with fakes/mocks for RAG/LLM), all passing.
- Detailed documentation (`PHASE_1_HANDOFF.md`, updated README, CHANGELOG).
- Everything 100% local/Ollama. No external LLM APIs.

**Notable Weaknesses / Areas for Phase 2 Improvement:**
- **Plan generation quality is basic and brittle**: The `maybe_plan` path does a single RAG lookup on the last query, passes a flat list of exercise *names* in a prompt, then relies on LLM structured output. No iterative refinement, limited day-by-day structure, weak enforcement of exact profile constraints (equipment, injuries, days), and falls back to `None` on any LLM error. Plans often lack variety, proper progression, or full respect for constraints.
- **RAG is minimal**: Only 10 exercises; simple post-hoc boosting (string contains); retrieval metrics were mediocre in Phase 1 evals. No hybrid search or better context injection into planning.
- **No persistence**: Profiles and plans exist only in-memory per CLI session or invoke call. UI will need save/load.
- **No UI**: `src/grokfit_coach/ui/` is still just the skeleton `__init__.py` (intentionally untouched in Phase 1).
- **CLI is functional but plain**: Text-only REPL; no rich output, streaming, or multi-turn plan editing.
- **Agent extensibility**: The single graph with a special "maybe_plan" conditional is okay for foundation but will need cleanup for future agents.
- **Tests**: Strong unit coverage, but no end-to-end UI tests or real-Ollama integration tests yet. Plan quality not systematically evaluated.
- Minor: LangChain deprecation warnings for embeddings; small seed set; no meal plans beyond basic.

**Overall**: Phase 1 delivered a *working, safe, testable terminal agent* as the core. The foundation (agent, tools, RAG, safety, models, CLI) is solid and reusable. Phase 2 can safely build the UI and improvements on top without refactoring the core.

## 2. Phase 2 Scope (Focused & Realistic)

**Must Deliver**:
- **Gradio UI** (new `src/grokfit_coach/ui/app.py` + launch entry):
  - Tabs (using `gr.Blocks` or `gr.TabbedInterface`):
    - **Profile**: Form matching `UserProfile` fields (name, age, gender, height/weight, goal dropdown, fitness_level, multi-select equipment/restrictions/injuries, days/week, duration). "Save" button that validates + persists. Load from saved.
    - **Coach Chat**: `gr.Chatbot` + input. On submit: load current profile (from state/persistence), call `invoke_coach(profile, message)`, display response (with disclaimer). Support "generate plan" natural language.
    - **Plans**: Display last/current `WeeklyWorkoutPlan` (pretty markdown or structured cards). Button "Generate / Regenerate Weekly Plan" that triggers improved plan logic using current profile + agent. Option to save/export.
  - Prominent safety disclaimer banner on every tab.
  - Launch via `python -m grokfit_coach.ui.app` or console script (keep CLI separate and working).
  - Session state for profile/chat history within the Gradio app.

- **Improved Weekly Workout Plan Generation**:
  - Enhance the planning path (either improve `maybe_plan` node or add a dedicated tool/helper).
  - Better RAG usage: retrieve more context (full Exercise objects with cues/contraindications), filter strictly by profile equipment + avoid injuries.
  - Structured prompt engineering + few-shot examples in the plan prompt.
  - Post-processing validation: ensure all recommended exercises exist in seeds, respect equipment, include form cues/safety notes.
  - Make plans more realistic: respect `workout_days_per_week` and `session_duration_min`, vary intensity, add rest notes, simple progression hints.
  - Keep it using the existing `WeeklyWorkoutPlan` Pydantic model (improve the model slightly if needed for better structure, e.g., add `estimated_duration`).
  - Fallback: if LLM structured output fails, generate a safe default plan from retrieved exercises.

- **Basic Local Persistence** (new `src/grokfit_coach/persistence.py` or in `utils/`):
  - Save/load `UserProfile` as JSON (e.g., `~/.grokfit/profile.json` or `data/user_profile.json` under project, configurable via settings).
  - Save/load last generated `WeeklyWorkoutPlan` as JSON.
  - Simple functions: `save_profile(profile)`, `load_profile() -> Optional[UserProfile]`, same for plan.
  - Use in CLI (optional --save flag or auto on exit?) and UI (auto on save/generate).
  - Handle missing files gracefully; use EXAMPLE as default.
  - Keep it file-based JSON (no DB yet). Respect privacy (local only).

- **Non-Breaking**:
  - Terminal CLI (`grokfit-coach` / `cli.py`) must continue to work exactly as before (or with minor optional persistence).
  - All existing unit tests must continue to pass.
  - Safety guardrails must remain active and tested (pre-filter + disclaimer on all outputs, including from UI).
  - Agent (`invoke_coach`, `build_coach_graph`) API remains stable for UI to call.
  - 100% local Ollama only.

**Out of Scope for Phase 2** (keep focused):
- Meal plans (beyond any incidental nutrition in chat).
- Advanced RAG (hybrid, reranking, larger seeds).
- Multi-agent orchestration.
- Voice, images, rich visualizations beyond basic Gradio.
- Cloud anything, auth, multi-user.
- Full persistence of chat history (only profile + last plan).
- Polished styling (basic Gradio is fine).

## 3. High-Level Implementation Order (Step-by-Step, with Verification)

1. **Setup & Branch Hygiene**
   - (Already done) Branch created from Phase 1.
   - Add Gradio to dependencies (`pyproject.toml`, `requirements.txt`).
   - Create/update `src/grokfit_coach/ui/__init__.py` and `app.py`.
   - Add any new settings (e.g., persistence paths) to `config/settings.py`.
   - Quick test: `pytest tests/unit -q` still green.

2. **Persistence Layer** (foundational for UI + improved CLI)
   - Implement `src/grokfit_coach/persistence.py`: `save_profile`, `load_profile`, `save_plan`, `load_plan`.
   - Use `pathlib`, JSON + Pydantic `.model_dump_json()` / `.model_validate_json()`.
   - Default location: e.g., `Path.home() / ".grokfit"` (create dir if needed). Make configurable.
   - Wire into CLI (e.g., auto-load profile, optional save on plan gen).
   - Add basic tests in `tests/unit/test_persistence.py`.
   - Verify: CLI still works, can save/load profile/plan.

3. **Improve Plan Generation**
   - Refactor/enhance `agents/graph.py` (the `maybe_plan` node or extract to a new tool `generate_workout_plan`).
   - Better context: pass full `Exercise` objects (or rich summaries) from RAG, filtered by profile.
   - Stronger prompt in `agents/prompts.py` (add few-shot examples of good plans, explicit rules for constraints).
   - Post-validation in the plan function: filter invalid exercises, ensure day count matches profile, add safety notes.
   - Make the plan path more robust (retry structured output, or fallback to a deterministic safe plan from retrieved exercises).
   - Update `WeeklyWorkoutPlan` model if needed for better fields (e.g., `focus`, `notes` per day).
   - Manual verification: Use CLI with various profiles (different equipment, injuries, goals) and inspect plan quality.
   - Add a simple evaluation or more test cases for plans.

4. **Gradio UI Implementation**
   - `src/grokfit_coach/ui/app.py`:
     - Use `gr.Blocks()` with `gr.Tab()`.
     - **Profile tab**: `gr.Textbox`, `gr.Number`, `gr.Dropdown`/`Radio`, `gr.CheckboxGroup`/`Multiselect` for lists, `gr.Slider`. "Load Saved", "Save Profile" buttons. On save: validate with Pydantic, persist, update session state.
     - **Coach Chat tab**: `gr.Chatbot(value=[], type="messages")`, `gr.Textbox(placeholder=...)`. Submit handler: get current profile from state/persistence, call `from grokfit_coach.agents.graph import invoke_coach`, append to chat history (user + assistant with disclaimer).
     - **Plans tab**: `gr.Markdown()` or custom display for the plan (use `format_plan` logic or Gradio components for days/exercises). "Generate Plan" button that calls improved plan logic (via agent or direct), displays it, offers "Save Plan".
   - Global: Load profile on app start into `gr.State`. Safety banner (`gr.Markdown(DISCLAIMER)`).
   - Launch function: `demo.launch(server_name="127.0.0.1", share=False)`.
   - Add entry point in `pyproject.toml` (optional: `grokfit-coach-ui`).
   - Keep `ui/__init__.py` exporting the demo if useful.
   - End-to-end test: Manually launch UI, fill profile, chat (including "create a plan"), generate plan, verify safety in responses, persistence works across "restarts".

5. **Integration, Polish & Non-Breaking Checks**
   - Ensure UI calls the exact same `invoke_coach` / graph as CLI (no duplication).
   - Update CLI to optionally use persistence by default.
   - Run full `pytest tests/unit -q`.
   - Manual verification:
     - Terminal CLI still works unchanged (`grokfit-coach`, unsafe queries blocked, plans generated).
     - UI launches, all tabs functional, chat produces safe agent responses, plans are better quality.
     - Safety: Try unsafe prompts in chat → blocked.
     - Persistence: Save profile in UI, restart CLI/UI, profile loads.
   - Fix any deprecations or small issues surfaced.
   - Add minimal UI-specific tests if feasible (e.g., smoke test that app object builds).

6. **Documentation & Handoff**
   - Update `README.md`: Add UI section, new launch commands, screenshots placeholders or ASCII, note that terminal CLI remains primary for now.
   - Create `PHASE_2_HANDOFF.md` (modeled after Phase 1): what was built, architecture (UI as thin layer over agent), how to run (terminal + UI), design decisions (persistence location, plan improvements), limitations, Phase 3 ideas (better plans, meal support, multi-agent, etc.).
   - Update `CHANGELOG.md`.
   - Ensure `PHASE_1_HANDOFF.md` is still accurate.

## 4. Verification Gates (Run After Major Components)

- After persistence + plan improvements: `pytest`, manual CLI + plan quality checks with varied profiles.
- After UI built: Launch UI (`python -m grokfit_coach.ui.app` or equivalent), full end-to-end flow in browser.
- Before any push: All unit tests green, UI works, CLI unbroken, unsafe requests blocked in both interfaces, persistence functional.
- At end: Update docs, perhaps a final `git status` + commit summary.

## 5. Risks & Mitigations (Keep Scope Tight)

- LLM plan quality still variable → Mitigate with strong prompts, RAG filtering, post-validation, fallback.
- Gradio session state vs persistence confusion → Clear "Save" buttons + auto-load on start.
- Breaking CLI → Never touch `cli.py` core; only add optional persistence calls.
- Heavy deps (Gradio + torch from sentence-transformers) → Already in Phase 1; document first-run download.
- Structured output reliability → Keep try/except + fallback as in Phase 1.

## 6. Timeline / Order Notes

Follow the numbered order above. Use `todo_write` tool to track sub-tasks. After each major section (2,3,4), run verification. Push the branch to GitHub **only** when UI is end-to-end usable + tests pass + safety confirmed.

This plan keeps Phase 2 focused on the user's explicit goals while leveraging the excellent Phase 1 foundation. No scope creep.

---

**Ready to implement.** Next steps will be adding Gradio to packaging, then persistence layer, etc.