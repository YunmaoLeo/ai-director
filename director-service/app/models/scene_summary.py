from pydantic import BaseModel, Field


class Bounds(BaseModel):
    width: float
    length: float
    height: float


class SceneObject(BaseModel):
    id: str
    name: str
    category: str
    position: tuple[float, float, float]
    size: tuple[float, float, float]
    forward: tuple[float, float, float] | None = None
    importance: float = 0.5
    tags: list[str] = Field(default_factory=list)


class SpatialRelation(BaseModel):
    type: str
    source: str
    target: str


class FreeSpace(BaseModel):
    walkable_regions: list[list[tuple[float, float]]] = Field(default_factory=list)
    blocked_regions: list[list[tuple[float, float]]] = Field(default_factory=list)
    preferred_open_regions: list[list[tuple[float, float]]] = Field(default_factory=list)


class SceneSummary(BaseModel):
    scene_id: str
    scene_name: str
    scene_type: str
    description: str
    bounds: Bounds
    objects: list[SceneObject]
    relations: list[SpatialRelation] = Field(default_factory=list)
    free_space: FreeSpace | None = None
