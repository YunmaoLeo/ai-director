import pytest
from fastapi.testclient import TestClient

from app.api import api_app


@pytest.fixture
def client():
    return TestClient(api_app)


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
