from pydantic import BaseModel, Field

from app.models.enums import PathType


class TrajectoryMetrics(BaseModel):
    visibility_score: float = 0.0
    smoothness_score: float = 0.0
    framing_score: float = 0.0
    occlusion_risk: float = 0.0
    clearance_score: float = 0.0


class ShotTrajectory(BaseModel):
    shot_id: str
    start_position: tuple[float, float, float]
    end_position: tuple[float, float, float]
    look_at_position: tuple[float, float, float]
    fov: float = 60.0
    path_type: PathType = PathType.linear
    sampled_points: list[tuple[float, float, float]] = Field(default_factory=list)
    duration: float = 3.0
    metrics: TrajectoryMetrics = Field(default_factory=TrajectoryMetrics)


class TrajectoryPlan(BaseModel):
    plan_id: str
    scene_id: str
    total_duration: float
    trajectories: list[ShotTrajectory]
