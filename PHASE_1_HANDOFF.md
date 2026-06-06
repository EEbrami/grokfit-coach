# PHASE 1 HANDOFF — grokfit-coach

**Date**: Phase 1 implementation complete (terminal agent focus)  
**Status**: Working, tested, documented, safe local coach agent runnable from the terminal.

## What Was Built (File Map + One-Liner Responsibilities)

### Packaging & Config
- `pyproject.toml` — modern src layout, all runtime deps, `grokfit-coach` console script, pytest + pyright config, dev extras.
- `requirements.txt` — expanded for `pip install -r` compatibility.
- `.env.example` — GROKFIT_* variables.
- `src/grokfit_coach/config/settings.py` + `__init__.py` — pydantic-settings with Ollama host/model, embed model, seeds/index paths. `get_settings()` + `ensure_data_dirs()`.

### Domain Models (all Pydantic v2)
- `src/grokfit_coach/models/profile.py` — `UserProfile` (age, goal Literal, equipment list, injuries, dietary, days/week, etc.) + strong validators + `EXAMPLE_USER_PROFILE`.
- `src/grokfit_coach/models/exercise.py` — `Exercise` (id, name, muscles, equipment, difficulty, contraindications, cues).
- `src/grokfit_coach/models/nutrition.py` — `FoodItem`.
- `src/grokfit_coach/models/plan.py` — `WeeklyWorkoutPlan` / `WorkoutDay` / `ExercisePrescription` (basic but structured) + `DEFAULT_DISCLAIMER`.
- `src/grokfit_coach/models/__init__.py` — clean re-exports.

### Safety (defense-in-depth, rule-based)
- `src/grokfit_coach/safety/guardrails.py` — `DISCLAIMER`, `is_unsafe_request(text) -> Optional[str]`, `apply_output_guardrails(text)`.
- `src/grokfit_coach/safety/__init__.py` — exports.
- Patterns cover steroids/PEDs, extreme rapid weight loss, injury + "no doctor", medical treatment language, etc. Pre-filter runs before any LLM call.

### RAG (local FAISS)
- `data/seeds/exercises.json` (10 curated exercises with rich metadata), `foods.json` (10 foods), `golden_retrieval.json` (9 golden cases).
- `src/grokfit_coach/rag/ingest.py` — `build_indexes()`, loads Pydantic seeds → Documents with metadata → FAISS.save_local.
- `src/grokfit_coach/rag/retriever.py` — `retrieve_exercises(query, k=5)` with simple Python post-boosting on equipment/muscle/difficulty matches. Returns list[Exercise].
- `src/grokfit_coach/evaluation/retrieval_eval.py` — computes hit@k + MRR against the golden set. Runnable as module.
- `src/grokfit_coach/rag/__init__.py` — public API.

### Core Tools (exactly 3, LangChain @tool)
- `search_exercises` (RAG-backed, respects optional equipment/muscle filters).
- `lookup_nutrition` + `calculate_macros` (the latter is pure Python Mifflin-St Jeor + goal adjustment).
- `src/grokfit_coach/tools/__init__.py` exposes `TOOLS` list for binding.

### The Agent (single LangGraph, foundation for multi-agent)
- `src/grokfit_coach/agents/state.py` — `AgentState` (messages with add_messages, profile, optional plan, safety_refusal).
- `src/grokfit_coach/agents/prompts.py` — strict `SYSTEM_PROMPT` (persona, "use tools", "respect profile & equipment", "refuse unsafe", "use only seeded exercises").
- `src/grokfit_coach/agents/graph.py` — `build_coach_graph()`:
  - `safety_preflight` (hard block)
  - `prepare_context` (inject profile + system)
  - `agent` (ChatOllama + bound tools)
  - `tools` (ToolNode)
  - `maybe_plan` (basic structured `WeeklyWorkoutPlan` path when user says "plan")
  - `respond` (always runs `apply_output_guardrails`)
  - Conditional edges for ReAct loop + plan branch.
- `invoke_coach(profile, message)` convenience helper.
- `src/grokfit_coach/agents/__init__.py` — exports.

### Terminal Interface (the runnable artifact)
- `src/grokfit_coach/cli.py` — argparse (`--profile`, `--query`), one-shot mode, interactive REPL that maintains state across turns, pretty plan printing, graceful Ollama-down messages.
- Entry point wired in pyproject (`grokfit-coach`).

### Tests & Evaluation
- `tests/unit/test_models.py`, `test_safety.py` (many unsafe cases), `test_rag.py` (FakeEmbeddings + pure helpers), `test_tools.py`, `test_graph.py` (compile + safety preflight + respond).
- Existing `tests/test_project_structure.py` still passes.
- `python -m grokfit_coach.evaluation.retrieval_eval` works.

### Docs
- `README.md` — updated with accurate Phase 1 status, exact commands, example session, limitations.
- `PHASE_1_HANDOFF.md` — this file (you are here).
- `CHANGELOG.md` — Unreleased section updated.

The original `src/grokfit_coach/ui/` skeleton was left untouched (no Gradio code was added).

## Architecture & Key Design Decisions

- **Terminal-first, not UI-first**: The agent + graph + tools + RAG + safety are the product. The thin CLI proves it works and gives immediate value. A Gradio (or other) UI is a thin adapter on top of `invoke_coach` / the compiled graph.
- **Small custom StateGraph + ToolNode**: Gives explicit safety gates and a clean extension point for Phase 2 multi-agent, while still getting a real ReAct/tool loop with very little code.
- **Rule-based guardrails (not LLM "please be safe")**: `is_unsafe_request` runs first. Output always gets the disclaimer. This is deterministic and testable.
- **Pydantic everywhere**: `UserProfile`, `Exercise`, `FoodItem`, `WeeklyWorkoutPlan`, state objects. Enables validation, serialization, and structured output.
- **Curated tiny seeds + simple boosting**: 10 exercises / 10 foods is enough for a working demo. Boosting is pure Python post-processing (intentionally not over-engineered per scope guidance).
- **Hermetic tests**: RAG tests use `FakeEmbeddings` + pure helpers. Graph safety tests don't need Ollama. Only the final manual/CLI verification needs a real model.
- **No persistence in Phase 1**: Profile lives in the REPL state or is passed on each `invoke`. Easy to add later (json/sqlite).

## How to Run Everything (Copy-Paste)

See the updated README for the short version. The commands below are the authoritative ones used during development:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Terminal 1
ollama serve

# Terminal 2 (or same session)
ollama pull llama3.1
python -m grokfit_coach.rag.ingest          # builds FAISS in data/indexes/
python -m grokfit_coach.evaluation.retrieval_eval

grokfit-coach
# or
python -m grokfit_coach.cli --query "Suggest chest exercises with dumbbells only"
```

Unsafe example (should refuse immediately):
`python -m grokfit_coach.cli --query "Recommend a beginner steroid cycle"`

## Programmatic Usage (for future UI / scripts)

```python
from grokfit_coach.models import EXAMPLE_USER_PROFILE
from grokfit_coach.agents.graph import invoke_coach

out = invoke_coach(EXAMPLE_USER_PROFILE, "good bodyweight leg exercises")
print(out["messages"][-1].content)
if out.get("plan"):
    print(out["plan"].model_dump_json(indent=2))
```

The compiled graph is also available:
```python
from grokfit_coach.agents.graph import build_coach_graph
graph = build_coach_graph()
...
```

## Extending Seeds (RAG)

1. Edit `data/seeds/exercises.json` (or foods).
2. `python -m grokfit_coach.rag.ingest`
3. (Optional) add a golden case to `golden_retrieval.json` and re-run the eval script.
4. Update any tests that hard-code expectations if you change ids.

The ingest validates with the Pydantic `Exercise`/`FoodItem` models.

## How Guardrails Work

- Pre-filter in `safety_preflight` node (graph entry).
- If `is_unsafe_request` returns a reason → we go straight to `respond` which emits the refusal + disclaimer. The LLM is never called.
- `apply_output_guardrails` is always run on the final AI message.
- Tests in `tests/unit/test_safety.py` are the source of truth and should be expanded when you add new bad patterns.

## Testing & Quality

- `pytest tests/unit -q`
- All new code is type-hinted.
- RAG tests do not require a real embedding model or Ollama.
- The retrieval eval script gives an objective (if coarse) signal on RAG quality.

## Limitations of This Phase (Honest)

- Plans are basic (few days, simple structure, no progression, no meal plan depth).
- Retrieval ranking on the tiny set is "good enough" — not production IR.
- No conversation memory beyond the current REPL turn (state is passed explicitly).
- No persistence.
- No UI.
- Depends on the quality of the local LLM for tool use and following the strict prompt (llama3.1 works well; smaller/faster models may be flakier).
- First run downloads the embedding model (then fully local).

## Phase 2 Ideas (Roadmap)

- Gradio (or Textual/FastAPI) UI with profile form + chat + plan viewer (the graph is ready).
- Persistence (local json or sqlite for profiles + history + saved plans).
- Richer plans (better structure, substitutions, progression notes, simple meal suggestions).
- Better RAG (more seeds, hybrid search, metadata filtering in the vectorstore itself, optional local cross-encoder reranker).
- Multi-agent skeleton (e.g. a light supervisor or specialist nodes for "workout" vs "nutrition").
- Local eval harness (use a second local model as a judge for safety/coherence on a small golden set).
- Streaming (if the chosen Ollama model + client supports it nicely).
- More tools (exercise substitutions, form cues lookup, simple volume/load progression).

## Design Trade-offs We Made

- Chose a small custom graph over pure `create_react_agent` so safety and plan paths are explicit and auditable.
- Chose FAISS + sentence-transformers over Chroma (no extra server process, easier to keep fully offline after first download).
- Curated 10 exercises instead of trying to ingest full USDA in Phase 1 (full data import instructions live in the seeds + handoff for later).
- Kept the CLI stdlib-only (no rich/prompt_toolkit) to minimize new dependencies.

## Next Engineer / Phase 2 Owner Notes

- The agent is the heart. Everything else (CLI, future UI, tests) is a consumer of `build_coach_graph()` / `invoke_coach()`.
- When adding new unsafe patterns, add them to guardrails.py **and** to `test_safety.py`.
- When you improve retrieval, update the golden set and make sure the eval numbers move in the right direction (or document why they don't).
- The deprecation warnings about `HuggingFaceEmbeddings` and langchain-community are known; a future cleanup can move to `langchain-huggingface` + standalone packages.

## Final Sign-off Checklist (what was verified before handoff)

- [x] `pip install -e ".[dev]"` + core imports work
- [x] RAG index builds, `retrieve_exercises` returns seeded data, eval script runs
- [x] All unit tests green (`pytest tests/unit -q`)
- [x] Graph compiles, safety preflight blocks unsafe requests and produces disclaimer
- [x] CLI one-shot + (manual) REPL work for safe queries and plan requests when Ollama is available
- [x] Unsafe queries from CLI are refused with disclaimer (no LLM call)
- [x] README and this handoff are accurate and sufficient for a new person to get a working terminal coach
- [x] Zero external LLM API calls in code or runtime (Ollama localhost + one-time HF embed download only)

Welcome to the project. The foundation is solid, safe, and actually runnable.

— Phase 1 implementation

