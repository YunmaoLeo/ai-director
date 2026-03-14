"""Builds LLM prompts from scene data and user intent."""

from pathlib import Path

from app.models.scene_summary import SceneSummary
from app.models.cinematic_scene import CinematicScene


_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


class PromptBuilder:
    def __init__(self, prompts_dir: Path | None = None):
        self._dir = prompts_dir or _PROMPTS_DIR

    def build(self, scene: SceneSummary, cinematic: CinematicScene, intent: str) -> tuple[str, str]:
        """Return (system_prompt, user_prompt)."""
        system = (self._dir / "system_prompt.txt").read_text(encoding="utf-8")
        template = (self._dir / "user_prompt_template.txt").read_text(encoding="utf-8")

        objects_text = self._format_objects(scene)
        regions_text = self._format_regions(cinematic)
        affordances_text = self._format_affordances(cinematic)
        groups_text = self._format_groups(cinematic)

        user_prompt = template.format(
            scene_name=scene.scene_name,
            scene_type=scene.scene_type,
            width=scene.bounds.width,
            length=scene.bounds.length,
            height=scene.bounds.height,
            spatial_summary=cinematic.spatial_summary,
            objects_text=objects_text,
            regions_text=regions_text,
            affordances_text=affordances_text,
            groups_text=groups_text,
            intent=intent,
            scene_id=scene.scene_id,
        )
        return system, user_prompt

    def _format_objects(self, scene: SceneSummary) -> str:
        lines = []
        for o in scene.objects:
            tags = ", ".join(o.tags) if o.tags else "none"
            lines.append(
                f"- {o.id} ({o.name}): category={o.category}, "
                f"pos=({o.position[0]}, {o.position[1]}, {o.position[2]}), "
                f"size=({o.size[0]}, {o.size[1]}, {o.size[2]}), "
                f"importance={o.importance}, tags=[{tags}]"
            )
        return "\n".join(lines) if lines else "No objects."

    def _format_regions(self, cinematic: CinematicScene) -> str:
        lines = []
        for r in cinematic.semantic_regions:
            objs = ", ".join(r.object_ids)
            lines.append(f"- {r.name} (objects: {objs})")
        return "\n".join(lines) if lines else "No regions."

    def _format_affordances(self, cinematic: CinematicScene) -> str:
        lines = []
        for a in cinematic.cinematic_affordances:
            lines.append(f"- {a.object_id}: {a.affordance_type} — {a.description} (score={a.score:.2f})")
        return "\n".join(lines) if lines else "No affordances."

    def _format_groups(self, cinematic: CinematicScene) -> str:
        lines = []
        for g in cinematic.object_groups:
            objs = ", ".join(g.object_ids)
            lines.append(f"- {g.name} ({g.relation_type}): [{objs}]")
        return "\n".join(lines) if lines else "No groups."
