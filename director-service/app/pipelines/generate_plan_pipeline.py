"""Full pipeline: scene → abstraction → directing plan → trajectory → validation → save."""

from pathlib import Path

from app.models.scene_summary import SceneSummary
from app.models.cinematic_scene import CinematicScene
from app.models.directing_plan import DirectingPlan
from app.models.trajectory_plan import TrajectoryPlan
from app.models.validation_report import ValidationReport
from app.services.scene_abstraction import SceneAbstractor
from app.services.affordance_analyzer import AffordanceAnalyzer
from app.services.directing_plan_generator import DirectingPlanGenerator
from app.services.plan_validator import PlanValidator
from app.services.trajectory_solver import TrajectorySolver
from app.services.file_manager import FileManager
from app.services.llm_client import create_llm_client
from app.utils.logger import get_logger

logger = get_logger(__name__)


class PipelineResult:
    def __init__(
        self,
        scene: SceneSummary,
        cinematic: CinematicScene,
        directing_plan: DirectingPlan,
        trajectory_plan: TrajectoryPlan,
        validation_report: ValidationReport,
    ):
        self.scene = scene
        self.cinematic = cinematic
        self.directing_plan = directing_plan
        self.trajectory_plan = trajectory_plan
        self.validation_report = validation_report


class GeneratePlanPipeline:
    def __init__(
        self,
        llm_provider: str = "mock",
        llm_model: str | None = None,
        output_dir: str | Path = "outputs",
        scenes_dir: str | Path = "scenes",
    ):
        self._abstractor = SceneAbstractor()
        self._affordance = AffordanceAnalyzer()
        self._llm_client = create_llm_client(llm_provider, model=llm_model)
        self._generator = DirectingPlanGenerator(self._llm_client)
        self._validator = PlanValidator()
        self._solver = TrajectorySolver()
        self._file_manager = FileManager(output_dir, scenes_dir)
        self._scenes_dir = Path(scenes_dir)

    def run(
        self,
        scene_path: str | Path,
        intent: str,
        save: bool = True,
        prefix: str = "",
    ) -> PipelineResult:
        # Step 1: Load scene
        logger.info("Loading scene from %s", scene_path)
        scene = self._file_manager.load_scene(scene_path)
        return self.run_scene(scene, intent, save=save, prefix=prefix)

    def run_scene(
        self,
        scene: SceneSummary,
        intent: str,
        save: bool = True,
        prefix: str = "",
    ) -> PipelineResult:
        logger.info("Running pipeline for scene_id=%s", scene.scene_id)

        # Step 2: Derive cinematic abstraction
        logger.info("Building cinematic scene abstraction...")
        cinematic = self._abstractor.abstract(scene)
        cinematic = self._affordance.analyze(scene, cinematic)

        # Step 3: Generate directing plan
        logger.info("Generating directing plan for intent: %s", intent)
        directing_plan = self._generator.generate(scene, cinematic, intent)

        # Step 4: Validate directing plan
        logger.info("Validating directing plan...")
        dp_report = self._validator.validate_directing_plan(directing_plan, scene)

        # Step 5: Solve trajectory
        logger.info("Solving trajectory...")
        trajectory_plan = self._solver.solve(directing_plan, scene)

        # Step 6: Validate trajectory
        logger.info("Validating trajectory plan...")
        tp_report = self._validator.validate_trajectory_plan(trajectory_plan, directing_plan, scene)

        # Merge reports
        combined_report = ValidationReport(
            is_valid=dp_report.is_valid and tp_report.is_valid,
            errors=dp_report.errors + tp_report.errors,
            warnings=dp_report.warnings + tp_report.warnings,
        )

        # Step 7: Save outputs
        if save:
            self._file_manager.save_directing_plan(directing_plan, prefix)
            self._file_manager.save_trajectory_plan(trajectory_plan, prefix)
            self._file_manager.save_validation_report(combined_report, prefix)
            logger.info("All outputs saved.")

        return PipelineResult(
            scene=scene,
            cinematic=cinematic,
            directing_plan=directing_plan,
            trajectory_plan=trajectory_plan,
            validation_report=combined_report,
        )
