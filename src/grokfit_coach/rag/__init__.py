"""RAG package: local FAISS + sentence-transformers over curated exercise seeds."""

from .ingest import build_indexes, build_exercise_index, load_exercise_seeds
from .retriever import retrieve_exercises, get_exercise_vectorstore

__all__ = [
    "build_indexes",
    "build_exercise_index",
    "load_exercise_seeds",
    "retrieve_exercises",
    "get_exercise_vectorstore",
]
