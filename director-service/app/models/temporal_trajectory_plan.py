"""Temporal trajectory plan models with timed camera positions."""

from pydantic import BaseModel, Field

from app.models.scene_timeline import TimeSpan
from app.models.enums import PathType
from app.models.trajectory_plan import TrajectoryMetrics


class TimedTrajectoryPoint(BaseModel):
    timestamp: float
    position: tuple[float, float, float]
    look_at: tuple[float, float, float]
    fov: float = 60.0
    dutch: float = 0.0
    focus_distance: float = 10.0
    aperture: float = 5.6
    focal_length: float = 50.0
    lens_shift: tuple[float, float] = (0.0, 0.0)


class TemporalShotTrajectory(BaseModel):
    shot_id: str
    time_start: float
    time_end: float
    transition_in: str = "cut"
    path_type: PathType = PathType.linear
    rig_style: str = "default"
    noise_amplitude: float = 0.0
    noise_frequency: float = 0.0
    timed_points: list[TimedTrajectoryPoint] = Field(default_factory=list)
    metrics: TrajectoryMetrics = Field(default_factory=TrajectoryMetrics)


class TemporalTrajectoryPlan(BaseModel):
    plan_id: str
    scene_id: str
    time_span: TimeSpan | None = None
    trajectories: list[TemporalShotTrajectory] = Field(default_factory=list)
