"""Temporal directing plan models with beats and time-parameterized shots."""

from pydantic import BaseModel, Field

from app.models.scene_timeline import TimeSpan
from app.models.temporal_enums import TransitionType


class Beat(BaseModel):
    beat_id: str
    time_start: float
    time_end: float
    goal: str
    mood: str = "neutral"
    subjects: list[str] = Field(default_factory=list)


class TemporalShot(BaseModel):
    shot_id: str
    time_start: float
    time_end: float
    goal: str
    subject: str
    shot_type: str
    movement: str
    pacing: str = "steady"
    constraints: dict = Field(default_factory=dict)
    rationale: str = ""
    transition_in: str = TransitionType.cut.value
    beat_id: str = ""


class TemporalDirectingPlan(BaseModel):
    plan_id: str
    scene_id: str
    intent: str
    summary: str = ""
    time_span: TimeSpan | None = None
    beats: list[Beat] = Field(default_factory=list)
    shots: list[TemporalShot] = Field(default_factory=list)
