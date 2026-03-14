"""Trajectory solver: converts semantic shots into continuous camera trajectories.

Operates in 2.5D (XZ plane + Y height). Computes camera placement based on
shot type, generates 10-20 sampled points via linear/Bezier/arc interpolation,
applies simple AABB collision pushback, and computes heuristic scoring.
"""

import math

from app.models.scene_summary import SceneSummary, SceneObject
from app.models.directing_plan import DirectingPlan, Shot
from app.models.trajectory_plan import TrajectoryPlan, ShotTrajectory, TrajectoryMetrics
from app.models.enums import ShotType, Movement, PathType
from app.utils.geometry_utils import (
    Vec3, vec3_add, vec3_sub, vec3_scale, vec3_normalize, vec3_distance,
    xz_distance, aabb_contains_xz, aabb_pushback_xz, clamp_to_bounds,
    arc_points, bezier_quadratic, linear_points, centroid,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Shot-type to camera-distance mapping (metres)
_SHOT_DISTANCES: dict[ShotType, tuple[float, float]] = {
    ShotType.establishing: (4.0, 6.0),
    ShotType.wide: (3.0, 5.0),
    ShotType.medium: (1.5, 3.0),
    ShotType.close_up: (0.8, 1.5),
    ShotType.detail: (0.5, 1.0),
    ShotType.reveal: (2.5, 4.5),
}

# Shot-type to camera height
_SHOT_HEIGHTS: dict[ShotType, float] = {
    ShotType.establishing: 2.2,
    ShotType.wide: 1.8,
    ShotType.medium: 1.5,
    ShotType.close_up: 1.3,
    ShotType.detail: 1.0,
    ShotType.reveal: 1.6,
}

_NUM_POINTS = 15


class TrajectorySolver:
    def solve(self, plan: DirectingPlan, scene: SceneSummary) -> TrajectoryPlan:
        objects_by_id = {o.id: o for o in scene.objects}
        trajectories: list[ShotTrajectory] = []

        for shot in plan.shots:
            traj = self._solve_shot(shot, scene, objects_by_id)
            trajectories.append(traj)

        return TrajectoryPlan(
            plan_id=plan.plan_id,
            scene_id=plan.scene_id,
            total_duration=plan.total_duration,
            trajectories=trajectories,
        )

    def _solve_shot(
        self,
        shot: Shot,
        scene: SceneSummary,
        objects_by_id: dict[str, SceneObject],
    ) -> ShotTrajectory:
        # Determine look-at target
        look_at = self._compute_look_at(shot, scene, objects_by_id)
        height = _SHOT_HEIGHTS.get(shot.shot_type, 1.5)
        dist_min, dist_max = _SHOT_DISTANCES.get(shot.shot_type, (2.0, 4.0))
        dist = (dist_min + dist_max) / 2

        # Compute start/end camera positions
        start, end = self._compute_camera_positions(
            shot, look_at, dist, height, scene, objects_by_id
        )

        # Determine path type and generate points
        path_type, points = self._generate_path(shot, start, end, look_at, height)

        # Collision avoidance
        points = self._apply_collision_avoidance(points, scene)

        # Clamp to bounds
        w, l = scene.bounds.width, scene.bounds.length
        points = [clamp_to_bounds(p, w, l) for p in points]

        # Compute FOV based on shot type
        fov = self._compute_fov(shot.shot_type)

        # Compute metrics
        metrics = self._compute_metrics(points, look_at, scene, objects_by_id, shot)

        return ShotTrajectory(
            shot_id=shot.shot_id,
            start_position=points[0],
            end_position=points[-1],
            look_at_position=look_at,
            fov=fov,
            path_type=path_type,
            sampled_points=points,
            duration=shot.duration,
            metrics=metrics,
        )

    def _compute_look_at(
        self,
        shot: Shot,
        scene: SceneSummary,
        objects_by_id: dict[str, SceneObject],
    ) -> Vec3:
        if shot.subject == "room":
            # Center of the room
            return (
                scene.bounds.width / 2,
                1.0,
                scene.bounds.length / 2,
            )
        obj = objects_by_id.get(shot.subject)
        if obj:
            return (obj.position[0], obj.position[1] + obj.size[1] / 2, obj.position[2])
        return (scene.bounds.width / 2, 1.0, scene.bounds.length / 2)

    def _compute_camera_positions(
        self,
        shot: Shot,
        look_at: Vec3,
        dist: float,
        height: float,
        scene: SceneSummary,
        objects_by_id: dict[str, SceneObject],
    ) -> tuple[Vec3, Vec3]:
        room_center = (scene.bounds.width / 2, height, scene.bounds.length / 2)

        if shot.movement == Movement.static:
            pos = self._place_camera(look_at, dist, height, scene)
            return pos, pos

        if shot.movement == Movement.slow_forward:
            start = self._place_camera(look_at, dist * 1.3, height, scene)
            end = self._place_camera(look_at, dist * 0.7, height, scene)
            return start, end

        if shot.movement == Movement.slow_backward:
            start = self._place_camera(look_at, dist * 0.7, height, scene)
            end = self._place_camera(look_at, dist * 1.3, height, scene)
            return start, end

        if shot.movement == Movement.lateral_slide:
            # Move laterally relative to look_at
            dir_to_look = vec3_sub(look_at, room_center)
            dir_to_look = vec3_normalize(dir_to_look)
            # Perpendicular on XZ plane
            perp = (-dir_to_look[2], 0.0, dir_to_look[0])
            offset = vec3_scale(perp, dist * 0.5)
            base = self._place_camera(look_at, dist, height, scene)
            start = vec3_add(base, offset)
            end = vec3_sub(base, offset)
            return (start[0], height, start[2]), (end[0], height, end[2])

        if shot.movement in (Movement.arc, Movement.orbit):
            start = self._place_camera(look_at, dist, height, scene, angle_offset=-0.5)
            end = self._place_camera(look_at, dist, height, scene, angle_offset=0.5)
            return start, end

        if shot.movement == Movement.pan:
            pos = self._place_camera(look_at, dist, height, scene)
            return pos, pos

        # Default
        return self._place_camera(look_at, dist, height, scene), self._place_camera(look_at, dist * 0.8, height, scene)

    def _place_camera(
        self,
        look_at: Vec3,
        dist: float,
        height: float,
        scene: SceneSummary,
        angle_offset: float = 0.0,
    ) -> Vec3:
        """Place camera at distance from look_at, biased toward room center."""
        room_cx = scene.bounds.width / 2
        room_cz = scene.bounds.length / 2

        # Direction from look_at to room center
        dx = room_cx - look_at[0]
        dz = room_cz - look_at[2]
        length = math.sqrt(dx * dx + dz * dz)
        if length < 0.1:
            dx, dz = 0.0, -1.0
        else:
            dx, dz = dx / length, dz / length

        # Apply angle offset (rotation on XZ plane)
        if angle_offset != 0:
            cos_a = math.cos(angle_offset)
            sin_a = math.sin(angle_offset)
            dx, dz = dx * cos_a - dz * sin_a, dx * sin_a + dz * cos_a

        x = look_at[0] + dx * dist
        z = look_at[2] + dz * dist
        return (x, height, z)

    def _generate_path(
        self,
        shot: Shot,
        start: Vec3,
        end: Vec3,
        look_at: Vec3,
        height: float,
    ) -> tuple[PathType, list[Vec3]]:
        if shot.movement in (Movement.arc, Movement.orbit):
            dist = xz_distance(start, look_at)
            start_angle = math.atan2(start[2] - look_at[2], start[0] - look_at[0])
            end_angle = math.atan2(end[2] - look_at[2], end[0] - look_at[0])
            # Ensure arc goes in a consistent direction
            if end_angle - start_angle > math.pi:
                end_angle -= 2 * math.pi
            elif start_angle - end_angle > math.pi:
                end_angle += 2 * math.pi
            points = arc_points(look_at, dist, start_angle, end_angle, _NUM_POINTS, height)
            return PathType.arc, points

        if shot.movement in (Movement.slow_forward, Movement.slow_backward, Movement.lateral_slide):
            # Bezier with control point offset toward look_at for smooth curve
            mid = (
                (start[0] + end[0]) / 2,
                height,
                (start[2] + end[2]) / 2,
            )
            # Offset control point slightly toward look_at for curvature
            ctrl = (
                mid[0] + (look_at[0] - mid[0]) * 0.2,
                height,
                mid[2] + (look_at[2] - mid[2]) * 0.2,
            )
            points = bezier_quadratic(start, ctrl, end, _NUM_POINTS)
            return PathType.bezier, points

        # Static or pan: linear (or single point)
        if shot.movement == Movement.static:
            return PathType.linear, [start] * _NUM_POINTS

        return PathType.linear, linear_points(start, end, _NUM_POINTS)

    def _apply_collision_avoidance(
        self, points: list[Vec3], scene: SceneSummary
    ) -> list[Vec3]:
        result = []
        for pt in points:
            pushed = pt
            for obj in scene.objects:
                if aabb_contains_xz(pushed, obj.position, obj.size, margin=0.3):
                    pushed = aabb_pushback_xz(pushed, obj.position, obj.size, margin=0.3)
            result.append(pushed)
        return result

    def _compute_fov(self, shot_type: ShotType) -> float:
        fov_map: dict[ShotType, float] = {
            ShotType.establishing: 65.0,
            ShotType.wide: 60.0,
            ShotType.medium: 50.0,
            ShotType.close_up: 40.0,
            ShotType.detail: 35.0,
            ShotType.reveal: 55.0,
        }
        return fov_map.get(shot_type, 55.0)

    def _compute_metrics(
        self,
        points: list[Vec3],
        look_at: Vec3,
        scene: SceneSummary,
        objects_by_id: dict[str, SceneObject],
        shot: Shot,
    ) -> TrajectoryMetrics:
        # Visibility: simple heuristic — are objects in keep_objects_visible
        # roughly "in front" of the camera along the path?
        visibility = self._score_visibility(points, look_at, shot, objects_by_id)
        smoothness = self._score_smoothness(points)
        framing = self._score_framing(points, look_at, shot)
        clearance = self._score_clearance(points, scene)

        return TrajectoryMetrics(
            visibility_score=visibility,
            smoothness_score=smoothness,
            framing_score=framing,
            occlusion_risk=max(0.0, 1.0 - clearance),
            clearance_score=clearance,
        )

    def _score_visibility(
        self,
        points: list[Vec3],
        look_at: Vec3,
        shot: Shot,
        objects_by_id: dict[str, SceneObject],
    ) -> float:
        """Heuristic: fraction of path points where subject is roughly visible."""
        if not points:
            return 0.0
        visible_count = 0
        for pt in points:
            dist = xz_distance(pt, look_at)
            if 0.3 < dist < 10.0:
                visible_count += 1
        return visible_count / len(points)

    def _score_smoothness(self, points: list[Vec3]) -> float:
        """Heuristic: penalize sharp direction changes between consecutive segments."""
        if len(points) < 3:
            return 1.0
        smooth_count = 0
        for i in range(1, len(points) - 1):
            d1 = vec3_sub(points[i], points[i - 1])
            d2 = vec3_sub(points[i + 1], points[i])
            len1 = vec3_distance(points[i], points[i - 1])
            len2 = vec3_distance(points[i + 1], points[i])
            if len1 < 1e-6 or len2 < 1e-6:
                smooth_count += 1
                continue
            dot = (d1[0] * d2[0] + d1[1] * d2[1] + d1[2] * d2[2]) / (len1 * len2)
            if dot > 0.5:  # Less than ~60 degree turn
                smooth_count += 1
        return smooth_count / max(1, len(points) - 2)

    def _score_framing(self, points: list[Vec3], look_at: Vec3, shot: Shot) -> float:
        """Heuristic: closer to ideal shot distance = better framing."""
        dist_min, dist_max = _SHOT_DISTANCES.get(shot.shot_type, (2.0, 4.0))
        ideal = (dist_min + dist_max) / 2
        if not points:
            return 0.0
        scores = []
        for pt in points:
            d = xz_distance(pt, look_at)
            deviation = abs(d - ideal) / ideal
            scores.append(max(0.0, 1.0 - deviation))
        return sum(scores) / len(scores)

    def _score_clearance(self, points: list[Vec3], scene: SceneSummary) -> float:
        """Fraction of points that are outside all object AABBs."""
        if not points:
            return 0.0
        clear = 0
        for pt in points:
            collides = False
            for obj in scene.objects:
                if aabb_contains_xz(pt, obj.position, obj.size, margin=0.1):
                    collides = True
                    break
            if not collides:
                clear += 1
        return clear / len(points)
