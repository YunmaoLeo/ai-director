"""File manager for saving and loading scenes and pipeline outputs."""

from pathlib import Path

from app.models.scene_summary import SceneSummary
from app.models.directing_plan import DirectingPlan
from app.models.trajectory_plan import TrajectoryPlan
from app.models.validation_report import ValidationReport
from app.utils.json_utils import load_json, save_json, pydantic_to_json
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FileManager:
    def __init__(self, output_dir: str | Path = "outputs"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def load_scene(self, path: str | Path) -> SceneSummary:
        data = load_json(path)
        return SceneSummary.model_validate(data)

    def save_directing_plan(self, plan: DirectingPlan, prefix: str = "") -> Path:
        filename = f"{prefix}directing_plan.json" if prefix else "directing_plan.json"
        path = self._output_dir / filename
        save_json(pydantic_to_json(plan), path)
        logger.info("Saved directing plan to %s", path)
        return path

    def save_trajectory_plan(self, plan: TrajectoryPlan, prefix: str = "") -> Path:
        filename = f"{prefix}trajectory_plan.json" if prefix else "trajectory_plan.json"
        path = self._output_dir / filename
        save_json(pydantic_to_json(plan), path)
        logger.info("Saved trajectory plan to %s", path)
        return path

    def save_validation_report(self, report: ValidationReport, prefix: str = "") -> Path:
        filename = f"{prefix}validation_report.json" if prefix else "validation_report.json"
        path = self._output_dir / filename
        save_json(pydantic_to_json(report), path)
        logger.info("Saved validation report to %s", path)
        return path

    def list_scenes(self, scenes_dir: str | Path = "scenes") -> list[dict]:
        """List available scene files with metadata."""
        sd = Path(scenes_dir)
        scenes = []
        if sd.exists():
            for f in sorted(sd.glob("*.json")):
                try:
                    data = load_json(f)
                    scenes.append({
                        "filename": f.name,
                        "scene_id": data.get("scene_id", f.stem),
                        "scene_name": data.get("scene_name", f.stem),
                        "scene_type": data.get("scene_type", "unknown"),
                    })
                except Exception:
                    logger.warning("Skipping invalid scene file: %s", f)
        return scenes

    def list_outputs(self) -> list[str]:
        """List output JSON files."""
        return sorted(f.name for f in self._output_dir.glob("*.json"))
