"""RAG package: local FAISS + sentence-transformers over curated exercise seeds."""

from .ingest import build_exercise_index, build_indexes, load_exercise_seeds
from .retriever import get_exercise_vectorstore, retrieve_exercises

__all__ = [
    "build_indexes",
    "build_exercise_index",
    "load_exercise_seeds",
    "retrieve_exercises",
    "get_exercise_vectorstore",
]
