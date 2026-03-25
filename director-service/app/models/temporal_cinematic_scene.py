"""Temporal cinematic scene models extending static CinematicScene with time-aware data."""

from pydantic import BaseModel, Field

from app.models.scene_timeline import TimeSpan
from app.models.cinematic_scene import (
    SemanticRegion,
    CinematicAffordance,
    VisibilityHint,
    FramingHint,
    ObjectGroup,
)


class SubjectTemporalProfile(BaseModel):
    object_id: str
    role: str = "primary"
    salience_score: float = 0.5
    active_windows: list[tuple[float, float]] = Field(default_factory=list)
    motion_summary: str = ""


class SpaceTimeAffordance(BaseModel):
    affordance_id: str
    type: str
    description: str
    time_start: float
    time_end: float
    object_ids: list[str] = Field(default_factory=list)
    score: float = 0.5


class OcclusionRiskWindow(BaseModel):
    time_start: float
    time_end: float
    blocker_id: str
    blocked_id: str
    severity: float = 0.5


class RevealOpportunity(BaseModel):
    time: float
    object_id: str
    description: str = ""
    score: float = 0.5


class TemporalCinematicScene(BaseModel):
    scene_id: str
    semantic_regions: list[SemanticRegion] = Field(default_factory=list)
    primary_subjects: list[str] = Field(default_factory=list)
    secondary_subjects: list[str] = Field(default_factory=list)
    object_groups: list[ObjectGroup] = Field(default_factory=list)
    spatial_summary: str = ""
    cinematic_affordances: list[CinematicAffordance] = Field(default_factory=list)
    visibility_hints: list[VisibilityHint] = Field(default_factory=list)
    framing_hints: list[FramingHint] = Field(default_factory=list)
    subject_profiles: list[SubjectTemporalProfile] = Field(default_factory=list)
    spacetime_affordances: list[SpaceTimeAffordance] = Field(default_factory=list)
    occlusion_risks: list[OcclusionRiskWindow] = Field(default_factory=list)
    reveal_opportunities: list[RevealOpportunity] = Field(default_factory=list)
    event_summary: str = ""
    replay_description: str = ""
    time_span: TimeSpan | None = None
