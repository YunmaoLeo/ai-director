"""Tests for temporal multi-pass plan orchestrator."""

import pytest

from app.services.temporal_plan_orchestrator import TemporalPlanOrchestrator
from app.services.temporal_abstraction import TemporalAbstractor
from app.services.llm_client import MockTemporalLLMClient
from app.models.temporal_enums import PlanningPassType


class TestTemporalPlanOrchestrator:
    def setup_method(self):
        self.llm = MockTemporalLLMClient()
        self.orchestrator = TemporalPlanOrchestrator(self.llm)
        self.abstractor = TemporalAbstractor()

    def test_orchestrate_walking_actor(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        plan, artifacts, _, _ = self.orchestrator.orchestrate(
            walking_actor_timeline, tc, "Follow the actor"
        )

        assert plan.scene_id == "temporal_walking_actor"
        assert len(plan.beats) >= 1
        assert len(plan.shots) >= 1
        assert plan.time_span is not None

        # Should include style + 3 planning pass artifacts
        assert len(artifacts) == 4
        assert artifacts[0].pass_type == PlanningPassType.director_intent
        assert artifacts[1].pass_type == PlanningPassType.global_beat
        assert artifacts[2].pass_type == PlanningPassType.shot_intent

    def test_orchestrate_two_actors(self, two_actors_timeline):
        tc = self.abstractor.abstract(two_actors_timeline)
        plan, artifacts, _, _ = self.orchestrator.orchestrate(
            two_actors_timeline, tc, "Capture the meeting"
        )

        assert len(plan.shots) >= 1
        for shot in plan.shots:
            assert shot.time_start < shot.time_end
            assert shot.shot_type in {
                "establishing", "wide", "medium", "close_up", "detail", "reveal"
            }

    def test_artifacts_structure(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        _, artifacts, _, _ = self.orchestrator.orchestrate(
            walking_actor_timeline, tc, "Overview"
        )

        for artifact in artifacts:
            assert artifact.pass_type in {
                PlanningPassType.director_intent,
                PlanningPassType.global_beat,
                PlanningPassType.shot_intent,
                PlanningPassType.constraint_critique,
            }
            assert artifact.duration_ms >= 0

    def test_beat_coverage(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        plan, _, _, _ = self.orchestrator.orchestrate(
            walking_actor_timeline, tc, "Overview"
        )

        # Beats should cover the full timeline
        if plan.beats:
            first_beat_start = min(b.time_start for b in plan.beats)
            last_beat_end = max(b.time_end for b in plan.beats)
            assert first_beat_start <= walking_actor_timeline.time_span.start + 0.1
            assert last_beat_end >= walking_actor_timeline.time_span.end - 0.1

    def test_shot_time_windows_valid(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        plan, _, _, _ = self.orchestrator.orchestrate(
            walking_actor_timeline, tc, "Overview"
        )

        for shot in plan.shots:
            duration = shot.time_end - shot.time_start
            assert duration > 0, f"Shot {shot.shot_id} has non-positive duration"

    def test_orchestrate_with_dynamic_tracking_policy(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        plan, artifacts, _, _ = self.orchestrator.orchestrate(
            walking_actor_timeline,
            tc,
            "Track the lead subject with aggressive motion continuity",
            style_profile="dynamic_tracking",
            style_brief="Prefer anticipatory framing before fast turns.",
        )
        assert len(plan.shots) >= 1
        assert any("style=dynamic_tracking" in a.input_summary for a in artifacts if a.input_summary)
