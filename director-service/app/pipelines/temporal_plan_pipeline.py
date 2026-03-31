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
from app.services.temporal_event_interpreter import TemporalEventInterpreter
from app.services.temporal_plan_orchestrator import TemporalPlanOrchestrator
from app.services.temporal_trajectory_solver import TemporalTrajectorySolver
from app.services.temporal_plan_validator import TemporalPlanValidator
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
    director_policy: str = "balanced"
    director_rationale: str = ""


class TemporalPlanPipeline:
    def __init__(
        self,
        llm_provider: str = "mock",
        llm_model: str | None = None,
        output_dir: str | Path = "outputs",
        scenes_dir: str | Path = "scenes",
    ):
        self._abstractor = TemporalAbstractor()
        self._event_interpreter = TemporalEventInterpreter()
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
        director_hint: str | None = None,
        director_notes: str | None = None,
        planning_mode: str = "freeform_llm",
    ) -> TemporalPipelineResult:
        """Run the full temporal planning pipeline."""
        logger.info(
            "Temporal pipeline started for scene_id=%s planning_mode=%s intent='%s'",
            timeline.scene_id,
            planning_mode,
            " ".join(intent.split())[:120],
        )

        if not timeline.raw_events and timeline.events:
            timeline.raw_events = list(timeline.events)
        if not timeline.events and timeline.raw_events:
            timeline.events = list(timeline.raw_events)

        if not timeline.semantic_events:
            cached_semantic_events = self._file_manager.load_cached_semantic_events(timeline)
            if cached_semantic_events:
                logger.info(
                    "Stage 0/5 [semantic] loaded %d semantic events from cache for scene_id=%s",
                    len(cached_semantic_events),
                    timeline.scene_id,
                )
                timeline.semantic_events = cached_semantic_events
            else:
                logger.info("Stage 0/5 [semantic] interpreting raw event layer for scene_id=%s", timeline.scene_id)
                timeline.semantic_events = self._event_interpreter.interpret(
                    timeline=timeline,
                    intent=intent,
                    llm_client=self._llm_client,
                )
                if timeline.semantic_events:
                    self._file_manager.save_cached_semantic_events(timeline, timeline.semantic_events)
                    logger.info(
                        "Stage 0/5 [semantic] produced %d semantic events for scene_id=%s",
                        len(timeline.semantic_events),
                        timeline.scene_id,
                    )

        # Step 1: Temporal abstraction
        logger.info("Stage 1/5 [abstraction] building temporal cinematic abstraction...")
        temporal_cinematic = self._abstractor.abstract(timeline)
        logger.info(
            "Stage 1/5 [abstraction] completed for scene_id=%s replay_desc_chars=%d",
            timeline.scene_id,
            len(temporal_cinematic.replay_description),
        )

        # Step 2: Multi-pass LLM orchestration
        logger.info("Stage 2/5 [orchestration] running multi-pass planner...")
        requested_policy = (director_hint or "auto").strip().lower()
        provided_policy_notes = (director_notes or "").strip()
        directing_plan, pass_artifacts, selected_policy, policy_rationale = self._orchestrator.orchestrate(
            timeline,
            temporal_cinematic,
            intent,
            style_profile=requested_policy,
            style_brief=provided_policy_notes,
            planning_mode=planning_mode,
        )
        logger.info(
            "Stage 2/5 [orchestration] completed plan_id=%s policy=%s shots=%d artifacts=%d",
            directing_plan.plan_id,
            selected_policy,
            len(directing_plan.shots),
            len(pass_artifacts),
        )

        # Step 3: Validate directing plan
        logger.info("Stage 3/5 [directing-validation] validating plan_id=%s", directing_plan.plan_id)
        dp_report = self._validator.validate_temporal_directing_plan(
            directing_plan, timeline
        )
        logger.info(
            "Stage 3/5 [directing-validation] completed valid=%s errors=%d warnings=%d",
            dp_report.is_valid,
            len(dp_report.errors),
            len(dp_report.warnings),
        )

        # Step 4: Solve temporal trajectories
        logger.info("Stage 4/5 [trajectory] solving trajectories for plan_id=%s", directing_plan.plan_id)
        trajectory_plan = self._solver.solve(directing_plan, timeline)
        logger.info(
            "Stage 4/5 [trajectory] completed trajectory_id=%s trajectories=%d",
            trajectory_plan.plan_id,
            len(trajectory_plan.trajectories),
        )

        # Step 5: Validate trajectory plan
        logger.info("Stage 5/5 [trajectory-validation] validating trajectory_id=%s", trajectory_plan.plan_id)
        tp_report = self._validator.validate_temporal_trajectory_plan(
            trajectory_plan, directing_plan, timeline
        )
        logger.info(
            "Stage 5/5 [trajectory-validation] completed valid=%s errors=%d warnings=%d",
            tp_report.is_valid,
            len(tp_report.errors),
            len(tp_report.warnings),
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

        logger.info(
            "Temporal pipeline finished for scene_id=%s plan_valid=%s total_errors=%d total_warnings=%d",
            timeline.scene_id,
            combined_report.is_valid,
            len(combined_report.errors),
            len(combined_report.warnings),
        )

        return TemporalPipelineResult(
            timeline=timeline,
            temporal_cinematic=temporal_cinematic,
            temporal_directing_plan=directing_plan,
            temporal_trajectory_plan=trajectory_plan,
            validation_report=combined_report,
            pass_artifacts=pass_artifacts,
            director_policy=selected_policy,
            director_rationale=policy_rationale,
        )
