"""Pydantic model for basic nutrition lookup (curated foods)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FoodItem(BaseModel):
    """Approximate nutrition info for a common food (demo / RAG use only)."""

    name: str
    calories: float = Field(description="kcal per serving or per 100g (see serving_desc)")
    protein_g: float = 0.0
    carbs_g: float = 0.0
    fat_g: float = 0.0
    serving_desc: str = Field(default="100g", description="e.g. '100g' or '1 large egg'")
    source: str = "curated"

    model_config = {"extra": "ignore"}
