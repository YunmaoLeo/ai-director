from app.models.directing_plan import DirectingPlan, Shot, ShotConstraints
from app.models.enums import ShotType, Movement, Pacing
from app.services.trajectory_solver import TrajectorySolver
from app.models.scene_summary import SceneSummary


def _make_plan(scene_id: str = "apartment_living_room") -> DirectingPlan:
    return DirectingPlan(
        plan_id="test_plan",
        scene_id=scene_id,
        intent="test",
        summary="test",
        total_duration=10.5,
        shots=[
            Shot(
                shot_id="shot_1",
                goal="Establish",
                subject="room",
                shot_type=ShotType.establishing,
                movement=Movement.slow_forward,
                duration=4.0,
                pacing=Pacing.calm,
            ),
            Shot(
                shot_id="shot_2",
                goal="Pan",
                subject="room",
                shot_type=ShotType.wide,
                movement=Movement.lateral_slide,
                duration=3.5,
                pacing=Pacing.steady,
            ),
            Shot(
                shot_id="shot_3",
                goal="Focus on sofa",
                subject="sofa",
                shot_type=ShotType.medium,
                movement=Movement.slow_forward,
                duration=3.0,
                pacing=Pacing.steady,
            ),
        ],
    )


def test_solver_returns_trajectories(apartment_scene: SceneSummary):
    solver = TrajectorySolver()
    plan = _make_plan()
    result = solver.solve(plan, apartment_scene)
    assert len(result.trajectories) == 3


def test_trajectories_have_sampled_points(apartment_scene: SceneSummary):
    solver = TrajectorySolver()
    plan = _make_plan()
    result = solver.solve(plan, apartment_scene)
    for traj in result.trajectories:
        assert len(traj.sampled_points) >= 10


def test_trajectories_have_valid_duration(apartment_scene: SceneSummary):
    solver = TrajectorySolver()
    plan = _make_plan()
    result = solver.solve(plan, apartment_scene)
    for traj in result.trajectories:
        assert traj.duration > 0


def test_trajectories_have_metrics(apartment_scene: SceneSummary):
    solver = TrajectorySolver()
    plan = _make_plan()
    result = solver.solve(plan, apartment_scene)
    for traj in result.trajectories:
        assert 0.0 <= traj.metrics.visibility_score <= 1.0
        assert 0.0 <= traj.metrics.smoothness_score <= 1.0
        assert 0.0 <= traj.metrics.clearance_score <= 1.0


def test_arc_movement(apartment_scene: SceneSummary):
    solver = TrajectorySolver()
    plan = DirectingPlan(
        plan_id="arc_test",
        scene_id="apartment_living_room",
        intent="orbit",
        summary="orbit test",
        total_duration=5.0,
        shots=[
            Shot(
                shot_id="shot_arc",
                goal="Orbit room",
                subject="room",
                shot_type=ShotType.wide,
                movement=Movement.arc,
                duration=5.0,
                pacing=Pacing.calm,
            ),
        ],
    )
    result = solver.solve(plan, apartment_scene)
    assert result.trajectories[0].path_type.value == "arc"


def test_static_movement(apartment_scene: SceneSummary):
    solver = TrajectorySolver()
    plan = DirectingPlan(
        plan_id="static_test",
        scene_id="apartment_living_room",
        intent="static",
        summary="static test",
        total_duration=3.0,
        shots=[
            Shot(
                shot_id="shot_static",
                goal="Static on desk",
                subject="desk",
                shot_type=ShotType.medium,
                movement=Movement.static,
                duration=3.0,
                pacing=Pacing.steady,
            ),
        ],
    )
    result = solver.solve(plan, apartment_scene)
    traj = result.trajectories[0]
    # All points should be the same for static
    for pt in traj.sampled_points:
        assert abs(pt[0] - traj.sampled_points[0][0]) < 0.01
        assert abs(pt[2] - traj.sampled_points[0][2]) < 0.01


def test_solver_works_all_scenes(apartment_scene, office_scene, corridor_scene):
    solver = TrajectorySolver()
    for scene in [apartment_scene, office_scene, corridor_scene]:
        plan = DirectingPlan(
            plan_id="multi_test",
            scene_id=scene.scene_id,
            intent="overview",
            summary="test",
            total_duration=4.0,
            shots=[
                Shot(
                    shot_id="shot_1",
                    goal="Overview",
                    subject="room",
                    shot_type=ShotType.establishing,
                    movement=Movement.slow_forward,
                    duration=4.0,
                    pacing=Pacing.calm,
                ),
            ],
        )
        result = solver.solve(plan, scene)
        assert len(result.trajectories) == 1
        assert len(result.trajectories[0].sampled_points) >= 10
