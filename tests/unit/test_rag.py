"""RAG tests focused on pure helpers (boost, model mapping) so they stay fast and hermetic.

Full vector behavior is covered by the retrieval_eval script + manual checks after ingest.
"""

from __future__ import annotations

from langchain_core.documents import Document

from grokfit_coach.models import Exercise
from grokfit_coach.rag.retriever import _boost_score


def test_boost_score_gives_higher_rank_to_matching_equipment():
    doc = Document(
        page_content="Dumbbell Bench Press",
        metadata={"id": "ex_003", "name": "Dumbbell Bench Press", "equipment": ["dumbbells"], "muscle_groups": ["chest"], "difficulty": "novice"},
    )
    base = 0.8
    boosted = _boost_score(doc, "dumbbell chest beginner", base)
    assert boosted > base  # equipment + muscle token match should boost


def test_exercise_roundtrip_from_doc():
    doc = Document(
        page_content="Test Move. A simple test.",
        metadata={
            "id": "ex_t",
            "name": "Test Move",
            "equipment": ["dumbbells"],
            "muscle_groups": ["chest"],
            "difficulty": "beginner",
        },
    )
    ex = Exercise(
        id=doc.metadata["id"],
        name=doc.metadata["name"],
        description=doc.page_content,
        muscle_groups=doc.metadata.get("muscle_groups", []),
        equipment=doc.metadata.get("equipment", []),
        difficulty=doc.metadata.get("difficulty", "beginner"),
    )
    assert ex.id == "ex_t"
    assert "dumbbells" in ex.equipment

