from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import api
from app.api import api_app
from app.services.file_manager import FileManager


@pytest.fixture
def client():
    return TestClient(api_app)


@pytest.fixture
def isolated_runtime_dirs(tmp_path, monkeypatch):
    scenes_dir = tmp_path / "scenes"
    output_dir = tmp_path / "outputs"
    scenes_dir.mkdir()
    output_dir.mkdir()

    source_scenes = Path(__file__).resolve().parent.parent / "scenes"
    for source in source_scenes.glob("*.json"):
        (scenes_dir / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    monkeypatch.setattr(api.settings, "scenes_dir", scenes_dir)
    monkeypatch.setattr(api.settings, "output_dir", output_dir)
    monkeypatch.setattr(api.settings, "llm_provider", "mock")
    monkeypatch.setattr(api, "_file_manager", FileManager(output_dir, scenes_dir))
    return scenes_dir, output_dir


def test_list_scenes(client):
    response = client.get("/api/scenes")
    assert response.status_code == 200
    scenes = response.json()
    assert len(scenes) >= 3
    scene_ids = [s["scene_id"] for s in scenes]
    assert "apartment_living_room" in scene_ids


def test_get_scene(client):
    response = client.get("/api/scenes/apartment_living_room")
    assert response.status_code == 200
    data = response.json()
    assert data["scene_id"] == "apartment_living_room"
    assert len(data["objects"]) == 6


def test_get_scene_not_found(client):
    response = client.get("/api/scenes/nonexistent")
    assert response.status_code == 404


def test_generate_plan(client):
    response = client.post("/api/generate", json={
        "scene_id": "apartment_living_room",
        "intent": "Give me an overview",
    })
    assert response.status_code == 200
    data = response.json()
    assert "directing_plan" in data
    assert "trajectory_plan" in data
    assert "validation_report" in data
    assert len(data["directing_plan"]["shots"]) >= 2


def test_generate_plan_not_found(client):
    response = client.post("/api/generate", json={
        "scene_id": "nonexistent",
        "intent": "test",
    })
    assert response.status_code == 404


def test_list_outputs(client):
    response = client.get("/api/outputs")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_generate_plan_from_unity_saves_scene_and_outputs(client, isolated_runtime_dirs):
    scenes_dir, output_dir = isolated_runtime_dirs

    response = client.post("/api/unity/generate", json={
        "scene_id": "unity_scene",
        "intent": "Create a slow cinematic exploration of the room.",
        "scene_summary": {
            "scene_id": "unity_scene",
            "scene_name": "Unity Scene",
            "scene_type": "interior",
            "description": "Uploaded from Unity.",
            "bounds": {"width": 5.0, "length": 6.0, "height": 3.0},
            "objects": [
                {
                    "id": "desk",
                    "name": "Desk",
                    "category": "furniture",
                    "position": [3.0, 0.75, 2.0],
                    "size": [1.2, 0.8, 0.7],
                    "forward": [0.0, 0.0, 1.0],
                    "importance": 0.8,
                    "tags": ["workspace"],
                }
            ],
            "relations": [],
        },
        "vision_analysis": {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "analysis_text": "The desk is the primary subject.",
        },
    })

    assert response.status_code == 200
    data = response.json()
    assert data["debug_scene_id"]
    assert data["debug_scene_file"]
    assert data["output_prefix"]

    saved_scene = scenes_dir / data["debug_scene_file"]
    assert saved_scene.exists()
    saved_outputs = list(output_dir.glob(f'{data["output_prefix"]}*.json'))
    assert len(saved_outputs) == 3
