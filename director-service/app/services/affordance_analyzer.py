"""Rule-based cinematic affordance analyzer.

Derives filming opportunities from scene object properties and tags.
"""

from app.models.scene_summary import SceneSummary
from app.models.cinematic_scene import CinematicAffordance, CinematicScene


# Tag-based affordance rules: (tag, affordance_type, description_template, score)
_TAG_RULES: list[tuple[str, str, str, float]] = [
    ("light_source", "reveal", "{name} is a light source suitable for backlit framing or reveal shots", 0.8),
    ("reveal", "reveal", "{name} is suitable for reveal transitions", 0.7),
    ("anchor", "anchor", "{name} serves as a visual anchor for wide composition", 0.8),
    ("detail", "detail", "{name} is suitable for detail or close-up framing", 0.6),
    ("entrance", "transition", "{name} can serve as a transition or entry point for the camera", 0.5),
    ("view", "scenic", "{name} provides a scenic or backlit framing opportunity", 0.6),
    ("functional", "focus", "{name} is a functional object suitable for focused medium shots", 0.6),
    ("art", "detail", "{name} is a decorative element suitable for detail inspection", 0.6),
    ("endpoint", "destination", "{name} serves as a visual endpoint or reveal destination", 0.7),
]

# Category-based affordance rules
_CATEGORY_RULES: list[tuple[str, str, str, float]] = [
    ("furniture", "composition", "{name} provides compositional structure in wide shots", 0.5),
    ("lighting", "atmosphere", "{name} contributes to atmosphere and mood", 0.4),
    ("architectural", "context", "{name} defines the architectural context of the space", 0.5),
    ("equipment", "focus", "{name} is equipment suitable for focused shots", 0.5),
    ("decoration", "detail", "{name} is a decorative element worth close inspection", 0.5),
]


class AffordanceAnalyzer:
    def analyze(self, scene: SceneSummary, cinematic: CinematicScene) -> CinematicScene:
        """Populate cinematic_affordances on the CinematicScene."""
        affordances: list[CinematicAffordance] = []

        for obj in scene.objects:
            matched = False
            for tag, aff_type, desc_tpl, score in _TAG_RULES:
                if tag in obj.tags:
                    affordances.append(CinematicAffordance(
                        object_id=obj.id,
                        affordance_type=aff_type,
                        description=desc_tpl.format(name=obj.name),
                        score=score * obj.importance,
                    ))
                    matched = True

            if not matched:
                for cat, aff_type, desc_tpl, score in _CATEGORY_RULES:
                    if obj.category == cat:
                        affordances.append(CinematicAffordance(
                            object_id=obj.id,
                            affordance_type=aff_type,
                            description=desc_tpl.format(name=obj.name),
                            score=score * obj.importance,
                        ))
                        break

        cinematic.cinematic_affordances = affordances
        return cinematic
