"""File manager for saving and loading scenes and pipeline outputs."""

from datetime import datetime, UTC
import hashlib
import json
from pathlib import Path
from re import sub
from typing import Any

from app.models.scene_summary import SceneSummary
from app.models.directing_plan import DirectingPlan
from app.models.trajectory_plan import TrajectoryPlan
from app.models.validation_report import ValidationReport
from app.models.scene_timeline import SceneTimeline
from app.models.scene_timeline import SemanticSceneEvent
from app.models.temporal_directing_plan import TemporalDirectingPlan
from app.models.temporal_trajectory_plan import TemporalTrajectoryPlan
from app.models.planning_pass import PlanningPassArtifact
from app.utils.json_utils import load_json, save_json, pydantic_to_json
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FileManager:
    def __init__(self, output_dir: str | Path = "outputs", scenes_dir: str | Path = "scenes"):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._scenes_dir = Path(scenes_dir)
        self._scenes_dir.mkdir(parents=True, exist_ok=True)

    def load_scene(self, path: str | Path) -> SceneSummary:
        data = load_json(path)
        return SceneSummary.model_validate(data)

    def save_scene_summary(
        self,
        scene: SceneSummary,
        filename_prefix: str = "",
    ) -> Path:
        slug = self._slugify(scene.scene_id or scene.scene_name or "scene")
        filename = f"{filename_prefix}{slug}.json" if filename_prefix else f"{slug}.json"
        path = self._scenes_dir / filename
        save_json(pydantic_to_json(scene), path)
        logger.info("Saved scene summary to %s", path)
        return path

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

    def save_run_metadata(self, prefix: str, metadata: dict[str, Any]) -> Path:
        filename = f"{prefix}run_metadata.json"
        path = self._output_dir / filename
        payload = {
            "prefix": prefix,
            "created_at": datetime.now(UTC).isoformat(),
            **metadata,
        }
        save_json(payload, path)
        logger.info("Saved run metadata to %s", path)
        return path

    def list_runs(self) -> list[dict[str, Any]]:
        """List generated run bundles from run metadata files."""
        runs: list[dict[str, Any]] = []
        for path in self._output_dir.glob("*run_metadata.json"):
            try:
                data = load_json(path)
            except Exception:
                logger.warning("Skipping invalid run metadata file: %s", path)
                continue
            runs.append(data)
        runs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return runs

    def load_run_bundle(self, prefix: str) -> dict[str, Any]:
        """Load a run bundle by prefix."""
        normalized_prefix = self._normalize_prefix(prefix)
        metadata_path = self._output_dir / f"{normalized_prefix}run_metadata.json"
        directing_path = self._output_dir / f"{normalized_prefix}directing_plan.json"
        trajectory_path = self._output_dir / f"{normalized_prefix}trajectory_plan.json"
        validation_path = self._output_dir / f"{normalized_prefix}validation_report.json"

        for required_path in [metadata_path, directing_path, trajectory_path, validation_path]:
            if not required_path.exists():
                raise FileNotFoundError(f"Missing run artifact: {required_path.name}")

        metadata = load_json(metadata_path)
        return {
            "directing_plan": load_json(directing_path),
            "trajectory_plan": load_json(trajectory_path),
            "validation_report": load_json(validation_path),
            "output_prefix": normalized_prefix,
            "debug_scene_id": metadata.get("debug_scene_id"),
            "debug_scene_file": metadata.get("debug_scene_file"),
            "llm_provider": metadata.get("llm_provider"),
            "llm_model": metadata.get("llm_model"),
            "llm_model_requested": metadata.get("llm_model_requested"),
            "source_api": metadata.get("source_api"),
            "saved_at": metadata.get("created_at"),
        }

    # --- Temporal file operations ---

    def save_scene_timeline(self, timeline: SceneTimeline, prefix: str = "") -> Path:
        filename = f"{prefix}scene_timeline.json" if prefix else "scene_timeline.json"
        path = self._output_dir / filename
        save_json(pydantic_to_json(timeline), path)
        logger.info("Saved scene timeline to %s", path)
        return path

    def save_temporal_directing_plan(self, plan: TemporalDirectingPlan, prefix: str = "") -> Path:
        filename = f"{prefix}temporal_directing_plan.json" if prefix else "temporal_directing_plan.json"
        path = self._output_dir / filename
        save_json(pydantic_to_json(plan), path)
        logger.info("Saved temporal directing plan to %s", path)
        return path

    def save_temporal_trajectory_plan(self, plan: TemporalTrajectoryPlan, prefix: str = "") -> Path:
        filename = f"{prefix}temporal_trajectory_plan.json" if prefix else "temporal_trajectory_plan.json"
        path = self._output_dir / filename
        save_json(pydantic_to_json(plan), path)
        logger.info("Saved temporal trajectory plan to %s", path)
        return path

    def save_pass_artifacts(self, artifacts: list[PlanningPassArtifact], prefix: str = "") -> Path:
        filename = f"{prefix}pass_artifacts.json" if prefix else "pass_artifacts.json"
        path = self._output_dir / filename
        save_json([pydantic_to_json(a) for a in artifacts], path)
        logger.info("Saved %d pass artifacts to %s", len(artifacts), path)
        return path

    def save_temporal_run_metadata(self, prefix: str, metadata: dict[str, Any]) -> Path:
        filename = f"{prefix}temporal_run_metadata.json"
        path = self._output_dir / filename
        payload = {
            "prefix": prefix,
            "created_at": datetime.now(UTC).isoformat(),
            "temporal": True,
            **metadata,
        }
        save_json(payload, path)
        logger.info("Saved temporal run metadata to %s", path)
        return path

    # --- Semantic event cache ---

    def load_cached_semantic_events(self, timeline: SceneTimeline) -> list[SemanticSceneEvent] | None:
        """Load cached semantic events for a timeline snapshot, if available."""
        cache_path = self._semantic_cache_path()
        if not cache_path.exists():
            return None
        try:
            payload = load_json(cache_path)
            entries = payload.get("entries", {})
            cache_key = self._semantic_cache_key(timeline)
            raw_events = entries.get(cache_key, {}).get("semantic_events")
            if not isinstance(raw_events, list):
                return None
            parsed: list[SemanticSceneEvent] = []
            for item in raw_events:
                if not isinstance(item, dict):
                    continue
                parsed.append(SemanticSceneEvent.model_validate(item))
            return parsed or None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to read semantic event cache from %s: %s", cache_path, exc)
            return None

    def save_cached_semantic_events(
        self,
        timeline: SceneTimeline,
        semantic_events: list[SemanticSceneEvent],
    ) -> Path | None:
        """Persist semantic events cache for a timeline snapshot."""
        if not semantic_events:
            return None

        cache_path = self._semantic_cache_path()
        payload: dict[str, Any]
        if cache_path.exists():
            try:
                payload = load_json(cache_path)
            except Exception:  # noqa: BLE001
                payload = {}
        else:
            payload = {}

        entries = payload.get("entries")
        if not isinstance(entries, dict):
            entries = {}
            payload["entries"] = entries

        cache_key = self._semantic_cache_key(timeline)
        entries[cache_key] = {
            "scene_id": timeline.scene_id,
            "signature": self._semantic_signature(timeline),
            "updated_at": datetime.now(UTC).isoformat(),
            "semantic_events": [pydantic_to_json(event) for event in semantic_events],
        }

        payload.setdefault("version", 1)
        save_json(payload, cache_path)
        logger.info("Saved semantic event cache to %s", cache_path)
        return cache_path

    def load_temporal_run_bundle(self, prefix: str) -> dict[str, Any]:
        """Load a temporal run bundle by prefix."""
        normalized_prefix = self._normalize_prefix(prefix)
        metadata_path = self._output_dir / f"{normalized_prefix}temporal_run_metadata.json"
        directing_path = self._output_dir / f"{normalized_prefix}temporal_directing_plan.json"
        trajectory_path = self._output_dir / f"{normalized_prefix}temporal_trajectory_plan.json"
        validation_path = self._output_dir / f"{normalized_prefix}validation_report.json"
        artifacts_path = self._output_dir / f"{normalized_prefix}pass_artifacts.json"
        timeline_path = self._output_dir / f"{normalized_prefix}scene_timeline.json"

        for required_path in [metadata_path, directing_path, trajectory_path, validation_path]:
            if not required_path.exists():
                raise FileNotFoundError(f"Missing temporal run artifact: {required_path.name}")

        metadata = load_json(metadata_path)
        result: dict[str, Any] = {
            "temporal_directing_plan": load_json(directing_path),
            "temporal_trajectory_plan": load_json(trajectory_path),
            "validation_report": load_json(validation_path),
            "output_prefix": normalized_prefix,
            "scene_id": metadata.get("scene_id"),
            "intent": metadata.get("intent"),
            "llm_provider": metadata.get("llm_provider"),
            "llm_model": metadata.get("llm_model"),
            "director_hint": metadata.get("director_hint"),
            "director_policy": metadata.get("director_policy"),
            "director_rationale": metadata.get("director_rationale"),
            "director_notes": metadata.get("director_notes"),
            "cinematic_style_requested": metadata.get("cinematic_style_requested"),
            "cinematic_style": metadata.get("cinematic_style"),
            "style_rationale": metadata.get("style_rationale"),
            "style_notes": metadata.get("style_notes"),
            "saved_at": metadata.get("created_at"),
            "temporal": True,
        }
        if artifacts_path.exists():
            result["pass_artifacts"] = load_json(artifacts_path)
        if timeline_path.exists():
            result["scene_timeline"] = load_json(timeline_path)
        return result

    def list_temporal_runs(self) -> list[dict[str, Any]]:
        """List temporal run bundles from temporal run metadata files."""
        runs: list[dict[str, Any]] = []
        for path in self._output_dir.glob("*temporal_run_metadata.json"):
            try:
                data = load_json(path)
            except Exception:
                logger.warning("Skipping invalid temporal run metadata: %s", path)
                continue
            runs.append(data)
        runs.sort(key=lambda item: item.get("created_at", ""), reverse=True)
        return runs

    @staticmethod
    def build_run_prefix(scene_id: str, label: str = "") -> str:
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        parts = [FileManager._slugify(scene_id)]
        if label:
            parts.append(FileManager._slugify(label))
        parts.append(timestamp)
        return "_".join(part for part in parts if part) + "_"

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
        return normalized or "scene"

    @staticmethod
    def _normalize_prefix(prefix: str) -> str:
        normalized = prefix.strip()
        if not normalized:
            raise ValueError("Run prefix is empty.")
        if not normalized.endswith("_"):
            normalized += "_"
        if sub(r"[a-zA-Z0-9_]", "", normalized):
            raise ValueError("Invalid run prefix.")
        return normalized

    def _semantic_cache_path(self) -> Path:
        return self._output_dir / "semantic_event_cache.json"

    def _semantic_cache_key(self, timeline: SceneTimeline) -> str:
        return f"{self._slugify(timeline.scene_id)}:{self._semantic_signature(timeline)}"

    def _semantic_signature(self, timeline: SceneTimeline) -> str:
        raw_events = timeline.raw_events or timeline.events
        payload = {
            "scene_id": timeline.scene_id,
            "scene_type": timeline.scene_type,
            "time_span": pydantic_to_json(timeline.time_span),
            "objects_static": [pydantic_to_json(obj) for obj in timeline.objects_static],
            "raw_events": [pydantic_to_json(event) for event in raw_events],
        }
        blob = json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()
