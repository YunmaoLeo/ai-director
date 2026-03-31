"""Temporal trajectory solver: converts temporal shots into time-parameterized camera trajectories.

For each shot, samples at ~10Hz, interpolates moving subject positions at each timestep,
computes camera position based on movement type, applies collision avoidance against
static + moving objects, and smooths the final trajectory.
"""

import math
from typing import Any

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

_KNOWN_MOVEMENTS = {"static", "slow_forward", "slow_backward", "lateral_slide", "arc", "pan", "orbit"}

_SAMPLE_RATE = 10.0  # Hz

_TRANSITION_HARD_CUTS = {"cut", "hard_cut", "flash_cut"}
_TRANSITION_BLEND_SECONDS = {
    "cut": 0.0,
    "hard_cut": 0.0,
    "flash_cut": 0.0,
    "smooth": 0.45,
    "dissolve": 0.7,
    "match_cut": 0.24,
    "whip": 0.2,
}
_TRANSITION_CONTINUITY_WEIGHT = {
    "smooth": 0.85,
    "dissolve": 0.75,
    "match_cut": 0.55,
    "whip": 0.35,
}


class TemporalTrajectorySolver:
    def solve(
        self,
        plan: TemporalDirectingPlan,
        timeline: SceneTimeline,
    ) -> TemporalTrajectoryPlan:
        """Solve trajectories for all temporal shots."""
        tracks_by_id = {t.object_id: t for t in timeline.object_tracks}
        objects_by_id = {o.id: o for o in timeline.objects_static}
        shots_by_id = {s.shot_id: s for s in plan.shots}

        trajectories: list[TemporalShotTrajectory] = []
        for shot in plan.shots:
            traj = self._solve_temporal_shot(
                shot, timeline, tracks_by_id, objects_by_id
            )
            trajectories.append(traj)

        # Enforce shot continuity across boundaries according to transition type.
        self._enforce_shot_continuity(trajectories, shots_by_id)

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
        base_fov = self._resolve_base_fov(shot)
        height = self._resolve_camera_height(shot, timeline)
        dist = self._resolve_camera_distance(shot, timeline)
        event_context = self._derive_shot_event_context(shot, timeline)

        # Generate raw camera positions at each timestep
        raw_points: list[Vec3] = []
        look_ats: list[Vec3] = []
        timestamps: list[float] = []
        fovs: list[float] = []

        for i in range(num_samples):
            t_frac = i / max(1, num_samples - 1)
            motion_t = self._shape_motion_progress(t_frac, shot.movement, shot.pacing)
            timestamp = shot.time_start + t_frac * duration
            timestamps.append(timestamp)

            # Get subject position at this time
            subject_pos = self._get_subject_position_at_time(
                shot.subject, timestamp, timeline, tracks_by_id, objects_by_id
            )
            look_at = self._resolve_look_at(shot, subject_pos)
            look_at, dist_scale = self._apply_event_aware_framing(
                timestamp=timestamp,
                base_look_at=look_at,
                shot=shot,
                timeline=timeline,
                tracks_by_id=tracks_by_id,
                objects_by_id=objects_by_id,
                event_context=event_context,
            )
            look_ats.append(look_at)

            # Compute camera position
            cam_pos = self._compute_camera_position_at_time(
                shot, look_at, dist * dist_scale, height, motion_t, t_frac, timeline
            )
            raw_points.append(cam_pos)
            fovs.append(self._compute_fov_at_time(shot, base_fov, motion_t, t_frac))

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
                fov=fovs[i],
            ))

        # Compute metrics
        metrics = self._compute_temporal_metrics(
            smoothed_points, look_ats, timeline, objects_by_id, tracks_by_id, timestamps, shot
        )

        # Determine path type
        path_type = PathType.bezier
        solver_movement = self._resolve_solver_movement(shot)
        if solver_movement in ("static", "pan"):
            path_type = PathType.linear
        elif solver_movement in ("arc", "orbit"):
            path_type = PathType.arc

        return TemporalShotTrajectory(
            shot_id=shot.shot_id,
            time_start=shot.time_start,
            time_end=shot.time_end,
            transition_in=shot.transition_in,
            path_type=path_type,
            timed_points=timed_points,
            metrics=metrics,
        )

    def _derive_shot_event_context(self, shot: TemporalShot, timeline: SceneTimeline) -> dict[str, Any] | None:
        """Pick the most relevant semantic event around this shot."""
        semantic_events = timeline.semantic_events or []
        if not semantic_events:
            return None

        best: dict[str, Any] | None = None
        best_score = -1.0
        for event in semantic_events:
            overlaps = not (event.time_end < shot.time_start or event.time_start > shot.time_end)
            if not overlaps:
                continue
            subject_match = 0.0
            if shot.subject == "room":
                subject_match = 0.2
            elif shot.subject in event.object_ids:
                subject_match = 1.0
            elif event.object_ids:
                subject_match = 0.45
            role_bonus = {
                "setup": 0.08,
                "develop": 0.18,
                "peak": 0.32,
                "release": 0.12,
            }.get(event.dramatic_role, 0.1)
            score = event.salience + subject_match + role_bonus
            if score > best_score:
                best_score = score
                best = {
                    "event_time": (event.time_start + event.time_end) * 0.5,
                    "object_ids": list(event.object_ids),
                    "dramatic_role": event.dramatic_role,
                    "camera_implication": event.camera_implication or "",
                    "salience": event.salience,
                }
        return best

    def _apply_event_aware_framing(
        self,
        timestamp: float,
        base_look_at: Vec3,
        shot: TemporalShot,
        timeline: SceneTimeline,
        tracks_by_id: dict[str, ObjectTrack],
        objects_by_id: dict,
        event_context: dict[str, Any] | None,
    ) -> tuple[Vec3, float]:
        """Bias look-at and camera distance near key events for edit-aware readability."""
        if not event_context:
            return base_look_at, 1.0

        event_time = float(event_context.get("event_time", timestamp))
        delta = timestamp - event_time
        # Build-up starts before event and fades after event.
        if delta < -1.2 or delta > 1.0:
            return base_look_at, 1.0

        # Smooth local weighting around event.
        sigma = 0.55
        weight = math.exp(-0.5 * (delta / sigma) ** 2)
        weight *= 0.55 + 0.45 * max(0.0, min(1.0, float(event_context.get("salience", 0.5))))
        if weight < 0.05:
            return base_look_at, 1.0

        event_subject = shot.subject
        event_objects = event_context.get("object_ids") or []
        if shot.subject == "room" and event_objects:
            event_subject = str(event_objects[0])
        elif shot.subject not in event_objects and event_objects:
            event_subject = str(event_objects[0])

        event_target = self._get_subject_position_at_time(
            event_subject,
            timestamp,
            timeline,
            tracks_by_id,
            objects_by_id,
        )
        event_look = (event_target[0], event_target[1] + 0.5, event_target[2])
        blended_look = vec3_lerp(base_look_at, event_look, min(0.92, weight))

        role = str(event_context.get("dramatic_role", "develop"))
        implication = str(event_context.get("camera_implication", "")).lower()
        dist_scale = 1.0
        if role == "peak":
            dist_scale *= 0.84
        elif role == "setup":
            dist_scale *= 1.08
        elif role == "release":
            dist_scale *= 1.03

        if "tight" in implication or "punch" in implication or "close" in implication:
            dist_scale *= 0.9
        if "widen" in implication or "context" in implication or "orient" in implication:
            dist_scale *= 1.08

        return blended_look, max(0.72, min(1.22, dist_scale))

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
        motion_t: float,
        t_frac: float,
        timeline: SceneTimeline,
    ) -> Vec3:
        """Compute camera position using movement-aware non-linear progression."""
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

        movement = self._resolve_solver_movement(shot)
        height_value = height
        if shot.pacing == "dramatic" and movement not in ("static", "pan"):
            height_value += 0.06 * math.sin(t_frac * math.pi * 2.0)

        if self._constraint_bool(shot, "overhead") or self._constraint_bool(shot, "top_down"):
            spin = self._constraint_float(shot, "orbit_arc_degrees", default=150.0)
            radians = math.radians(spin)
            base_angle = math.atan2(dz, dx)
            angle = base_angle - radians / 2 + radians * motion_t
            overhead_dist = max(0.3, self._constraint_float(shot, "overhead_radius", default=dist * 0.35))
            x = look_at[0] + overhead_dist * math.cos(angle)
            z = look_at[2] + overhead_dist * math.sin(angle)
            return (x, height_value, z)

        camera_offset = self._constraint_vec3(shot, "camera_offset")
        if camera_offset is not None:
            return (
                look_at[0] + camera_offset[0],
                look_at[1] + camera_offset[1],
                look_at[2] + camera_offset[2],
            )

        if movement == "static":
            x = look_at[0] + dx * dist
            z = look_at[2] + dz * dist
            return (x, height_value, z)

        if movement == "slow_forward":
            current_dist = dist * (1.35 - 0.65 * motion_t)
            x = look_at[0] + dx * current_dist
            z = look_at[2] + dz * current_dist
            return (x, height_value, z)

        if movement == "slow_backward":
            current_dist = dist * (0.7 + 0.65 * motion_t)
            x = look_at[0] + dx * current_dist
            z = look_at[2] + dz * current_dist
            return (x, height_value, z)

        if movement == "lateral_slide":
            perp_x = -dz
            perp_z = dx
            offset = dist * 0.62 * (1.0 - 2.0 * motion_t)
            curvature = math.sin(math.pi * motion_t) * dist * 0.12
            base_x = look_at[0] + dx * dist
            base_z = look_at[2] + dz * dist
            return (
                base_x + perp_x * offset + dx * curvature,
                height_value,
                base_z + perp_z * offset + dz * curvature,
            )

        if movement in ("arc", "orbit"):
            pacing_scale = {
                "calm": 0.82,
                "steady": 1.0,
                "dramatic": 1.35,
                "deliberate": 0.92,
            }.get(shot.pacing, 1.0)
            angle_range = 1.0 * pacing_scale  # radians
            base_angle = math.atan2(dz, dx)
            angle = base_angle - angle_range / 2 + angle_range * motion_t
            x = look_at[0] + dist * math.cos(angle)
            z = look_at[2] + dist * math.sin(angle)
            return (x, height_value, z)

        if movement == "pan":
            perp_x = -dz
            perp_z = dx
            sweep = math.sin((motion_t - 0.5) * math.pi) * dist * 0.22
            x = look_at[0] + dx * dist
            z = look_at[2] + dz * dist
            return (x + perp_x * sweep, height_value, z + perp_z * sweep)

        # Default: gentle forward
        current_dist = dist * (1.15 - 0.22 * motion_t)
        x = look_at[0] + dx * current_dist
        z = look_at[2] + dz * current_dist
        return (x, height_value, z)

    def _shape_motion_progress(self, t_frac: float, movement: str, pacing: str) -> float:
        t = max(0.0, min(1.0, t_frac))
        if pacing == "calm":
            shaped = t * t * (3.0 - 2.0 * t)  # smoothstep
        elif pacing == "deliberate":
            shaped = t * t * (2.1 - 1.1 * t)
        elif pacing == "dramatic":
            shaped = 0.5 - 0.5 * math.cos(math.pi * t)
            shaped = min(1.0, max(0.0, shaped + 0.04 * math.sin(3.0 * math.pi * t)))
        else:
            shaped = t

        if movement in ("arc", "orbit"):
            shaped = 0.5 - 0.5 * math.cos(math.pi * shaped)
        elif movement == "lateral_slide":
            shaped = min(1.0, max(0.0, shaped + 0.06 * math.sin(2.0 * math.pi * shaped)))
        return shaped

    def _compute_fov_at_time(
        self,
        shot: TemporalShot,
        base_fov: float,
        motion_t: float,
        t_frac: float,
    ) -> float:
        fov = base_fov
        fov += {
            "calm": -1.5,
            "steady": 0.0,
            "dramatic": 1.8,
            "deliberate": -0.6,
        }.get(shot.pacing, 0.0)

        movement = shot.movement
        if movement == "slow_forward":
            fov += (1.0 - motion_t) * 2.0 - motion_t * 2.8
        elif movement == "slow_backward":
            fov += motion_t * 2.4 - (1.0 - motion_t) * 1.0
        elif movement in ("arc", "orbit"):
            fov += 1.2 * math.sin(math.pi * motion_t)
        elif movement in ("lateral_slide", "pan"):
            fov += 0.8 * math.sin(2.0 * math.pi * motion_t)

        fov = self._constraint_float(shot, "fov", default=fov)

        transition = (shot.transition_in or "cut").lower()
        if transition in {"flash_cut", "whip", "hard_cut"}:
            window = 0.1 if transition == "flash_cut" else (0.14 if transition == "whip" else 0.08)
            if t_frac <= window:
                impulse = {"flash_cut": 8.0, "whip": 5.2, "hard_cut": 3.0}[transition]
                fov += (1.0 - (t_frac / max(window, 1e-3))) * impulse
        elif transition in {"smooth", "dissolve", "match_cut"}:
            window = 0.18
            if t_frac <= window:
                impulse = {"smooth": 1.2, "dissolve": 0.8, "match_cut": 1.6}[transition]
                fov += (1.0 - (t_frac / window)) * impulse

        return float(max(28.0, min(95.0, fov)))

    def _resolve_base_fov(self, shot: TemporalShot) -> float:
        default = _FOV_MAP.get(shot.shot_type, 55.0)
        if self._constraint_bool(shot, "overhead") or self._constraint_bool(shot, "top_down"):
            default = max(default, 68.0)
        return self._constraint_float(shot, "fov", default=default)

    def _resolve_camera_height(self, shot: TemporalShot, timeline: SceneTimeline) -> float:
        default = _SHOT_HEIGHTS.get(shot.shot_type, 1.5)
        keywords = " ".join([
            shot.shot_type or "",
            shot.movement or "",
            shot.goal or "",
            shot.rationale or "",
            str(self._constraint_value(shot, "vantage") or ""),
            str(self._constraint_value(shot, "camera_style") or ""),
        ]).lower()
        if any(token in keywords for token in ("helicopter", "drone", "aerial", "bird", "overhead", "top down", "top-down", "high angle")):
            default = max(default, min(12.0, max(timeline.bounds.height * 0.85, 6.0)))
        if str(shot.constraints.get("height_bias", "")).lower() in {"high", "very_high", "aerial"}:
            default = max(default, min(12.0, max(timeline.bounds.height * 0.8, 5.0)))
        return self._constraint_float(shot, "camera_height", default=default)

    def _resolve_camera_distance(self, shot: TemporalShot, timeline: SceneTimeline) -> float:
        dist_min, dist_max = _SHOT_DISTANCES.get(shot.shot_type, (2.0, 4.0))
        default = (dist_min + dist_max) / 2
        vantage = str(self._constraint_value(shot, "vantage") or "").lower()
        if self._constraint_bool(shot, "overhead") or self._constraint_bool(shot, "top_down") or vantage in {"overhead", "aerial", "top_down"}:
            default *= 0.5
        distance = self._constraint_float(shot, "camera_distance", default=default)
        distance_scale = self._constraint_float(shot, "distance_scale", default=1.0)
        return max(0.25, distance * distance_scale)

    def _resolve_look_at(self, shot: TemporalShot, subject_pos: Vec3) -> Vec3:
        base = (subject_pos[0], subject_pos[1] + 0.5, subject_pos[2])
        look_offset = self._constraint_vec3(shot, "look_at_offset")
        if look_offset is None:
            look_offset = self._constraint_vec3(shot, "look_offset")
        if look_offset is None:
            return base
        return (
            base[0] + look_offset[0],
            base[1] + look_offset[1],
            base[2] + look_offset[2],
        )

    def _resolve_solver_movement(self, shot: TemporalShot) -> str:
        movement = (shot.movement or "").strip().lower()
        if movement in _KNOWN_MOVEMENTS:
            return movement
        dsl = str(self._constraint_value(shot, "dsl") or "").strip().lower()
        dsl_map = {
            "aerial_follow": "slow_forward",
            "top_lock": "orbit",
            "helicopter_orbit": "orbit",
            "parallel_strafe": "lateral_slide",
            "lead_chase": "slow_forward",
            "tail_chase": "slow_forward",
            "geo_reset": "static",
            "apex_orbit": "orbit",
            "impact_push": "slow_forward",
            "retreat_reveal": "slow_backward",
            "sentinel_watch": "static",
            "ground_skimmer": "slow_forward",
            "roofline_shadow": "slow_forward",
            "intercept_arc": "arc",
            "pair_lock": "orbit",
            "finish_drop": "slow_forward",
        }
        if dsl in dsl_map:
            return dsl_map[dsl]
        if any(token in movement for token in ("helicopter", "drone", "aerial", "fly", "glide")):
            if any(token in movement for token in ("orbit", "circle", "arc")):
                return "orbit"
            return "slow_forward"
        if any(token in movement for token in ("track", "follow", "chase", "push")):
            return "slow_forward"
        if any(token in movement for token in ("pull", "retreat")):
            return "slow_backward"
        if any(token in movement for token in ("slide", "strafe")):
            return "lateral_slide"
        if any(token in movement for token in ("arc", "circle", "wrap")):
            return "arc"
        if any(token in movement for token in ("pan", "sweep")):
            return "pan"
        return "slow_forward"

    def _constraint_float(self, shot: TemporalShot, key: str, default: float) -> float:
        value = self._constraint_value(shot, key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return default
        return default

    def _constraint_bool(self, shot: TemporalShot, key: str) -> bool:
        value = self._constraint_value(shot, key)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return False

    def _constraint_vec3(self, shot: TemporalShot, key: str) -> Vec3 | None:
        value = self._constraint_value(shot, key)
        if isinstance(value, (list, tuple)) and len(value) == 3:
            try:
                return (float(value[0]), float(value[1]), float(value[2]))
            except (TypeError, ValueError):
                return None
        return None

    def _constraint_value(self, shot: TemporalShot, key: str) -> Any:
        overrides = self._dsl_overrides(shot)
        if key in shot.constraints:
            return shot.constraints.get(key)
        return overrides.get(key)

    def _dsl_overrides(self, shot: TemporalShot) -> dict[str, Any]:
        dsl = str(shot.constraints.get("dsl", "")).strip().lower()
        if not dsl:
            return {}
        presets: dict[str, dict[str, Any]] = {
            "aerial_follow": {"vantage": "aerial", "height_bias": "aerial", "camera_height": 8.0, "camera_distance": 2.0, "fov": 68.0},
            "top_lock": {"vantage": "overhead", "overhead": True, "top_down": True, "camera_height": 10.0, "overhead_radius": 0.8, "fov": 72.0},
            "helicopter_orbit": {"vantage": "aerial", "overhead": True, "camera_height": 9.0, "overhead_radius": 1.6, "orbit_arc_degrees": 210.0, "fov": 70.0},
            "parallel_strafe": {"vantage": "high_angle", "camera_height": 3.2, "distance_scale": 1.15, "fov": 58.0},
            "lead_chase": {"camera_distance": 2.4, "look_at_offset": [0.0, 0.2, -0.4], "fov": 62.0},
            "tail_chase": {"camera_distance": 3.4, "fov": 60.0},
            "geo_reset": {"vantage": "high_angle", "camera_height": 4.8, "camera_distance": 4.8, "fov": 66.0},
            "apex_orbit": {"orbit_arc_degrees": 240.0, "camera_distance": 2.3, "fov": 54.0},
            "impact_push": {"camera_distance": 1.6, "distance_scale": 0.75, "fov": 46.0},
            "retreat_reveal": {"camera_distance": 5.5, "distance_scale": 1.4, "fov": 68.0},
            "sentinel_watch": {"vantage": "high_angle", "camera_height": 7.5, "camera_distance": 3.0, "fov": 62.0},
            "ground_skimmer": {"camera_height": 0.5, "camera_distance": 2.2, "fov": 78.0},
            "roofline_shadow": {"vantage": "high_angle", "camera_height": 6.2, "camera_offset": [1.8, 5.2, -1.8], "fov": 62.0},
            "intercept_arc": {"camera_distance": 2.8, "orbit_arc_degrees": 140.0, "fov": 58.0},
            "pair_lock": {"vantage": "high_angle", "camera_height": 5.2, "camera_distance": 3.6, "fov": 64.0},
            "finish_drop": {"vantage": "high_angle", "height_bias": "high", "camera_height": 6.8, "camera_distance": 2.6, "fov": 60.0},
        }
        return presets.get(dsl, {})

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
        self,
        trajectories: list[TemporalShotTrajectory],
        shots_by_id: dict[str, TemporalShot],
    ) -> None:
        """Apply transition-aware continuity at shot boundaries."""
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

            transition = "cut"
            if curr.shot_id in shots_by_id:
                transition = (shots_by_id[curr.shot_id].transition_in or "cut").lower()

            if transition in _TRANSITION_HARD_CUTS:
                continue

            blend_seconds = _TRANSITION_BLEND_SECONDS.get(transition, 0.0)
            if blend_seconds <= 0.0:
                continue

            prev_end = prev.timed_points[-1].position
            curr_start = curr.timed_points[0].position
            delta = vec3_distance(prev_end, curr_start)
            if delta <= 1e-3:
                continue

            sample_dt = 1.0 / _SAMPLE_RATE
            if len(curr.timed_points) >= 2:
                sample_dt = max(1e-3, curr.timed_points[1].timestamp - curr.timed_points[0].timestamp)
            blend_count = min(
                len(curr.timed_points),
                max(2, int(blend_seconds / max(sample_dt, 1e-3))),
            )

            if transition == "whip":
                self._apply_whip_entry(prev_end, curr.timed_points, blend_count)
                continue

            continuity_weight = _TRANSITION_CONTINUITY_WEIGHT.get(transition, 0.5)
            self._apply_blended_entry(prev_end, curr.timed_points, blend_count, continuity_weight)

    def _apply_blended_entry(
        self,
        prev_end: Vec3,
        points: list[TimedTrajectoryPoint],
        blend_count: int,
        continuity_weight: float,
    ) -> None:
        for j in range(blend_count):
            t = j / max(1, blend_count - 1)
            eased = t * t * (3.0 - 2.0 * t)
            old_pos = points[j].position
            mix = min(1.0, max(0.0, eased + (1.0 - continuity_weight) * 0.32))
            blended = vec3_lerp(prev_end, old_pos, mix)
            points[j] = TimedTrajectoryPoint(
                timestamp=points[j].timestamp,
                position=blended,
                look_at=points[j].look_at,
                fov=points[j].fov,
            )

    def _apply_whip_entry(
        self,
        prev_end: Vec3,
        points: list[TimedTrajectoryPoint],
        blend_count: int,
    ) -> None:
        curr_start = points[0].position
        direction = vec3_sub(curr_start, prev_end)
        direction_len = vec3_length(direction)
        if direction_len < 1e-3 and len(points) > 1:
            direction = vec3_sub(points[min(2, len(points) - 1)].position, curr_start)
            direction_len = vec3_length(direction)
        if direction_len < 1e-3:
            return

        direction_n = vec3_scale(direction, 1.0 / direction_len)
        perp = (-direction_n[2], 0.0, direction_n[0])
        sweep = min(1.6, max(0.25, direction_len * 0.35))

        for j in range(blend_count):
            t = j / max(1, blend_count - 1)
            eased = t * t * (3.0 - 2.0 * t)
            old_pos = points[j].position
            bridge = vec3_lerp(prev_end, old_pos, 0.24 + 0.76 * eased)
            side = math.sin((1.0 - t) * math.pi) * sweep
            blended = vec3_add(bridge, vec3_scale(perp, side))
            points[j] = TimedTrajectoryPoint(
                timestamp=points[j].timestamp,
                position=blended,
                look_at=points[j].look_at,
                fov=points[j].fov,
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
