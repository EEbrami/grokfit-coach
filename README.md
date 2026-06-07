# grokfit-coach

**Phase 1 complete** — a strictly local, privacy-first AI personal trainer & nutrition coach that runs 100% on your machine using **Ollama**.

The agent is **fully functional from the terminal** (REPL or one-shot). It uses a single LangGraph agent with RAG (FAISS + curated seeds), LangChain tools, strong rule-based safety guardrails, and Pydantic v2 models throughout.

Everything stays on-device. No external LLM APIs are used.

## What works in Phase 1 (terminal)

- Load a rich `UserProfile` (goal, equipment, injuries, dietary needs, etc.)
- Chat naturally: "good dumbbell chest exercises for an intermediate lifter"
- The agent uses the local exercise RAG + tools to give grounded answers
- Ask for a plan: "create a 3-4 day weekly workout plan for fat loss with what I have"
- The agent produces a simple structured `WeeklyWorkoutPlan`
- **Safety guardrails** block steroids, crash diets, injury programs without professionals, medical advice, etc. — before the LLM is even called
- Every final answer includes a clear disclaimer

## Tech Stack (Phase 1)

- Python 3.11+
- LangGraph + LangChain (tools + ChatOllama)
- Pydantic v2 (all models + structured plan output)
- FAISS + sentence-transformers (local RAG)
- Ollama (local LLM only)

## Quick Start (Terminal Agent)

```bash
# 1. venv + install (editable recommended)
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start Ollama and pull a model (one time)
# (in another terminal)
ollama serve
ollama pull llama3.1

# 3. Build the local RAG index from seeds (one time, or after editing seeds)
python -m grokfit_coach.rag.ingest

# 4. Run the coach
grokfit-coach
# or
python -m grokfit_coach.cli

# One-shot example
python -m grokfit_coach.cli --query "Suggest 3 dumbbell exercises for chest"
```

On first RAG build it will download the small embedding model (~80-100 MB). After that everything is fully offline.

## Example Interaction (what you will see)

```
GrokFit Coach (100% local via Ollama)
Profile: Alex Rivera | Goal: fat_loss | Level: intermediate
...

You: good beginner dumbbell chest exercises
Coach: Relevant exercises from the local knowledge base:
- Dumbbell Bench Press ...
(plus disclaimer)

You: create a simple 3 day plan with what I have
Coach: ...
=== Weekly Plan for Alex Rivera (goal: fat_loss) ===
...
(plus disclaimer)
```

Unsafe requests are refused immediately with a helpful message + disclaimer.

## Project Layout (key pieces)

```
src/grokfit_coach/
├── agents/          # LangGraph state, prompts, graph (the agent)
├── config/          # pydantic-settings (Ollama host/model, paths)
├── models/          # UserProfile, Exercise, FoodItem, WeeklyWorkoutPlan (all Pydantic v2)
├── rag/             # ingest + retriever (FAISS) + retrieval_eval
├── safety/          # guardrails (is_unsafe_request + forced disclaimer)
├── tools/           # 3 LangChain @tools (search_exercises, lookup_nutrition, calculate_macros)
└── cli.py           # thin terminal REPL / one-shot (the runnable Phase 1 artifact)

data/seeds/          # committed curated exercises.json, foods.json, golden set
tests/unit/          # pytest (models, safety, rag-fakes, tools, graph)
```

## Running the Terminal CLI (Phase 1 + Persistence)

```bash
# After `pip install -e .`
grokfit-coach
# or
python -m grokfit_coach.cli

# One-shot example
grokfit-coach --query "Suggest chest exercises with dumbbells only"

# With explicit profile (overrides persisted one)
grokfit-coach --profile myprofile.json --query "create a 3 day plan"
```

The CLI automatically loads your profile from `~/.grokfit/profile.json` (or falls back to example) and auto-saves generated plans.

## Running the Gradio UI (Phase 2)

```bash
# After `pip install -e .`
grokfit-coach-ui
# or
python -m grokfit_coach.ui.app
```

Then open http://127.0.0.1:7860 in your browser.

**UI Tabs**:
- **Profile**: Fill the form (name, age, goal, equipment, injuries, etc.). Click "Save Profile". This persists to `~/.grokfit/profile.json` and is used by Chat and Plans.
- **Coach Chat**: Type questions or "create a weekly plan for me". The agent uses your saved profile. All responses go through safety guardrails.
- **Plans**: Click "Generate / Regenerate Weekly Plan" to create an improved plan using the Phase 2 logic. The last plan is also auto-loaded from persistence.

**Persistence Sharing**: The terminal CLI and UI share the same `~/.grokfit/` JSON files. Save a profile in the UI → it appears in the CLI (and vice versa). Generated plans appear in the UI Plans tab.

**Safety**: Unsafe requests (steroids, crash diets, injury advice without professionals, etc.) are blocked by guardrails before the LLM is called, in both CLI and UI. Every final response includes the standard disclaimer.

## Project Layout (key pieces)

```
src/grokfit_coach/
├── agents/          # LangGraph state, prompts, graph (the agent)
├── config/          # pydantic-settings (Ollama host/model, paths)
├── models/          # UserProfile, Exercise, FoodItem, WeeklyWorkoutPlan (all Pydantic v2)
├── rag/             # ingest + retriever (FAISS) + retrieval_eval
├── safety/          # guardrails (is_unsafe_request + forced disclaimer)
├── tools/           # 3 LangChain @tools (search_exercises, lookup_nutrition, calculate_macros)
├── cli.py           # thin terminal REPL / one-shot (unchanged, now with optional persistence)
├── persistence.py   # local JSON save/load for profile + last plan (~/.grokfit/)
└── ui/
    └── app.py       # Gradio UI (Profile / Coach Chat / Plans tabs)

data/seeds/          # committed curated exercises.json, foods.json, golden set
tests/unit/          # pytest (models, safety, rag-fakes, tools, graph)
```

## Development

```bash
pytest tests/unit -q
python -m grokfit_coach.evaluation.retrieval_eval
python -m grokfit_coach.rag.ingest   # after editing seeds
grokfit-coach-ui                     # launch the web UI (after `pip install -e .`)
```

Type checking: the project has `[tool.pyright]` in pyproject.toml. Run `pyright src/grokfit_coach` (or your preferred checker).

## Status & Limitations

**Current Status (feat/phase-2-ui branch)**

Phase 1 (solid local terminal agent) + Phase 2 (Gradio UI + persistence + improved plans) are complete.

- Full conversational agent (terminal CLI + Gradio UI) using RAG, tools, and strong safety guardrails.
- Improved weekly workout plan generation with better profile awareness, filtering, validation, and fallbacks.
- Basic but effective local persistence (`~/.grokfit/profile.json` and `last_plan.json`) shared between CLI and UI.
- Gradio UI with Profile / Coach Chat / Plans tabs.
- Terminal CLI (`grokfit-coach`) remains fully functional and unchanged in behavior.

**Limitations**:
- Plan quality still depends on the capabilities of the local Ollama model (structured output + following instructions). Improved in Phase 2 but not perfect.
- Small curated seed dataset (10 exercises / 10 foods).
- Persistence is last-plan only (no full chat history or multiple saved plans).
- UI is functional but basic Gradio (no advanced styling or mobile optimizations yet).

See `PHASE_1_HANDOFF.md` for Phase 1 details and `PHASE_2_HANDOFF.md` for Phase 2 specifics, design decisions, and next steps.

## Safety First

Strong guardrails (pre-filter + post-processing) are present from the very first line of the agent. Unsafe requests are blocked. Every answer contains a clear medical disclaimer. This is non-negotiable.

## License

MIT (see LICENSE).
