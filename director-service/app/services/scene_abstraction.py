"""Derives a CinematicScene from a SceneSummary.

Clusters objects into semantic regions, ranks subjects by importance,
and generates a spatial summary for LLM consumption.
"""

import math

from app.models.scene_summary import SceneSummary, SceneObject
from app.models.cinematic_scene import (
    CinematicScene, SemanticRegion, VisibilityHint, FramingHint, ObjectGroup,
)
from app.utils.geometry_utils import Vec3, xz_distance, centroid


# Clustering radius (metres) for grouping objects into regions
_CLUSTER_RADIUS = 2.5

# Category to region-name mapping
_REGION_LABELS: dict[str, str] = {
    "seating": "seating area",
    "workspace": "work area",
    "entrance": "entrance area",
    "light_source": "window area",
    "view": "window area",
    "storage": "storage area",
    "display": "display area",
}


class SceneAbstractor:
    def abstract(self, scene: SceneSummary) -> CinematicScene:
        regions = self._build_regions(scene)
        primary, secondary = self._rank_subjects(scene)
        groups = self._build_groups(scene)
        visibility = self._build_visibility_hints(scene)
        framing = self._build_framing_hints(scene)
        spatial = self._spatial_summary_text(scene, regions)

        return CinematicScene(
            scene_id=scene.scene_id,
            semantic_regions=regions,
            primary_subjects=[o.id for o in primary],
            secondary_subjects=[o.id for o in secondary],
            object_groups=groups,
            spatial_summary=spatial,
            cinematic_affordances=[],  # filled by AffordanceAnalyzer
            visibility_hints=visibility,
            framing_hints=framing,
        )

    # ---- internal helpers ----

    def _build_regions(self, scene: SceneSummary) -> list[SemanticRegion]:
        """Simple greedy clustering: assign objects to regions by XZ proximity."""
        assigned: set[str] = set()
        regions: list[SemanticRegion] = []
        objects_by_id = {o.id: o for o in scene.objects}

        # Sort by importance descending so important objects seed regions first
        sorted_objs = sorted(scene.objects, key=lambda o: -o.importance)

        for seed in sorted_objs:
            if seed.id in assigned:
                continue
            members = [seed]
            assigned.add(seed.id)
            for other in sorted_objs:
                if other.id in assigned:
                    continue
                if xz_distance(seed.position, other.position) <= _CLUSTER_RADIUS:
                    members.append(other)
                    assigned.add(other.id)

            region_name = self._name_region(members)
            positions = [m.position for m in members]
            center = centroid(positions)
            radius = max(xz_distance(center, p) for p in positions) + 0.5 if len(positions) > 1 else 1.0

            regions.append(SemanticRegion(
                region_id=f"region_{len(regions)}",
                name=region_name,
                description=f"Region containing {', '.join(m.name for m in members)}",
                center=center,
                radius=radius,
                object_ids=[m.id for m in members],
            ))

        return regions

    def _name_region(self, objects: list[SceneObject]) -> str:
        for obj in objects:
            for tag in obj.tags:
                if tag in _REGION_LABELS:
                    return _REGION_LABELS[tag]
        # Fallback: use the most important object's category
        return f"{objects[0].category} area"

    def _rank_subjects(self, scene: SceneSummary) -> tuple[list[SceneObject], list[SceneObject]]:
        sorted_objs = sorted(scene.objects, key=lambda o: -o.importance)
        threshold = 0.6
        primary = [o for o in sorted_objs if o.importance >= threshold]
        secondary = [o for o in sorted_objs if o.importance < threshold]
        if not primary and sorted_objs:
            primary = [sorted_objs[0]]
            secondary = sorted_objs[1:]
        return primary, secondary

    def _build_groups(self, scene: SceneSummary) -> list[ObjectGroup]:
        groups: list[ObjectGroup] = []
        for rel in scene.relations:
            groups.append(ObjectGroup(
                group_id=f"group_{len(groups)}",
                name=f"{rel.source} & {rel.target}",
                object_ids=[rel.source, rel.target],
                relation_type=rel.type,
            ))
        return groups

    def _build_visibility_hints(self, scene: SceneSummary) -> list[VisibilityHint]:
        hints = []
        for obj in scene.objects:
            min_d = 1.0
            max_d = 5.0
            if obj.category == "architectural":
                min_d = 2.0
                max_d = 6.0
            elif "detail" in obj.tags:
                min_d = 0.5
                max_d = 2.5
            hints.append(VisibilityHint(
                object_id=obj.id,
                best_viewing_direction=obj.forward,
                min_distance=min_d,
                max_distance=max_d,
            ))
        return hints

    def _build_framing_hints(self, scene: SceneSummary) -> list[FramingHint]:
        hints = []
        for obj in scene.objects:
            shot_types = []
            if obj.importance >= 0.7:
                shot_types.extend(["medium", "close_up"])
            if "anchor" in obj.tags:
                shot_types.append("wide")
            if "detail" in obj.tags:
                shot_types.append("detail")
            if "reveal" in obj.tags:
                shot_types.append("reveal")
            if not shot_types:
                shot_types.append("wide")

            # Context objects: those related via spatial relations
            context = []
            for rel in scene.relations:
                if rel.source == obj.id:
                    context.append(rel.target)
                elif rel.target == obj.id:
                    context.append(rel.source)

            hints.append(FramingHint(
                object_id=obj.id,
                recommended_shot_types=shot_types,
                context_objects=context,
            ))
        return hints

    def _spatial_summary_text(self, scene: SceneSummary, regions: list[SemanticRegion]) -> str:
        lines = [
            f"Scene '{scene.scene_name}' is a {scene.scene_type} space "
            f"({scene.bounds.width}m x {scene.bounds.length}m x {scene.bounds.height}m).",
            f"It contains {len(scene.objects)} objects across {len(regions)} semantic regions.",
        ]
        for region in regions:
            lines.append(f"- {region.name}: {region.description}")
        return "\n".join(lines)
