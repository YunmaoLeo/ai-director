"""Tests for the temporal plan pipeline end-to-end."""

import copy

import pytest

from app.models.scene_timeline import SemanticSceneEvent
from app.pipelines.temporal_plan_pipeline import TemporalPlanPipeline


class TestTemporalPlanPipeline:
    def setup_method(self):
        self.pipeline = TemporalPlanPipeline(
            llm_provider="mock",
            output_dir="outputs",
            scenes_dir="scenes",
        )

    def test_pipeline_walking_actor(self, walking_actor_timeline):
        result = self.pipeline.run(
            walking_actor_timeline,
            "Follow the actor across the room",
            save=False,
        )

        assert result.temporal_directing_plan is not None
        assert result.temporal_trajectory_plan is not None
        assert result.validation_report is not None
        assert len(result.pass_artifacts) == 4

        # Plan should have shots
        assert len(result.temporal_directing_plan.shots) >= 1
        # Trajectories should match shots
        assert len(result.temporal_trajectory_plan.trajectories) == len(
            result.temporal_directing_plan.shots
        )

    def test_pipeline_two_actors(self, two_actors_timeline):
        result = self.pipeline.run(
            two_actors_timeline,
            "Capture both actors meeting",
            save=False,
        )

        assert result.temporal_directing_plan.scene_id == "temporal_two_actors"
        assert result.validation_report.is_valid
        assert len(result.temporal_directing_plan.beats) >= 1

    def test_pipeline_occlusion_scene(self, occlusion_test_timeline):
        result = self.pipeline.run(
            occlusion_test_timeline,
            "Film the statue reveal after occlusion",
            save=False,
        )

        assert result.temporal_directing_plan is not None
        # Temporal cinematic should have detected reveal opportunities
        assert result.temporal_cinematic is not None

    def test_pipeline_results_valid(self, walking_actor_timeline):
        result = self.pipeline.run(
            walking_actor_timeline,
            "Overview of the scene",
            save=False,
        )

        # All trajectory points should have valid timestamps
        for traj in result.temporal_trajectory_plan.trajectories:
            for pt in traj.timed_points:
                assert pt.timestamp >= walking_actor_timeline.time_span.start - 0.01
                assert pt.timestamp <= walking_actor_timeline.time_span.end + 0.01
                assert 10.0 <= pt.fov <= 120.0

    def test_pipeline_pass_artifacts_complete(self, walking_actor_timeline):
        result = self.pipeline.run(
            walking_actor_timeline,
            "Overview",
            save=False,
        )

        # Should have style, beat, shot, and critique passes
        pass_types = [a.pass_type.value for a in result.pass_artifacts]
        assert "director_intent" in pass_types
        assert "global_beat" in pass_types
        assert "shot_intent" in pass_types
        assert "constraint_critique" in pass_types

    def test_pipeline_with_style_profile(self, walking_actor_timeline):
        result = self.pipeline.run(
            walking_actor_timeline,
            "High-motion tracking of the lead subject",
            save=False,
            director_hint="dynamic_tracking",
            director_notes="Keep context visible around action turns.",
        )
        assert result.temporal_directing_plan is not None
        assert len(result.temporal_directing_plan.shots) >= 1

    def test_pipeline_populates_dual_event_layers(self, walking_actor_timeline):
        timeline = copy.deepcopy(walking_actor_timeline)
        # Simulate older payload that only had `events`.
        timeline.raw_events = []
        timeline.semantic_events = []
        assert len(timeline.events) > 0

        result = self.pipeline.run(
            timeline,
            "Summarize the core temporal moments clearly",
            save=False,
        )
        assert len(result.timeline.raw_events) > 0
        assert len(result.timeline.semantic_events) > 0

    def test_pipeline_reuses_cached_semantic_events(self, walking_actor_timeline, tmp_path, monkeypatch):
        output_dir = tmp_path / "outputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        pipeline = TemporalPlanPipeline(
            llm_provider="mock",
            output_dir=output_dir,
            scenes_dir="scenes",
        )

        timeline = copy.deepcopy(walking_actor_timeline)
        timeline.semantic_events = []
        calls = {"count": 0}

        def _fake_interpret(*_, **__):
            calls["count"] += 1
            return [
                SemanticSceneEvent(
                    semantic_id="sem_cache_0001",
                    label="Cached Test Event",
                    time_start=timeline.time_span.start,
                    time_end=min(timeline.time_span.end, timeline.time_span.start + 0.2),
                    object_ids=[],
                    summary="Cached semantic event",
                    salience=0.7,
                    confidence=0.9,
                    evidence_event_ids=[],
                    tags=["cache"],
                )
            ]

        monkeypatch.setattr(pipeline._event_interpreter, "interpret", _fake_interpret)

        result_first = pipeline.run(
            copy.deepcopy(timeline),
            "First run",
            save=False,
        )
        assert calls["count"] == 1
        assert len(result_first.timeline.semantic_events) == 1

        result_second = pipeline.run(
            copy.deepcopy(timeline),
            "Second run",
            save=False,
        )
        assert calls["count"] == 1
        assert len(result_second.timeline.semantic_events) == 1
        assert result_second.timeline.semantic_events[0].semantic_id == "sem_cache_0001"
