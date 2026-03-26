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


class TemporalShotTrajectory(BaseModel):
    shot_id: str
    time_start: float
    time_end: float
    transition_in: str = "cut"
    path_type: PathType = PathType.linear
    timed_points: list[TimedTrajectoryPoint] = Field(default_factory=list)
    metrics: TrajectoryMetrics = Field(default_factory=TrajectoryMetrics)


class TemporalTrajectoryPlan(BaseModel):
    plan_id: str
    scene_id: str
    time_span: TimeSpan | None = None
    trajectories: list[TemporalShotTrajectory] = Field(default_factory=list)
