import pytest

from app.models.directing_plan import DirectingPlan, Shot, ShotConstraints
from app.models.trajectory_plan import TrajectoryPlan, ShotTrajectory, TrajectoryMetrics
from app.models.enums import ShotType, Movement, Pacing, PathType
from app.services.plan_validator import PlanValidator
from app.models.scene_summary import SceneSummary


def _make_valid_plan(scene_id: str = "apartment_living_room") -> DirectingPlan:
    return DirectingPlan(
        plan_id="test_plan",
        scene_id=scene_id,
        intent="test intent",
        summary="A test plan",
        total_duration=7.0,
        shots=[
            Shot(
                shot_id="shot_1",
                goal="Establish the room",
                subject="room",
                shot_type=ShotType.establishing,
                movement=Movement.slow_forward,
                duration=4.0,
                pacing=Pacing.calm,
                constraints=ShotConstraints(keep_objects_visible=["sofa"]),
                rationale="Opening shot",
            ),
            Shot(
                shot_id="shot_2",
                goal="Focus on desk",
                subject="desk",
                shot_type=ShotType.medium,
                movement=Movement.static,
                duration=3.0,
                pacing=Pacing.steady,
                rationale="Desk focus",
            ),
        ],
    )


def test_valid_plan_passes(apartment_scene: SceneSummary):
    validator = PlanValidator()
    plan = _make_valid_plan()
    report = validator.validate_directing_plan(plan, apartment_scene)
    assert report.is_valid
    assert len(report.errors) == 0


def test_wrong_scene_id_fails(apartment_scene: SceneSummary):
    validator = PlanValidator()
    plan = _make_valid_plan(scene_id="wrong_scene")
    report = validator.validate_directing_plan(plan, apartment_scene)
    assert not report.is_valid


def test_unknown_subject_fails(apartment_scene: SceneSummary):
    validator = PlanValidator()
    plan = _make_valid_plan()
    plan.shots[0].subject = "nonexistent_object"
    report = validator.validate_directing_plan(plan, apartment_scene)
    assert not report.is_valid


def test_no_shots_fails(apartment_scene: SceneSummary):
    validator = PlanValidator()
    plan = _make_valid_plan()
    plan.shots = []
    report = validator.validate_directing_plan(plan, apartment_scene)
    assert not report.is_valid


def test_negative_duration_fails(apartment_scene: SceneSummary):
    validator = PlanValidator()
    plan = _make_valid_plan()
    plan.shots[0].duration = -1.0
    report = validator.validate_directing_plan(plan, apartment_scene)
    assert not report.is_valid


def test_duration_mismatch_warning(apartment_scene: SceneSummary):
    validator = PlanValidator()
    plan = _make_valid_plan()
    plan.total_duration = 100.0  # Doesn't match sum of shots
    report = validator.validate_directing_plan(plan, apartment_scene)
    assert any(w.category == "semantic" for w in report.warnings)


def test_trajectory_validation(apartment_scene: SceneSummary):
    validator = PlanValidator()
    plan = _make_valid_plan()
    trajectory = TrajectoryPlan(
        plan_id="test_plan",
        scene_id="apartment_living_room",
        total_duration=7.0,
        trajectories=[
            ShotTrajectory(
                shot_id="shot_1",
                start_position=(3.0, 1.8, 1.0),
                end_position=(3.0, 1.8, 3.0),
                look_at_position=(3.0, 1.0, 4.0),
                fov=60.0,
                path_type=PathType.linear,
                sampled_points=[(3.0, 1.8, float(z)) for z in range(1, 16)],
                duration=4.0,
            ),
            ShotTrajectory(
                shot_id="shot_2",
                start_position=(4.0, 1.5, 2.0),
                end_position=(4.0, 1.5, 2.0),
                look_at_position=(5.0, 0.75, 2.0),
                fov=50.0,
                path_type=PathType.linear,
                sampled_points=[(4.0, 1.5, 2.0)] * 15,
                duration=3.0,
            ),
        ],
    )
    report = validator.validate_trajectory_plan(trajectory, plan, apartment_scene)
    assert report.is_valid
