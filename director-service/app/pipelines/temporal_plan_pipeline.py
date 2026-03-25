"""Temporal planning pipeline: timeline -> abstraction -> multi-pass LLM -> trajectory -> validation -> save."""

from dataclasses import dataclass, field
from pathlib import Path

from app.models.scene_timeline import SceneTimeline
from app.models.temporal_cinematic_scene import TemporalCinematicScene
from app.models.temporal_directing_plan import TemporalDirectingPlan
from app.models.temporal_trajectory_plan import TemporalTrajectoryPlan
from app.models.validation_report import ValidationReport
from app.models.planning_pass import PlanningPassArtifact
from app.services.temporal_abstraction import TemporalAbstractor
from app.services.temporal_plan_orchestrator import TemporalPlanOrchestrator
from app.services.temporal_trajectory_solver import TemporalTrajectorySolver
from app.services.temporal_plan_validator import TemporalPlanValidator
from app.services.cinematic_style import build_style_brief
from app.services.file_manager import FileManager
from app.services.llm_client import create_llm_client, MockTemporalLLMClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class TemporalPipelineResult:
    timeline: SceneTimeline
    temporal_cinematic: TemporalCinematicScene
    temporal_directing_plan: TemporalDirectingPlan
    temporal_trajectory_plan: TemporalTrajectoryPlan
    validation_report: ValidationReport
    pass_artifacts: list[PlanningPassArtifact] = field(default_factory=list)
    cinematic_style: str = "default"
    style_rationale: str = ""


class TemporalPlanPipeline:
    def __init__(
        self,
        llm_provider: str = "mock",
        llm_model: str | None = None,
        output_dir: str | Path = "outputs",
        scenes_dir: str | Path = "scenes",
    ):
        self._abstractor = TemporalAbstractor()
        if llm_provider == "mock":
            self._llm_client = MockTemporalLLMClient()
        else:
            self._llm_client = create_llm_client(llm_provider, model=llm_model)
        self._orchestrator = TemporalPlanOrchestrator(self._llm_client)
        self._solver = TemporalTrajectorySolver()
        self._validator = TemporalPlanValidator()
        self._file_manager = FileManager(output_dir, scenes_dir)

    def run(
        self,
        timeline: SceneTimeline,
        intent: str,
        save: bool = True,
        prefix: str = "",
        style_profile: str | None = None,
        style_notes: str | None = None,
    ) -> TemporalPipelineResult:
        """Run the full temporal planning pipeline."""
        logger.info("Running temporal pipeline for scene_id=%s", timeline.scene_id)

        # Step 1: Temporal abstraction
        logger.info("Building temporal cinematic scene abstraction...")
        temporal_cinematic = self._abstractor.abstract(timeline)

        # Step 2: Multi-pass LLM orchestration
        logger.info("Running multi-pass LLM orchestration (intent: %s)...", intent)
        requested_style = (style_profile or "auto").strip().lower()
        provided_style_brief = ""
        if requested_style not in ("", "auto", "llm"):
            _, provided_style_brief = build_style_brief(requested_style, style_notes)
        directing_plan, pass_artifacts, selected_style, style_rationale = self._orchestrator.orchestrate(
            timeline,
            temporal_cinematic,
            intent,
            style_profile=requested_style,
            style_brief=provided_style_brief,
        )

        # Step 3: Validate directing plan
        logger.info("Validating temporal directing plan...")
        dp_report = self._validator.validate_temporal_directing_plan(
            directing_plan, timeline
        )

        # Step 4: Solve temporal trajectories
        logger.info("Solving temporal trajectories...")
        trajectory_plan = self._solver.solve(directing_plan, timeline)

        # Step 5: Validate trajectory plan
        logger.info("Validating temporal trajectory plan...")
        tp_report = self._validator.validate_temporal_trajectory_plan(
            trajectory_plan, directing_plan, timeline
        )

        # Merge reports
        combined_report = ValidationReport(
            is_valid=dp_report.is_valid and tp_report.is_valid,
            errors=dp_report.errors + tp_report.errors,
            warnings=dp_report.warnings + tp_report.warnings,
        )

        # Step 6: Save outputs
        if save and prefix:
            self._file_manager.save_scene_timeline(timeline, prefix)
            self._file_manager.save_temporal_directing_plan(directing_plan, prefix)
            self._file_manager.save_temporal_trajectory_plan(trajectory_plan, prefix)
            self._file_manager.save_validation_report(combined_report, prefix)
            self._file_manager.save_pass_artifacts(pass_artifacts, prefix)
            logger.info("All temporal outputs saved with prefix: %s", prefix)

        return TemporalPipelineResult(
            timeline=timeline,
            temporal_cinematic=temporal_cinematic,
            temporal_directing_plan=directing_plan,
            temporal_trajectory_plan=trajectory_plan,
            validation_report=combined_report,
            pass_artifacts=pass_artifacts,
            cinematic_style=selected_style,
            style_rationale=style_rationale,
        )
