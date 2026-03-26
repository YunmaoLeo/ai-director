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


class CameraProgramItem(BaseModel):
    camera_id: str
    role: str = "virtual_camera"
    primary_subject: str = "room"
    shot_type_bias: str = "wide"
    movement_bias: str = "steady"
    notes: str = ""


class CutDecisionItem(BaseModel):
    cut_id: str
    timestamp: float
    from_camera_id: str = ""
    to_camera_id: str = ""
    transition: str = TransitionType.cut.value
    reason: str = ""
    shot_id: str = ""


class TemporalDirectingPlan(BaseModel):
    plan_id: str
    scene_id: str
    intent: str
    summary: str = ""
    time_span: TimeSpan | None = None
    director_policy: str = "balanced"
    director_rationale: str = ""
    beats: list[Beat] = Field(default_factory=list)
    shots: list[TemporalShot] = Field(default_factory=list)
    camera_program: list[CameraProgramItem] = Field(default_factory=list)
    edit_decision_list: list[CutDecisionItem] = Field(default_factory=list)
