"""Scene timeline models for time-varying scenes."""

from pydantic import BaseModel, Field, model_validator

from app.models.scene_summary import Bounds, SceneObject, SpatialRelation, FreeSpace


class TimeSpan(BaseModel):
    start: float
    end: float
    duration: float


class ObjectTrackSample(BaseModel):
    timestamp: float
    position: tuple[float, float, float]
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    velocity: tuple[float, float, float] = (0.0, 0.0, 0.0)
    visible: bool = True


class MotionDescriptor(BaseModel):
    average_speed: float = 0.0
    max_speed: float = 0.0
    direction_trend: tuple[float, float, float] = (0.0, 0.0, 0.0)
    acceleration_bucket: str = "constant"
    total_displacement: float = 0.0


class ObjectTrack(BaseModel):
    object_id: str
    samples: list[ObjectTrackSample] = Field(default_factory=list)
    motion: MotionDescriptor = Field(default_factory=MotionDescriptor)
    keyframe_indices: list[int] = Field(default_factory=list)


class SceneEvent(BaseModel):
    event_id: str
    event_type: str
    timestamp: float
    duration: float = 0.0
    object_ids: list[str] = Field(default_factory=list)
    description: str = ""


class SemanticSceneEvent(BaseModel):
    semantic_id: str
    label: str
    time_start: float
    time_end: float
    object_ids: list[str] = Field(default_factory=list)
    summary: str = ""
    dramatic_role: str = "develop"
    camera_implication: str = "maintain_subject_continuity"
    salience: float = 0.5
    confidence: float = 0.5
    evidence_event_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class CameraCandidate(BaseModel):
    region_id: str
    time_start: float
    time_end: float
    center: tuple[float, float, float]
    radius: float
    clearance_score: float = 0.5


class SceneTimeline(BaseModel):
    schema_version: str = "1.0"
    scene_id: str
    scene_name: str
    scene_type: str
    description: str = ""
    bounds: Bounds
    time_span: TimeSpan
    objects_static: list[SceneObject] = Field(default_factory=list)
    object_tracks: list[ObjectTrack] = Field(default_factory=list)
    # Backward-compatible event field used by older runtimes/fixtures.
    events: list[SceneEvent] = Field(default_factory=list)
    # Deterministic, geometry-derived event stream from Unity/backend rules.
    raw_events: list[SceneEvent] = Field(default_factory=list)
    # LLM-interpreted narrative event layer for readability/directing cues.
    semantic_events: list[SemanticSceneEvent] = Field(default_factory=list)
    camera_candidates: list[CameraCandidate] = Field(default_factory=list)
    relations: list[SpatialRelation] = Field(default_factory=list)
    free_space: FreeSpace | None = None

    @model_validator(mode="after")
    def _sync_event_layers(self) -> "SceneTimeline":
        # Accept legacy payloads that only provide "events".
        if not self.raw_events and self.events:
            self.raw_events = list(self.events)
        # Keep legacy "events" populated for older clients.
        if not self.events and self.raw_events:
            self.events = list(self.raw_events)
        return self
