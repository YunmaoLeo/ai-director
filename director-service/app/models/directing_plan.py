from pydantic import BaseModel, Field

from app.models.enums import ShotType, Movement, Pacing


class ShotConstraints(BaseModel):
    keep_objects_visible: list[str] = Field(default_factory=list)
    avoid_high_angle: bool = False
    avoid_occlusion: bool = True
    preserve_context: bool = False
    end_on_subject: bool = False
    maintain_room_readability: bool = False


class Shot(BaseModel):
    shot_id: str
    goal: str
    subject: str
    shot_type: ShotType
    movement: Movement
    duration: float
    pacing: Pacing = Pacing.steady
    constraints: ShotConstraints = Field(default_factory=ShotConstraints)
    rationale: str = ""


class DirectingPlan(BaseModel):
    plan_id: str
    scene_id: str
    intent: str
    summary: str
    total_duration: float
    shots: list[Shot]
