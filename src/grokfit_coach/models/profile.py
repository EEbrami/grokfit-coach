"""Pydantic models for core user profile data."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AthleteProfile(BaseModel):
    """Basic profile used by planning and coaching agents."""

    name: str = Field(..., min_length=1, description="Athlete display name")
    goal: str = Field(..., min_length=3, description="Primary fitness goal")
    activity_level: str = Field(
        default="moderate",
        description="Current activity level (e.g., low, moderate, high)",
    )
