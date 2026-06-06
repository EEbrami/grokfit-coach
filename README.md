# grokfit-coach

A clean, local-first Python foundation for building an AI-powered personal fitness coach that runs **100% locally**.

`grokfit-coach` is designed for a future multi-agent system (LangGraph) that can support workout planning, nutrition guidance, and conversational coaching while keeping user data private on-device.

## Core Principles

- **Local-only inference:** uses Ollama models running on your machine
- **No external API dependency:** no cloud LLM calls required
- **Composable multi-agent design:** built around LangGraph
- **Type-safe domain models:** built with Pydantic

## Tech Stack

- Python 3.11+
- [LangGraph](https://github.com/langchain-ai/langgraph)
- [Pydantic v2](https://docs.pydantic.dev/)
- [Ollama](https://ollama.com/) for local model serving

## Project Layout

```text
.
├── docs/
├── src/
│   └── grokfit_coach/
│       ├── agents/
│       ├── evaluation/
│       ├── models/
│       ├── rag/
│       ├── tools/
│       ├── ui/
│       └── utils/
├── tests/
├── LICENSE
├── PHASE_1_HANDOFF.md
└── requirements.txt
```

## Local Setup

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Install and start Ollama (if not already installed), then pull a model:

   ```bash
   ollama pull llama3.1
   ```

4. Verify package imports:

   ```bash
   python -c "from grokfit_coach.models.profile import AthleteProfile; print(AthleteProfile(name='Alex', goal='fat_loss').model_dump())"
   ```

## Status

This repository currently provides the initial professional scaffold for Phase 1 development.
