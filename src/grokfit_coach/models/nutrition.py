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

    # --- Phase 3: grounding in the local nutrition DB + safety/diet flags ---
    fdc_id: int | None = Field(default=None, description="USDA FoodData Central id, when DB-grounded")
    grams: float | None = Field(default=None, description="Numeric portion in grams (complements serving_desc)")
    diet_flags: list[str] = Field(
        default_factory=list, description="e.g. ['vegan', 'vegetarian'] derived from a curated map / OFF labels"
    )
    allergen_flags: list[str] = Field(
        default_factory=list,
        description="Allergens KNOWN to be present, e.g. ['milk']. Absence != allergen-free (fail closed).",
    )

    model_config = {"extra": "ignore"}
