"""Evaluation package for grokfit-coach (RAG quality, guardrails, etc.)."""

from .retrieval_eval import main as run_retrieval_eval
from .retrieval_eval import run_eval

__all__ = ["run_eval", "run_retrieval_eval"]
