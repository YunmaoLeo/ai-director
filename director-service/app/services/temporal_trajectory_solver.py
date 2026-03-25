"""Temporal trajectory solver: converts temporal shots into time-parameterized camera trajectories.

For each shot, samples at ~10Hz, interpolates moving subject positions at each timestep,
computes camera position based on movement type, applies collision avoidance against
static + moving objects, and smooths the final trajectory.
"""

import math

from app.models.scene_timeline import SceneTimeline, ObjectTrack
from app.models.temporal_directing_plan import TemporalDirectingPlan, TemporalShot
from app.models.temporal_trajectory_plan import (
    TemporalTrajectoryPlan,
    TemporalShotTrajectory,
    TimedTrajectoryPoint,
)
from app.models.trajectory_plan import TrajectoryMetrics
from app.models.enums import ShotType, Movement, PathType
from app.utils.geometry_utils import (
    Vec3,
    vec3_add,
    vec3_sub,
    vec3_scale,
    vec3_normalize,
    vec3_distance,
    vec3_length,
    vec3_lerp,
    xz_distance,
    aabb_contains_xz,
    aabb_pushback_xz,
    clamp_to_bounds,
    interpolate_track_at_time,
    gaussian_smooth_points,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)

_SHOT_DISTANCES: dict[str, tuple[float, float]] = {
    "establishing": (4.0, 6.0),
    "wide": (3.0, 5.0),
    "medium": (1.5, 3.0),
    "close_up": (0.8, 1.5),
    "detail": (0.5, 1.0),
    "reveal": (2.5, 4.5),
}

_SHOT_HEIGHTS: dict[str, float] = {
    "establishing": 2.2,
    "wide": 1.8,
    "medium": 1.5,
    "close_up": 1.3,
    "detail": 1.0,
    "reveal": 1.6,
}

_FOV_MAP: dict[str, float] = {
    "establishing": 65.0,
    "wide": 60.0,
    "medium": 50.0,
    "close_up": 40.0,
    "detail": 35.0,
    "reveal": 55.0,
}

_SAMPLE_RATE = 10.0  # Hz


class TemporalTrajectorySolver:
    def solve(
        self,
        plan: TemporalDirectingPlan,
        timeline: SceneTimeline,
    ) -> TemporalTrajectoryPlan:
        """Solve trajectories for all temporal shots."""
        tracks_by_id = {t.object_id: t for t in timeline.object_tracks}
        objects_by_id = {o.id: o for o in timeline.objects_static}

        trajectories: list[TemporalShotTrajectory] = []
        for shot in plan.shots:
            traj = self._solve_temporal_shot(
                shot, timeline, tracks_by_id, objects_by_id
            )
            trajectories.append(traj)

        # Enforce shot continuity across boundaries
        self._enforce_shot_continuity(trajectories)

        return TemporalTrajectoryPlan(
            plan_id=plan.plan_id,
            scene_id=plan.scene_id,
            time_span=plan.time_span,
            trajectories=trajectories,
        )

    def _solve_temporal_shot(
        self,
        shot: TemporalShot,
        timeline: SceneTimeline,
        tracks_by_id: dict[str, ObjectTrack],
        objects_by_id: dict,
    ) -> TemporalShotTrajectory:
        """Solve a single temporal shot trajectory."""
        duration = shot.time_end - shot.time_start
        num_samples = max(2, int(duration * _SAMPLE_RATE))
        fov = _FOV_MAP.get(shot.shot_type, 55.0)
        height = _SHOT_HEIGHTS.get(shot.shot_type, 1.5)
        dist_min, dist_max = _SHOT_DISTANCES.get(shot.shot_type, (2.0, 4.0))
        dist = (dist_min + dist_max) / 2

        # Generate raw camera positions at each timestep
        raw_points: list[Vec3] = []
        look_ats: list[Vec3] = []
        timestamps: list[float] = []

        for i in range(num_samples):
            t_frac = i / max(1, num_samples - 1)
            timestamp = shot.time_start + t_frac * duration
            timestamps.append(timestamp)

            # Get subject position at this time
            subject_pos = self._get_subject_position_at_time(
                shot.subject, timestamp, timeline, tracks_by_id, objects_by_id
            )
            look_at = (subject_pos[0], subject_pos[1] + 0.5, subject_pos[2])
            look_ats.append(look_at)

            # Compute camera position
            cam_pos = self._compute_camera_position_at_time(
                shot, look_at, dist, height, t_frac, timeline
            )
            raw_points.append(cam_pos)

        # Apply temporal collision avoidance
        pushed_points = self._apply_temporal_collision_avoidance(
            raw_points, timestamps, timeline, tracks_by_id
        )

        # Clamp to bounds
        w, l = timeline.bounds.width, timeline.bounds.length
        clamped_points = [clamp_to_bounds(p, w, l) for p in pushed_points]

        # Smooth trajectory
        smoothed_points = self._smooth_trajectory(clamped_points)

        # Build timed trajectory points
        timed_points: list[TimedTrajectoryPoint] = []
        for i in range(num_samples):
            timed_points.append(TimedTrajectoryPoint(
                timestamp=timestamps[i],
                position=smoothed_points[i],
                look_at=look_ats[i],
                fov=fov,
            ))

        # Compute metrics
        metrics = self._compute_temporal_metrics(
            smoothed_points, look_ats, timeline, objects_by_id, tracks_by_id, timestamps, shot
        )

        # Determine path type
        path_type = PathType.bezier
        if shot.movement in ("static", "pan"):
            path_type = PathType.linear
        elif shot.movement in ("arc", "orbit"):
            path_type = PathType.arc

        return TemporalShotTrajectory(
            shot_id=shot.shot_id,
            time_start=shot.time_start,
            time_end=shot.time_end,
            path_type=path_type,
            timed_points=timed_points,
            metrics=metrics,
        )

    def _get_subject_position_at_time(
        self,
        subject_id: str,
        timestamp: float,
        timeline: SceneTimeline,
        tracks_by_id: dict[str, ObjectTrack],
        objects_by_id: dict,
    ) -> Vec3:
        """Get subject position at a given time, interpolating from track or static."""
        if subject_id == "room":
            return (
                timeline.bounds.width / 2,
                0.0,
                timeline.bounds.length / 2,
            )

        # Check tracks first
        track = tracks_by_id.get(subject_id)
        if track and track.samples:
            samples_dicts = [s.model_dump() for s in track.samples]
            return interpolate_track_at_time(samples_dicts, timestamp)

        # Fall back to static object
        obj = objects_by_id.get(subject_id)
        if obj:
            return (obj.position[0], obj.position[1], obj.position[2])

        # Default to room center
        return (
            timeline.bounds.width / 2,
            0.0,
            timeline.bounds.length / 2,
        )

    def _compute_camera_position_at_time(
        self,
        shot: TemporalShot,
        look_at: Vec3,
        dist: float,
        height: float,
        t_frac: float,
        timeline: SceneTimeline,
    ) -> Vec3:
        """Compute camera position based on movement type parameterized by time fraction."""
        room_cx = timeline.bounds.width / 2
        room_cz = timeline.bounds.length / 2

        # Direction from look_at to room center
        dx = room_cx - look_at[0]
        dz = room_cz - look_at[2]
        length = math.sqrt(dx * dx + dz * dz)
        if length < 0.1:
            dx, dz = 0.0, -1.0
        else:
            dx, dz = dx / length, dz / length

        movement = shot.movement

        if movement == "static":
            x = look_at[0] + dx * dist
            z = look_at[2] + dz * dist
            return (x, height, z)

        if movement == "slow_forward":
            current_dist = dist * (1.3 - 0.6 * t_frac)
            x = look_at[0] + dx * current_dist
            z = look_at[2] + dz * current_dist
            return (x, height, z)

        if movement == "slow_backward":
            current_dist = dist * (0.7 + 0.6 * t_frac)
            x = look_at[0] + dx * current_dist
            z = look_at[2] + dz * current_dist
            return (x, height, z)

        if movement == "lateral_slide":
            perp_x = -dz
            perp_z = dx
            offset = dist * 0.5 * (1.0 - 2.0 * t_frac)
            base_x = look_at[0] + dx * dist
            base_z = look_at[2] + dz * dist
            return (base_x + perp_x * offset, height, base_z + perp_z * offset)

        if movement in ("arc", "orbit"):
            angle_range = 1.0  # radians
            base_angle = math.atan2(dz, dx)
            angle = base_angle - angle_range / 2 + angle_range * t_frac
            x = look_at[0] + dist * math.cos(angle)
            z = look_at[2] + dist * math.sin(angle)
            return (x, height, z)

        if movement == "pan":
            x = look_at[0] + dx * dist
            z = look_at[2] + dz * dist
            return (x, height, z)

        # Default: gentle forward
        current_dist = dist * (1.1 - 0.2 * t_frac)
        x = look_at[0] + dx * current_dist
        z = look_at[2] + dz * current_dist
        return (x, height, z)

    def _apply_temporal_collision_avoidance(
        self,
        points: list[Vec3],
        timestamps: list[float],
        timeline: SceneTimeline,
        tracks_by_id: dict[str, ObjectTrack],
    ) -> list[Vec3]:
        """AABB pushback at each timestep including moving objects."""
        result: list[Vec3] = []

        for i, (pt, ts) in enumerate(zip(points, timestamps)):
            pushed = pt

            # Push back from static objects
            for obj in timeline.objects_static:
                if aabb_contains_xz(pushed, obj.position, obj.size, margin=0.3):
                    pushed = aabb_pushback_xz(pushed, obj.position, obj.size, margin=0.3)

            # Push back from moving objects at their current position
            for track_id, track in tracks_by_id.items():
                if not track.samples:
                    continue
                samples_dicts = [s.model_dump() for s in track.samples]
                track_pos = interpolate_track_at_time(samples_dicts, ts)
                # Use a default size for tracked objects
                track_size = (0.6, 1.8, 0.6)
                # Check if this track has a corresponding static object for size
                for obj in timeline.objects_static:
                    if obj.id == track_id:
                        track_size = obj.size
                        break
                if aabb_contains_xz(pushed, track_pos, track_size, margin=0.4):
                    pushed = aabb_pushback_xz(pushed, track_pos, track_size, margin=0.4)

            result.append(pushed)

        return result

    def _smooth_trajectory(self, points: list[Vec3]) -> list[Vec3]:
        """Gaussian smoothing to reduce jitter."""
        if len(points) < 3:
            return list(points)
        return gaussian_smooth_points(points, sigma=1.5)

    def _enforce_shot_continuity(
        self, trajectories: list[TemporalShotTrajectory]
    ) -> None:
        """Match position + direction at shot boundaries."""
        if len(trajectories) < 2:
            return

        sorted_trajs = sorted(trajectories, key=lambda t: t.time_start)

        for i in range(1, len(sorted_trajs)):
            prev = sorted_trajs[i - 1]
            curr = sorted_trajs[i]

            if not prev.timed_points or not curr.timed_points:
                continue

            # Check if shots are temporally adjacent (within 0.5s)
            gap = curr.time_start - prev.time_end
            if gap > 0.5:
                continue

            prev_end = prev.timed_points[-1].position
            curr_start = curr.timed_points[0].position
            delta = vec3_distance(prev_end, curr_start)

            # If large discontinuity, blend the first few points of current shot
            if delta > 1.0:
                blend_count = min(5, len(curr.timed_points))
                for j in range(blend_count):
                    blend_t = j / blend_count
                    old_pos = curr.timed_points[j].position
                    blended = vec3_lerp(prev_end, old_pos, blend_t)
                    curr.timed_points[j] = TimedTrajectoryPoint(
                        timestamp=curr.timed_points[j].timestamp,
                        position=blended,
                        look_at=curr.timed_points[j].look_at,
                        fov=curr.timed_points[j].fov,
                    )

    def _compute_temporal_metrics(
        self,
        points: list[Vec3],
        look_ats: list[Vec3],
        timeline: SceneTimeline,
        objects_by_id: dict,
        tracks_by_id: dict[str, ObjectTrack],
        timestamps: list[float],
        shot: TemporalShot,
    ) -> TrajectoryMetrics:
        """Compute metrics including subject tracking score."""
        visibility = self._score_visibility(points, look_ats)
        smoothness = self._score_smoothness(points)
        framing = self._score_framing(points, look_ats, shot.shot_type)
        clearance = self._score_clearance(points, timeline)
        tracking = self._score_subject_tracking(
            points, look_ats, timestamps, shot, timeline, tracks_by_id, objects_by_id
        )

        return TrajectoryMetrics(
            visibility_score=visibility,
            smoothness_score=smoothness,
            framing_score=framing,
            occlusion_risk=max(0.0, 1.0 - clearance),
            clearance_score=min(clearance, tracking),
        )

    def _score_visibility(self, points: list[Vec3], look_ats: list[Vec3]) -> float:
        if not points:
            return 0.0
        visible = 0
        for pt, la in zip(points, look_ats):
            dist = xz_distance(pt, la)
            if 0.3 < dist < 10.0:
                visible += 1
        return visible / len(points)

    def _score_smoothness(self, points: list[Vec3]) -> float:
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
            if dot > 0.5:
                smooth_count += 1
        return smooth_count / max(1, len(points) - 2)

    def _score_framing(self, points: list[Vec3], look_ats: list[Vec3], shot_type: str) -> float:
        dist_min, dist_max = _SHOT_DISTANCES.get(shot_type, (2.0, 4.0))
        ideal = (dist_min + dist_max) / 2
        if not points:
            return 0.0
        scores = []
        for pt, la in zip(points, look_ats):
            d = xz_distance(pt, la)
            deviation = abs(d - ideal) / max(ideal, 0.01)
            scores.append(max(0.0, 1.0 - deviation))
        return sum(scores) / len(scores)

    def _score_clearance(self, points: list[Vec3], timeline: SceneTimeline) -> float:
        if not points:
            return 0.0
        clear = 0
        for pt in points:
            collides = False
            for obj in timeline.objects_static:
                if aabb_contains_xz(pt, obj.position, obj.size, margin=0.1):
                    collides = True
                    break
            if not collides:
                clear += 1
        return clear / len(points)

    def _score_subject_tracking(
        self,
        points: list[Vec3],
        look_ats: list[Vec3],
        timestamps: list[float],
        shot: TemporalShot,
        timeline: SceneTimeline,
        tracks_by_id: dict[str, ObjectTrack],
        objects_by_id: dict,
    ) -> float:
        """Score how well the camera tracks the moving subject over time."""
        if shot.subject == "room" or not points:
            return 1.0

        track = tracks_by_id.get(shot.subject)
        if not track or not track.samples:
            return 1.0

        tracking_scores: list[float] = []
        for pt, la, ts in zip(points, look_ats, timestamps):
            samples_dicts = [s.model_dump() for s in track.samples]
            actual_pos = interpolate_track_at_time(samples_dicts, ts)
            look_dist = xz_distance(la, actual_pos)
            # Score: 1.0 if look_at is exactly on subject, drops off linearly
            score = max(0.0, 1.0 - look_dist / 3.0)
            tracking_scores.append(score)

        return sum(tracking_scores) / len(tracking_scores) if tracking_scores else 1.0
