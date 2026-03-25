"""Tests for temporal trajectory solver."""

import pytest

from app.services.temporal_trajectory_solver import TemporalTrajectorySolver
from app.services.temporal_plan_orchestrator import TemporalPlanOrchestrator
from app.services.temporal_abstraction import TemporalAbstractor
from app.services.llm_client import MockTemporalLLMClient


class TestTemporalTrajectorySolver:
    def setup_method(self):
        self.solver = TemporalTrajectorySolver()
        self.llm = MockTemporalLLMClient()
        self.orchestrator = TemporalPlanOrchestrator(self.llm)
        self.abstractor = TemporalAbstractor()

    def _make_plan(self, timeline):
        tc = self.abstractor.abstract(timeline)
        plan, _, _, _ = self.orchestrator.orchestrate(timeline, tc, "Overview")
        return plan

    def test_solve_walking_actor(self, walking_actor_timeline):
        plan = self._make_plan(walking_actor_timeline)
        trajectory = self.solver.solve(plan, walking_actor_timeline)

        assert trajectory.scene_id == walking_actor_timeline.scene_id
        assert len(trajectory.trajectories) == len(plan.shots)

        for traj in trajectory.trajectories:
            assert len(traj.timed_points) >= 2
            # Timestamps should be monotonically increasing
            for i in range(1, len(traj.timed_points)):
                assert traj.timed_points[i].timestamp > traj.timed_points[i - 1].timestamp

    def test_solve_two_actors(self, two_actors_timeline):
        plan = self._make_plan(two_actors_timeline)
        trajectory = self.solver.solve(plan, two_actors_timeline)

        for traj in trajectory.trajectories:
            assert len(traj.timed_points) >= 2
            # FOV should be reasonable
            for pt in traj.timed_points:
                assert 10.0 <= pt.fov <= 120.0

    def test_metrics_computed(self, walking_actor_timeline):
        plan = self._make_plan(walking_actor_timeline)
        trajectory = self.solver.solve(plan, walking_actor_timeline)

        for traj in trajectory.trajectories:
            assert 0.0 <= traj.metrics.visibility_score <= 1.0
            assert 0.0 <= traj.metrics.smoothness_score <= 1.0
            assert 0.0 <= traj.metrics.framing_score <= 1.0
            assert 0.0 <= traj.metrics.clearance_score <= 1.0

    def test_points_within_bounds(self, walking_actor_timeline):
        plan = self._make_plan(walking_actor_timeline)
        trajectory = self.solver.solve(plan, walking_actor_timeline)
        w = walking_actor_timeline.bounds.width
        l = walking_actor_timeline.bounds.length

        for traj in trajectory.trajectories:
            for pt in traj.timed_points:
                assert -1 <= pt.position[0] <= w + 1, (
                    f"X out of bounds: {pt.position[0]}"
                )
                assert -1 <= pt.position[2] <= l + 1, (
                    f"Z out of bounds: {pt.position[2]}"
                )

    def test_shot_continuity(self, walking_actor_timeline):
        plan = self._make_plan(walking_actor_timeline)
        trajectory = self.solver.solve(plan, walking_actor_timeline)

        sorted_trajs = sorted(trajectory.trajectories, key=lambda t: t.time_start)
        for i in range(1, len(sorted_trajs)):
            prev = sorted_trajs[i - 1]
            curr = sorted_trajs[i]
            if not prev.timed_points or not curr.timed_points:
                continue
            # If adjacent, position delta should not be enormous
            gap = curr.time_start - prev.time_end
            if gap <= 0.5:
                prev_end = prev.timed_points[-1].position
                curr_start = curr.timed_points[0].position
                dx = abs(prev_end[0] - curr_start[0])
                dz = abs(prev_end[2] - curr_start[2])
                # After continuity enforcement, should be reasonable
                assert dx < 10 and dz < 10
