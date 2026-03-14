from pydantic import BaseModel, Field


class SemanticRegion(BaseModel):
    region_id: str
    name: str
    description: str
    center: tuple[float, float, float]
    radius: float
    object_ids: list[str] = Field(default_factory=list)


class CinematicAffordance(BaseModel):
    object_id: str
    affordance_type: str
    description: str
    score: float = 0.5


class VisibilityHint(BaseModel):
    object_id: str
    best_viewing_direction: tuple[float, float, float] | None = None
    min_distance: float = 1.0
    max_distance: float = 5.0
    occlusion_risk: float = 0.0


class FramingHint(BaseModel):
    object_id: str
    recommended_shot_types: list[str] = Field(default_factory=list)
    recommended_angles: list[str] = Field(default_factory=list)
    context_objects: list[str] = Field(default_factory=list)


class ObjectGroup(BaseModel):
    group_id: str
    name: str
    object_ids: list[str]
    relation_type: str


class CinematicScene(BaseModel):
    scene_id: str
    semantic_regions: list[SemanticRegion] = Field(default_factory=list)
    primary_subjects: list[str] = Field(default_factory=list)
    secondary_subjects: list[str] = Field(default_factory=list)
    object_groups: list[ObjectGroup] = Field(default_factory=list)
    spatial_summary: str = ""
    cinematic_affordances: list[CinematicAffordance] = Field(default_factory=list)
    visibility_hints: list[VisibilityHint] = Field(default_factory=list)
    framing_hints: list[FramingHint] = Field(default_factory=list)
