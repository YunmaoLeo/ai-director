"""Tests for temporal API endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.api import api_app
from app.utils.json_utils import load_json
from pathlib import Path


SCENES_DIR = Path(__file__).resolve().parent.parent / "scenes"


@pytest.fixture
def client():
    return TestClient(api_app)


@pytest.fixture
def walking_actor_data():
    return load_json(SCENES_DIR / "temporal_walking_actor.json")


@pytest.fixture
def two_actors_data():
    return load_json(SCENES_DIR / "temporal_two_actors.json")


class TestTemporalGenerateEndpoint:
    def test_generate_temporal_plan(self, client, walking_actor_data):
        response = client.post("/api/temporal/generate", json={
            "scene_id": "temporal_walking_actor",
            "intent": "Follow the actor",
            "scene_timeline": walking_actor_data,
            "cinematic_style": "motorsport_f1",
        })
        assert response.status_code == 200
        data = response.json()
        assert "temporal_directing_plan" in data
        assert "temporal_trajectory_plan" in data
        assert "validation_report" in data
        assert "pass_artifacts" in data
        assert "scene_timeline" in data
        assert data["temporal"] is True
        assert data["cinematic_style"] == "motorsport_f1"
        assert len(data["pass_artifacts"]) == 4

    def test_auto_style_selection_for_racing_intent(self, client, walking_actor_data):
        response = client.post("/api/temporal/generate", json={
            "scene_id": "temporal_walking_actor",
            "intent": "Track this like an F1 race broadcast with high-speed readability",
            "scene_timeline": walking_actor_data,
            "cinematic_style": "auto",
        })
        assert response.status_code == 200
        data = response.json()
        assert data["cinematic_style"] == "motorsport_f1"
        assert isinstance(data.get("style_rationale"), str)

    def test_generate_with_two_actors(self, client, two_actors_data):
        response = client.post("/api/temporal/generate", json={
            "scene_id": "temporal_two_actors",
            "intent": "Capture the meeting",
            "scene_timeline": two_actors_data,
        })
        assert response.status_code == 200
        data = response.json()
        plan = data["temporal_directing_plan"]
        assert len(plan["shots"]) >= 1

    def test_invalid_timeline_returns_400(self, client):
        response = client.post("/api/temporal/generate", json={
            "scene_id": "test",
            "intent": "test",
            "scene_timeline": {"invalid": True},
        })
        assert response.status_code == 400

    def test_temporal_plan_has_time_windows(self, client, walking_actor_data):
        response = client.post("/api/temporal/generate", json={
            "scene_id": "temporal_walking_actor",
            "intent": "Overview",
            "scene_timeline": walking_actor_data,
        })
        data = response.json()
        for shot in data["temporal_directing_plan"]["shots"]:
            assert "time_start" in shot
            assert "time_end" in shot
            assert shot["time_end"] > shot["time_start"]

    def test_temporal_trajectory_has_timed_points(self, client, walking_actor_data):
        response = client.post("/api/temporal/generate", json={
            "scene_id": "temporal_walking_actor",
            "intent": "Follow actor",
            "scene_timeline": walking_actor_data,
        })
        data = response.json()
        for traj in data["temporal_trajectory_plan"]["trajectories"]:
            assert "timed_points" in traj
            assert len(traj["timed_points"]) >= 2
            for pt in traj["timed_points"]:
                assert "timestamp" in pt
                assert "position" in pt
                assert "look_at" in pt


class TestTemporalRunsEndpoint:
    def test_list_temporal_runs(self, client):
        response = client.get("/api/temporal/runs")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_temporal_run_contains_scene_timeline(self, client, walking_actor_data):
        create = client.post("/api/temporal/generate", json={
            "scene_id": "temporal_walking_actor",
            "intent": "Overview",
            "scene_timeline": walking_actor_data,
        })
        assert create.status_code == 200
        prefix = create.json()["output_prefix"]
        detail = client.get(f"/api/temporal/runs/{prefix}")
        assert detail.status_code == 200
        payload = detail.json()
        assert "scene_timeline" in payload
        assert payload["scene_timeline"]["scene_id"] == "temporal_walking_actor"

    def test_temporal_styles_endpoint(self, client):
        response = client.get("/api/temporal/styles")
        assert response.status_code == 200
        payload = response.json()
        assert "profiles" in payload
        assert "motorsport_f1" in payload["profiles"]


class TestExistingEndpointsUnchanged:
    """Verify that existing static endpoints still work."""

    def test_scenes_endpoint(self, client):
        response = client.get("/api/scenes")
        assert response.status_code == 200
        scenes = response.json()
        assert isinstance(scenes, list)

    def test_runs_endpoint(self, client):
        response = client.get("/api/runs")
        assert response.status_code == 200

    def test_outputs_endpoint(self, client):
        response = client.get("/api/outputs")
        assert response.status_code == 200

    def test_llm_models_endpoint(self, client):
        response = client.get("/api/llm/models")
        assert response.status_code == 200
        data = response.json()
        assert "llm_provider" in data
