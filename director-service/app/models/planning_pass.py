"""Planning pass artifact and run bundle models for multi-pass orchestration."""

from pydantic import BaseModel, Field

from app.models.temporal_enums import PlanningPassType
from app.models.scene_timeline import SceneTimeline
from app.models.temporal_directing_plan import TemporalDirectingPlan
from app.models.temporal_trajectory_plan import TemporalTrajectoryPlan
from app.models.validation_report import ValidationReport


class PlanningPassArtifact(BaseModel):
    pass_type: PlanningPassType
    pass_index: int = 0
    model_provider: str = ""
    model_id: str = ""
    input_summary: str = ""
    output_raw: str = ""
    output_parsed: dict = Field(default_factory=dict)
    duration_ms: float = 0.0
    success: bool = True
    error_message: str = ""


class TemporalRunBundle(BaseModel):
    run_id: str
    scene_id: str
    intent: str
    created_at: str = ""
    scene_timeline_snapshot: SceneTimeline | None = None
    pass_artifacts: list[PlanningPassArtifact] = Field(default_factory=list)
    temporal_directing_plan: TemporalDirectingPlan | None = None
    temporal_trajectory_plan: TemporalTrajectoryPlan | None = None
    validation_report: ValidationReport | None = None
