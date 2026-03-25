"""Tests for temporal plan validator."""

import pytest

from app.services.temporal_plan_validator import TemporalPlanValidator
from app.services.temporal_plan_orchestrator import TemporalPlanOrchestrator
from app.services.temporal_abstraction import TemporalAbstractor
from app.services.temporal_trajectory_solver import TemporalTrajectorySolver
from app.services.llm_client import MockTemporalLLMClient
from app.models.temporal_directing_plan import TemporalDirectingPlan, TemporalShot, Beat
from app.models.scene_timeline import TimeSpan


class TestTemporalPlanValidator:
    def setup_method(self):
        self.validator = TemporalPlanValidator()
        self.llm = MockTemporalLLMClient()
        self.orchestrator = TemporalPlanOrchestrator(self.llm)
        self.abstractor = TemporalAbstractor()
        self.solver = TemporalTrajectorySolver()

    def test_valid_plan(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        plan, _, _, _ = self.orchestrator.orchestrate(walking_actor_timeline, tc, "Overview")
        report = self.validator.validate_temporal_directing_plan(plan, walking_actor_timeline)
        assert report.is_valid

    def test_empty_shots_error(self, walking_actor_timeline):
        plan = TemporalDirectingPlan(
            plan_id="test",
            scene_id=walking_actor_timeline.scene_id,
            intent="test",
            shots=[],
        )
        report = self.validator.validate_temporal_directing_plan(plan, walking_actor_timeline)
        assert not report.is_valid
        assert any("at least one shot" in e.message for e in report.errors)

    def test_unknown_subject_error(self, walking_actor_timeline):
        plan = TemporalDirectingPlan(
            plan_id="test",
            scene_id=walking_actor_timeline.scene_id,
            intent="test",
            shots=[TemporalShot(
                shot_id="s1",
                time_start=0,
                time_end=5,
                goal="test",
                subject="nonexistent_object",
                shot_type="wide",
                movement="static",
            )],
        )
        report = self.validator.validate_temporal_directing_plan(plan, walking_actor_timeline)
        assert not report.is_valid
        assert any("unknown subject" in e.message for e in report.errors)

    def test_negative_duration_error(self, walking_actor_timeline):
        plan = TemporalDirectingPlan(
            plan_id="test",
            scene_id=walking_actor_timeline.scene_id,
            intent="test",
            shots=[TemporalShot(
                shot_id="s1",
                time_start=5.0,
                time_end=3.0,
                goal="test",
                subject="room",
                shot_type="wide",
                movement="static",
            )],
        )
        report = self.validator.validate_temporal_directing_plan(plan, walking_actor_timeline)
        assert not report.is_valid
        assert any("non-positive" in e.message for e in report.errors)

    def test_duplicate_shot_ids(self, walking_actor_timeline):
        plan = TemporalDirectingPlan(
            plan_id="test",
            scene_id=walking_actor_timeline.scene_id,
            intent="test",
            shots=[
                TemporalShot(shot_id="s1", time_start=0, time_end=5, goal="a", subject="room", shot_type="wide", movement="static"),
                TemporalShot(shot_id="s1", time_start=5, time_end=10, goal="b", subject="room", shot_type="medium", movement="static"),
            ],
        )
        report = self.validator.validate_temporal_directing_plan(plan, walking_actor_timeline)
        assert not report.is_valid
        assert any("Duplicate" in e.message for e in report.errors)

    def test_trajectory_validation(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        plan, _, _, _ = self.orchestrator.orchestrate(walking_actor_timeline, tc, "Overview")
        trajectory = self.solver.solve(plan, walking_actor_timeline)
        report = self.validator.validate_temporal_trajectory_plan(
            trajectory, plan, walking_actor_timeline
        )
        assert report.is_valid

    def test_beat_shot_alignment_warning(self, walking_actor_timeline):
        plan = TemporalDirectingPlan(
            plan_id="test",
            scene_id=walking_actor_timeline.scene_id,
            intent="test",
            beats=[Beat(beat_id="b1", time_start=0, time_end=10, goal="test")],
            shots=[TemporalShot(
                shot_id="s1",
                time_start=0,
                time_end=10,
                goal="test",
                subject="room",
                shot_type="wide",
                movement="static",
                beat_id="nonexistent_beat",
            )],
        )
        report = self.validator.validate_temporal_directing_plan(plan, walking_actor_timeline)
        assert any("unknown beat" in w.message for w in report.warnings)
