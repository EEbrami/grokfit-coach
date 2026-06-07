# PHASE 2 HANDOFF — grokfit-coach

**Date**: Phase 2 UI + Persistence + Plan Quality complete  
**Branch**: `feat/phase-2-ui` (branched from completed `feat/phase-1-foundation`)  
**Status**: Gradio UI functional, persistence added, plan generation improved, CLI preserved, safety intact. All local.

## What Was Added in Phase 2 (on top of solid Phase 1 foundation)

### Packaging & Entry Points
- Added `gradio>=4.0` to runtime deps (pyproject.toml + requirements.txt).
- New console script: `grokfit-coach-ui = "grokfit_coach.ui.app:launch"`.
- UI can also be launched with `python -m grokfit_coach.ui.app`.

### Persistence (new `src/grokfit_coach/persistence.py`)
- `save_profile` / `load_profile` → `~/.grokfit/profile.json` (or configured path).
- `save_plan` / `load_plan` → `~/.grokfit/last_plan.json`.
- Graceful fallbacks to `EXAMPLE_USER_PROFILE` or `None`.
- `get_current_profile()` convenience.
- `ensure_user_data_dirs()` in settings.
- Integrated into CLI (default profile load from persistence; auto-save of generated plans).
- Simple, private, file-based JSON using Pydantic serialization.

### Improved Plan Generation
- Enhanced `agents/prompts.py` with dedicated `PLAN_GENERATION_PROMPT` containing explicit rules, constraint respect, and formatting instructions.
- Refactored `agents/graph.py` `maybe_generate_plan`:
  - Profile-aware RAG + client-side equipment/injury filtering.
  - Richer context passed to LLM (names + descriptions + equipment).
  - Stronger prompt injection via the new template.
  - Post-validation: keeps only exercises from the retrieved/allowed set.
  - Robust fallback: deterministic safe plan built from filtered retrieved exercises when LLM structured output fails or is invalid.
- Plans now better respect `workout_days_per_week`, `session_duration_min`, equipment, and basic injury avoidance.
- Still produces the same `WeeklyWorkoutPlan` Pydantic model (usable by CLI and UI).

### Gradio UI (`src/grokfit_coach/ui/app.py`)
- `gr.Blocks` + three tabs:
  - **Profile**: Full form (Text, Number, Dropdown, CheckboxGroup, Sliders). Load Saved + Save Profile (validates + persists via new layer). Updates shared state.
  - **Coach Chat**: `Chatbot` + textbox. On submit calls the exact same `invoke_coach(profile, message)` as the CLI. History maintained in session. Safety guardrails + disclaimer always applied.
  - **Plans**: Markdown display of current/last plan + "Generate / Regenerate" button that triggers the improved plan path (via agent). Auto-loads last saved plan. Status messages.
- Prominent disclaimer banner on load.
- Uses `gr.State` for current profile.
- Launch function: `launch()` (used by console script and `__main__`).
- Thin adapter: reuses Phase 1 agent, tools, RAG, safety, and persistence. No duplication of core logic.
- `ui/__init__.py` now exports `launch`.

### Non-Breaking Guarantees
- Terminal CLI (`grokfit-coach`) works exactly as in Phase 1 (plus optional persistence benefits). All previous usage patterns unchanged.
- All existing unit tests continue to pass (verified multiple times).
- Safety guardrails unchanged and active in both CLI and UI (pre-filter before agent, forced disclaimer on every final output).
- Agent public API (`build_coach_graph`, `invoke_coach`) untouched.

### Documentation
- `README.md` updated with Phase 2 UI section, new commands, layout, and status.
- This `PHASE_2_HANDOFF.md`.
- (CHANGELOG would be updated in a real commit.)

## How to Run the Terminal CLI and the UI

**Prerequisites (same for both):**
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Terminal 1 (background)
ollama serve

# Terminal 2
ollama pull llama3.1
python -m grokfit_coach.rag.ingest   # one-time (or after changing seeds)
```

**Terminal CLI (unchanged from Phase 1, now with persistence):**
```bash
grokfit-coach
# or
python -m grokfit_coach.cli

# One-shot
grokfit-coach --query "good beginner dumbbell chest exercises"

# With explicit profile (overrides persisted ~/.grokfit/profile.json)
grokfit-coach --profile myprofile.json --query "create a 3 day plan"
```

The CLI auto-loads from `~/.grokfit/profile.json` and auto-saves generated plans.

**Gradio UI (new in Phase 2):**
```bash
grokfit-coach-ui
# or
python -m grokfit_coach.ui.app
```

Then open http://127.0.0.1:7860.

**UI Usage:**
1. **Profile tab**: Fill/edit the form (including equipment, injuries, goals). Click **Save Profile**. This writes to `~/.grokfit/profile.json`.
2. **Coach Chat tab**: Chat naturally. The agent automatically uses your saved/persisted profile. Try "create a weekly plan...".
3. **Plans tab**: Click **Generate / Regenerate Weekly Plan**. Uses the improved Phase 2 plan logic. Last plan auto-loads from persistence.

**Persistence Sharing (CLI ↔ UI):**
- Both use the exact same `~/.grokfit/profile.json` and `last_plan.json`.
- Save profile in UI → it is used the next time you run the CLI.
- Generate a plan in CLI → it appears in the UI Plans tab on next load.

Unsafe requests are refused by guardrails in **both** the terminal CLI and the UI (before the LLM is called). All final outputs include the disclaimer.

## Design Decisions & Trade-offs

- **UI as thin layer**: The Gradio app only handles presentation, form conversion, and calling the existing `invoke_coach` + persistence. This preserves the "agent is the product" philosophy from Phase 1 and makes future UIs (or TUI, web, etc.) easy.
- **Persistence location**: `~/.grokfit/` (user home) so it works across terminal + UI sessions and survives repo changes. Configurable via Settings if needed later. Pure JSON for simplicity and inspectability.
- **Plan improvements focused on quality without complexity**: Kept the same `maybe_plan` trigger point and Pydantic output type. Added filtering + validation + prompt engineering + fallback instead of a full new agent or heavy RAG overhaul. This delivers noticeable improvement while staying within "focused Phase 2" scope.
- **CLI compatibility first**: Persistence is additive. The old `load_profile(path)` behavior for `--profile` is preserved via the wrapper.
- **No breaking changes to agent/tests**: All core Phase 1 code (graph, tools, safety, RAG, models) was left intact except for the internal plan node enhancement.

## Verification Performed (before docs)
- `pytest tests/unit -q` → all green (multiple runs).
- Persistence roundtrips (profile + plan) work.
- UI module imports cleanly; form helpers, generate_plan path, and chat integration smoke-tested at Python level.
- CLI still loads/saves via persistence, one-shot and REPL paths functional (graceful when no Ollama).
- Safety unchanged (pre-filter + disclaimer applied to UI chat and plan outputs).
- Plan generation now has richer context, explicit rules, post-filtering, and a reliable fallback.

Full end-to-end UI usage (browser) requires `pip install -e .` + `grokfit-coach-ui` on a machine with a display (or headless Gradio testing).

## Known Limitations
- Plan quality is improved (better filtering, richer prompts, validation + fallback) but still depends on the local Ollama model's ability to reliably do structured output and follow complex instructions.
- The seed dataset is small and curated (10 exercises, 10 foods). Retrieval quality and plan variety are limited by this.
- Persistence is deliberately simple (last profile + last plan only). No chat history, no multiple named profiles, no versioning.
- UI is basic but fully functional Gradio. No custom CSS, limited mobile experience, no rich visualizations (charts, calendars, etc.).
- No meal plans or deeper nutrition planning UI.
- Real end-to-end testing with Ollama requires the model to be running and good at tool calling/structured output (llama3.1 recommended).

## Suggested Next Steps (Phase 3+ Ideas)
- More robust plan generation: turn planning into a proper tool that the ReAct agent can call iteratively, with better RAG context (full exercise objects, contraindications), few-shot examples, and multi-step refinement.
- Expand RAG: larger curated seeds or instructions for importing USDA data; hybrid search; metadata filtering inside the vector store.
- Richer persistence: full chat history, multiple saved profiles/plans, simple export.
- UI enhancements: better plan visualization (tables, muscle group heatmaps), history sidebar, one-click "use this plan in chat", macro pie charts, export to Markdown/PDF.
- Streaming responses in chat (when supported by the Ollama + LangChain stack).
- Multi-agent foundation: extract planning, nutrition advice, and general Q&A into specialist nodes behind the existing graph.
- Testing: Gradio-specific tests, end-to-end flows with a running Ollama, plan quality regression tests against golden profiles.
- Optional: TUI alternative, voice input (local), or integration with local calendar/todo apps.

## Final Notes
Phase 1 delivered a trustworthy, safe, local core (agent + RAG + tools + CLI + guardrails).  
Phase 2 successfully wrapped it with a convenient Gradio UI, added the expected local persistence, and made plan generation noticeably better — all while keeping the terminal CLI fully intact and everything 100% private/local.

The implementation on `feat/phase-2-ui` is ready for review. No changes were made to `main`. 

All work remains strictly local with Ollama. Safety guardrails are active in both interfaces. Persistence is shared cleanly between CLI and UI.
