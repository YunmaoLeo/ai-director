import pytest
from pathlib import Path

from app.models.scene_summary import SceneSummary
from app.models.scene_timeline import SceneTimeline
from app.utils.json_utils import load_json


SCENES_DIR = Path(__file__).resolve().parent.parent / "scenes"


@pytest.fixture
def apartment_scene() -> SceneSummary:
    data = load_json(SCENES_DIR / "apartment_living_room.json")
    return SceneSummary.model_validate(data)


@pytest.fixture
def office_scene() -> SceneSummary:
    data = load_json(SCENES_DIR / "office_room.json")
    return SceneSummary.model_validate(data)


@pytest.fixture
def corridor_scene() -> SceneSummary:
    data = load_json(SCENES_DIR / "corridor_scene.json")
    return SceneSummary.model_validate(data)


@pytest.fixture
def walking_actor_timeline() -> SceneTimeline:
    data = load_json(SCENES_DIR / "temporal_walking_actor.json")
    return SceneTimeline.model_validate(data)


@pytest.fixture
def two_actors_timeline() -> SceneTimeline:
    data = load_json(SCENES_DIR / "temporal_two_actors.json")
    return SceneTimeline.model_validate(data)


@pytest.fixture
def occlusion_test_timeline() -> SceneTimeline:
    data = load_json(SCENES_DIR / "temporal_occlusion_test.json")
    return SceneTimeline.model_validate(data)
