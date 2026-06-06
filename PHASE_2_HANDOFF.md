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

## How to Run Phase 2 (Terminal + UI)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Terminal 1
ollama serve

# Terminal 2
ollama pull llama3.1
python -m grokfit_coach.rag.ingest

# Terminal CLI (unchanged experience)
grokfit-coach
# or with explicit profile override
grokfit-coach --profile some.json --query "create a plan"

# New Gradio UI
grokfit-coach-ui
# or
python -m grokfit_coach.ui.app
```

In the UI:
1. Go to **Profile** tab → adjust fields (or Load Saved) → Save.
2. Go to **Coach Chat** → talk naturally (including "make me a plan..."). Your saved profile is used.
3. Go to **Plans** tab → Generate. Improved plans appear (better constraint adherence + fallback).

Unsafe requests are still refused before reaching the LLM in both interfaces.

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

## Limitations of Phase 2
- Plan quality is improved but still ultimately depends on the local LLM's structured-output reliability and prompt following.
- UI is functional Gradio (not heavily styled or mobile-optimized).
- Persistence is last-plan only (no full history or multiple saved plans).
- Profile form in UI uses simple comma-separated text for lists (works because of the existing validator, but could be multi-select in future).
- No meal-plan UI or deeper nutrition features.

## Next Steps / Phase 3 Ideas
- Better / more reliable plan generation (tool-augmented planning, more RAG context, few-shot examples in structured calls, or a dedicated planning tool that the ReAct loop can use iteratively).
- Expand seeds or add hybrid retrieval.
- Richer UI (better plan visualization, history, export to markdown/PDF, macro charts).
- Optional streaming in chat (if Ollama + LangChain client supports it well).
- Multi-agent skeleton (e.g. separate planner vs. Q&A specialist nodes behind the same graph entrypoint).
- More tests: Gradio component tests, real-Ollama integration tests (marked), plan quality regression suite.
- Persistence versioning or multiple named profiles.

## Final Notes
Phase 1 gave us a trustworthy, safe, local core agent + CLI.  
Phase 2 wrapped it in a convenient UI, added the persistence users expect, and made the plans noticeably better without sacrificing the foundation or the terminal experience.

The branch `feat/phase-2-ui` is ready for review/merge into the Phase 1 branch (or main later per the overall strategy).

All work remains 100% local and private.
