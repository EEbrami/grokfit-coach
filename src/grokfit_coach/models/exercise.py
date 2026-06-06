"""Pydantic model for exercises (used by RAG and plan generation)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class Exercise(BaseModel):
    """A single exercise with metadata for retrieval and safe recommendation."""

    id: str = Field(..., min_length=1, description="Stable identifier e.g. ex_001")
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=3)
    muscle_groups: list[str] = Field(default_factory=list, description="e.g. ['chest', 'triceps']")
    equipment: list[str] = Field(default_factory=list, description="e.g. ['dumbbells', 'none']")
    difficulty: str = Field(default="beginner", description="beginner | novice | intermediate | advanced")
    contraindications: list[str] = Field(default_factory=list)
    cues: str = Field(default="", description="Form cues or safety notes")

    model_config = {"extra": "ignore"}
