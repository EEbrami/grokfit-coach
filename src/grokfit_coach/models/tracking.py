"""Longitudinal tracking event model.

Every meaningful input (intake answers, generated plans, weigh-ins, measurements,
adherence check-ins, free notes) is recorded as a timestamped TrackingEvent in the
append-only event log (see grokfit_coach.storage.db). This is the backbone of
"track the user over time".
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "intake",
    "plan_generated",
    "weight",
    "measurement",
    "adherence",
    "note",
    "migration",
]


class TrackingEvent(BaseModel):
    ts: datetime
    type: EventType
    payload: dict[str, Any] = Field(default_factory=dict)

    model_config = {"extra": "ignore"}
