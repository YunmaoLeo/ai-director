"""Scene timeline models for time-varying scenes."""

from pydantic import BaseModel, Field

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


class CameraCandidate(BaseModel):
    region_id: str
    time_start: float
    time_end: float
    center: tuple[float, float, float]
    radius: float
    clearance_score: float = 0.5


class SceneTimeline(BaseModel):
    scene_id: str
    scene_name: str
    scene_type: str
    description: str = ""
    bounds: Bounds
    time_span: TimeSpan
    objects_static: list[SceneObject] = Field(default_factory=list)
    object_tracks: list[ObjectTrack] = Field(default_factory=list)
    events: list[SceneEvent] = Field(default_factory=list)
    camera_candidates: list[CameraCandidate] = Field(default_factory=list)
    relations: list[SpatialRelation] = Field(default_factory=list)
    free_space: FreeSpace | None = None
