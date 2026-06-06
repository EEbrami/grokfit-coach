"""Retriever over the local FAISS exercise index with simple metadata boosting.

Kept deliberately straightforward per Phase 1 scope guidance.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import HuggingFaceEmbeddings

from grokfit_coach.config.settings import get_settings
from grokfit_coach.models import Exercise


@lru_cache(maxsize=1)
def get_exercise_vectorstore(settings: Any | None = None) -> FAISS:
    s = settings or get_settings()
    index_path = s.index_dir / "exercises"
    embeddings = HuggingFaceEmbeddings(model_name=s.embed_model_name)
    # allow_dangerous_deserialization is required for local FAISS pickles in this setup
    return FAISS.load_local(str(index_path), embeddings, allow_dangerous_deserialization=True)


def _boost_score(doc, query: str, base_score: float) -> float:
    """Very simple boosting: bump score if query tokens appear in metadata."""
    q = query.lower()
    md = doc.metadata
    boost = 0.0
    for field in ("equipment", "muscle_groups"):
        vals = md.get(field, []) or []
        for v in vals:
            if str(v).lower() in q:
                boost += 0.15
    # slight difficulty preference if mentioned
    if md.get("difficulty") and md["difficulty"].lower() in q:
        boost += 0.1
    return base_score + boost


def retrieve_exercises(
    query: str,
    k: int = 5,
    settings: Any | None = None,
) -> list[Exercise]:
    """Semantic search + lightweight metadata boosting. Returns Pydantic Exercise models."""
    vs = get_exercise_vectorstore(settings)
    # Retrieve a few extra then re-rank/boost in python
    raw = vs.similarity_search_with_score(query, k=max(k * 2, 8))

    scored = []
    for doc, score in raw:
        boosted = _boost_score(doc, query, float(score))
        ex = Exercise(
            id=doc.metadata.get("id", "unknown"),
            name=doc.metadata.get("name", doc.metadata.get("id", "unknown")),
            description=doc.page_content,
            muscle_groups=doc.metadata.get("muscle_groups", []),
            equipment=doc.metadata.get("equipment", []),
            difficulty=doc.metadata.get("difficulty", "beginner"),
            contraindications=[],  # not stored in metadata for brevity
            cues="",
        )
        scored.append((boosted, ex))

    scored.sort(key=lambda x: x[0], reverse=True)  # higher better after boost
    return [ex for _, ex in scored[:k]]
