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

The `ui/` directory from the original skeleton is untouched (Gradio UI is planned for a later phase).

## Development

```bash
pytest tests/unit -q
python -m grokfit_coach.evaluation.retrieval_eval
python -m grokfit_coach.rag.ingest   # after editing seeds
```

Type checking: the project has `[tool.pyright]` in pyproject.toml. Run `pyright src/grokfit_coach` (or your preferred checker).

## Status & Limitations (Phase 1)

- Working conversational agent in the terminal with RAG + tools + safety.
- Basic structured weekly workout plans (intentionally kept simple).
- Small curated seed data (easy to extend).
- No persistence, no UI, no multi-agent, no streaming.
- Plan quality and retrieval ranking are "good enough for a tiny curated set" — the focus was on a safe, working loop.

See `PHASE_1_HANDOFF.md` for design decisions, how to extend seeds, how to call the agent from Python, and the Phase 2 roadmap.

## Safety First

Strong guardrails (pre-filter + post-processing) are present from the very first line of the agent. Unsafe requests are blocked. Every answer contains a clear medical disclaimer. This is non-negotiable.

## License

MIT (see LICENSE).
