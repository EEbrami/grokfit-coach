"""Ingestion script: build local FAISS index(es) from curated seeds.

Run: python -m grokfit_coach.rag.ingest
(or call build_indexes() from Python).

This is the only step that needs network on first run (downloads the embed model).
After that everything is local.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document

from grokfit_coach.config.settings import get_settings, ensure_data_dirs
from grokfit_coach.models import Exercise, FoodItem


def _load_json(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_exercise_seeds(settings: Any | None = None) -> list[Exercise]:
    s = settings or get_settings()
    path = s.seeds_dir / "exercises.json"
    raw = _load_json(path)
    return [Exercise.model_validate(item) for item in raw]


def load_food_seeds(settings: Any | None = None) -> list[FoodItem]:
    s = settings or get_settings()
    path = s.seeds_dir / "foods.json"
    raw = _load_json(path)
    return [FoodItem.model_validate(item) for item in raw]


def _exercise_to_document(ex: Exercise) -> Document:
    content = (
        f"{ex.name}. {ex.description}. "
        f"Muscles: {', '.join(ex.muscle_groups)}. "
        f"Equipment: {', '.join(ex.equipment)}. "
        f"Difficulty: {ex.difficulty}. "
        f"Cues: {ex.cues}"
    )
    metadata = {
        "id": ex.id,
        "name": ex.name,
        "type": "exercise",
        "difficulty": ex.difficulty,
        "muscle_groups": ex.muscle_groups,
        "equipment": ex.equipment,
    }
    return Document(page_content=content, metadata=metadata)


def build_exercise_index(settings: Any | None = None) -> FAISS:
    s = settings or get_settings()
    ensure_data_dirs(s)

    exercises = load_exercise_seeds(s)
    docs = [_exercise_to_document(ex) for ex in exercises]

    embeddings = HuggingFaceEmbeddings(model_name=s.embed_model_name)
    vectorstore = FAISS.from_documents(docs, embeddings)

    index_path = s.index_dir / "exercises"
    vectorstore.save_local(str(index_path))
    print(f"Built exercise index with {len(docs)} documents -> {index_path}")
    return vectorstore


def build_indexes() -> None:
    """Idempotent entry point. Builds the main exercise index (foods kept simple for Phase 1)."""
    build_exercise_index()
    print("RAG indexes built successfully.")


if __name__ == "__main__":
    build_indexes()
