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
_KNOWN_LENS_PROFILES = {"normal", "wide_angle", "telephoto", "fisheye"}
_DEFAULT_SENSOR_SIZE = (36.0, 24.0)

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
        rig_style = self._resolve_rig_style(shot)
        noise_amplitude, noise_frequency = self._resolve_noise_settings(shot, rig_style)

        # Generate raw camera positions at each timestep
        raw_points: list[Vec3] = []
        look_ats: list[Vec3] = []
        timestamps: list[float] = []
        fovs: list[float] = []
        dutches: list[float] = []
        focus_distances: list[float] = []
        apertures: list[float] = []
        focal_lengths: list[float] = []
        lens_shifts: list[tuple[float, float]] = []
        bloom_intensities: list[float] = []
        bloom_thresholds: list[float] = []
        vignette_intensities: list[float] = []
        post_exposures: list[float] = []
        saturations: list[float] = []
        contrasts: list[float] = []
        chromatic_aberrations: list[float] = []
        film_grain_intensities: list[float] = []
        motion_blur_intensities: list[float] = []

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
            fov = self._compute_fov_at_time(shot, base_fov, motion_t, t_frac)
            fovs.append(fov)
            dutches.append(self._compute_dutch_at_time(shot, motion_t, t_frac))
            focus_distances.append(self._compute_focus_distance_at_time(shot, cam_pos, look_at, motion_t))
            apertures.append(self._compute_aperture_at_time(shot, motion_t))
            focal_lengths.append(self._compute_focal_length_at_time(shot, fov, motion_t))
            lens_shifts.append(self._compute_lens_shift_at_time(shot, motion_t))
            bloom_intensities.append(self._compute_bloom_intensity_at_time(shot, motion_t, t_frac))
            bloom_thresholds.append(self._compute_bloom_threshold_at_time(shot, motion_t))
            vignette_intensities.append(self._compute_vignette_intensity_at_time(shot, motion_t, t_frac))
            post_exposures.append(self._compute_post_exposure_at_time(shot, motion_t, t_frac))
            saturations.append(self._compute_saturation_at_time(shot, motion_t))
            contrasts.append(self._compute_contrast_at_time(shot, motion_t))
            chromatic_aberrations.append(self._compute_chromatic_aberration_at_time(shot, motion_t, t_frac))
            film_grain_intensities.append(self._compute_film_grain_intensity_at_time(shot, motion_t, t_frac))
            motion_blur_intensities.append(self._compute_motion_blur_intensity_at_time(shot, motion_t, t_frac))

        # Apply temporal collision avoidance
        pushed_points = self._apply_temporal_collision_avoidance(
            raw_points, timestamps, timeline, tracks_by_id
        )

        # Clamp to bounds
        w, l = timeline.bounds.width, timeline.bounds.length
        clamped_points = [clamp_to_bounds(p, w, l) for p in pushed_points]

        # Smooth trajectory
        smoothed_points = self._smooth_trajectory(clamped_points)
        styled_points = self._apply_rig_style(smoothed_points, timestamps, shot)
        final_points = [clamp_to_bounds(p, w, l) for p in styled_points]

        # Build timed trajectory points
        timed_points: list[TimedTrajectoryPoint] = []
        for i in range(num_samples):
            timed_points.append(TimedTrajectoryPoint(
                timestamp=timestamps[i],
                position=final_points[i],
                look_at=look_ats[i],
                fov=fovs[i],
                dutch=dutches[i],
                focus_distance=focus_distances[i],
                aperture=apertures[i],
                focal_length=focal_lengths[i],
                lens_shift=lens_shifts[i],
                bloom_intensity=bloom_intensities[i],
                bloom_threshold=bloom_thresholds[i],
                vignette_intensity=vignette_intensities[i],
                post_exposure=post_exposures[i],
                saturation=saturations[i],
                contrast=contrasts[i],
                chromatic_aberration=chromatic_aberrations[i],
                film_grain_intensity=film_grain_intensities[i],
                motion_blur_intensity=motion_blur_intensities[i],
            ))

        # Compute metrics
        metrics = self._compute_temporal_metrics(
            final_points, look_ats, timeline, objects_by_id, tracks_by_id, timestamps, shot
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
            rig_style=rig_style,
            noise_amplitude=noise_amplitude,
            noise_frequency=noise_frequency,
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
        height_value = self._resolve_camera_height_at_time(shot, height, motion_t)
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
        start_fov = self._constraint_optional_float(shot, "fov_start")
        end_fov = self._constraint_optional_float(shot, "fov_end")
        zoom_profile = self._resolve_zoom_profile(shot)

        if start_fov is not None or end_fov is not None:
            start = start_fov if start_fov is not None else base_fov
            end = end_fov if end_fov is not None else base_fov
            zoom_t = self._shape_zoom_progress(motion_t, zoom_profile)
            fov = start + (end - start) * zoom_t
        elif zoom_profile:
            fov = self._compute_zoom_profile_fov(base_fov, zoom_profile, motion_t)
        else:
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

    def _compute_dutch_at_time(
        self,
        shot: TemporalShot,
        motion_t: float,
        t_frac: float,
    ) -> float:
        start_dutch = self._constraint_optional_float(shot, "dutch_start")
        end_dutch = self._constraint_optional_float(shot, "dutch_end")
        static_dutch = self._constraint_optional_float(shot, "dutch")

        if start_dutch is not None or end_dutch is not None:
            start = start_dutch if start_dutch is not None else (static_dutch or 0.0)
            end = end_dutch if end_dutch is not None else (static_dutch or 0.0)
            dutch = start + (end - start) * motion_t
        elif static_dutch is not None:
            dutch = static_dutch
        else:
            keywords = self._shot_language_blob(shot)
            dutch = 0.0
            if "dutch angle" in keywords or "canted angle" in keywords or "tilted frame" in keywords:
                dutch = 12.0
            elif "hero" in keywords and "low angle" in keywords:
                dutch = 4.0
            if (shot.transition_in or "").lower() == "whip":
                dutch += math.sin(t_frac * math.pi) * 3.5

        return float(max(-35.0, min(35.0, dutch)))

    def _resolve_base_fov(self, shot: TemporalShot) -> float:
        default = _FOV_MAP.get(shot.shot_type, 55.0)
        if self._constraint_bool(shot, "overhead") or self._constraint_bool(shot, "top_down"):
            default = max(default, 68.0)
        lens_profile = self._resolve_lens_profile(shot)
        default += {
            "normal": 0.0,
            "wide_angle": 14.0,
            "telephoto": -10.0,
            "fisheye": 28.0,
        }.get(lens_profile, 0.0)
        default = float(max(28.0, min(95.0, default)))
        return self._constraint_float(shot, "fov", default=default)

    def _compute_focus_distance_at_time(
        self,
        shot: TemporalShot,
        camera_pos: Vec3,
        look_at: Vec3,
        motion_t: float,
    ) -> float:
        start_focus = self._constraint_optional_float(shot, "focus_distance_start")
        end_focus = self._constraint_optional_float(shot, "focus_distance_end")
        static_focus = self._constraint_optional_float(shot, "focus_distance")
        if start_focus is not None or end_focus is not None:
            base = max(0.15, vec3_distance(camera_pos, look_at))
            start = start_focus if start_focus is not None else (static_focus if static_focus is not None else base)
            end = end_focus if end_focus is not None else (static_focus if static_focus is not None else base)
            return float(max(0.15, start + (end - start) * motion_t))
        if static_focus is not None:
            return float(max(0.15, static_focus))
        return float(max(0.15, vec3_distance(camera_pos, look_at)))

    def _compute_aperture_at_time(self, shot: TemporalShot, motion_t: float) -> float:
        start_aperture = self._constraint_optional_float(shot, "aperture_start")
        end_aperture = self._constraint_optional_float(shot, "aperture_end")
        static_aperture = self._constraint_optional_float(shot, "aperture")
        base_aperture = self._resolve_base_aperture(shot)
        if start_aperture is not None or end_aperture is not None:
            start = start_aperture if start_aperture is not None else (static_aperture if static_aperture is not None else base_aperture)
            end = end_aperture if end_aperture is not None else (static_aperture if static_aperture is not None else base_aperture)
            aperture = start + (end - start) * motion_t
        elif static_aperture is not None:
            aperture = static_aperture
        else:
            aperture = base_aperture
        return float(max(1.0, min(16.0, aperture)))

    def _compute_focal_length_at_time(self, shot: TemporalShot, fov: float, motion_t: float) -> float:
        start_focal = self._constraint_optional_float(shot, "focal_length_start")
        end_focal = self._constraint_optional_float(shot, "focal_length_end")
        static_focal = self._constraint_optional_float(shot, "focal_length")
        if start_focal is not None or end_focal is not None:
            base = self._focal_length_from_fov(fov)
            start = start_focal if start_focal is not None else (static_focal if static_focal is not None else base)
            end = end_focal if end_focal is not None else (static_focal if static_focal is not None else base)
            focal_length = start + (end - start) * motion_t
        elif static_focal is not None:
            focal_length = static_focal
        else:
            focal_length = self._focal_length_from_fov(fov)
        return float(max(10.0, min(200.0, focal_length)))

    def _compute_lens_shift_at_time(self, shot: TemporalShot, motion_t: float) -> tuple[float, float]:
        start_shift = self._constraint_vec2(shot, "lens_shift_start")
        end_shift = self._constraint_vec2(shot, "lens_shift_end")
        static_shift = self._constraint_vec2(shot, "lens_shift")
        if start_shift is not None or end_shift is not None:
            start = start_shift if start_shift is not None else (static_shift if static_shift is not None else (0.0, 0.0))
            end = end_shift if end_shift is not None else (static_shift if static_shift is not None else (0.0, 0.0))
            return (
                start[0] + (end[0] - start[0]) * motion_t,
                start[1] + (end[1] - start[1]) * motion_t,
            )
        if static_shift is not None:
            return static_shift
        return (0.0, 0.0)

    def _compute_bloom_intensity_at_time(self, shot: TemporalShot, motion_t: float, t_frac: float) -> float:
        transition = (shot.transition_in or "cut").lower()
        default = 0.0
        keywords = self._shot_language_blob(shot)
        if any(token in keywords for token in ("dreamy", "glow", "neon", "halation", "bloom")):
            default = 0.35
        if transition in {"flash_cut", "whip"}:
            default = max(default, 0.45)
        return self._resolve_effect_scalar(
            shot,
            key="bloom_intensity",
            motion_t=motion_t,
            t_frac=t_frac,
            default=default,
            curve="glow",
            min_value=0.0,
            max_value=6.0,
        )

    def _compute_bloom_threshold_at_time(self, shot: TemporalShot, motion_t: float) -> float:
        threshold = self._resolve_effect_scalar_pair(
            shot,
            key="bloom_threshold",
            motion_t=motion_t,
            default=1.0,
            curve="exposure",
        )
        return float(max(0.0, min(4.0, threshold)))

    def _compute_vignette_intensity_at_time(self, shot: TemporalShot, motion_t: float, t_frac: float) -> float:
        default = 0.0
        keywords = self._shot_language_blob(shot)
        transition = (shot.transition_in or "cut").lower()
        if any(token in keywords for token in ("vignette", "surveillance", "claustrophobic", "intimate")):
            default = 0.28
        if transition in {"dissolve", "smooth"}:
            default = max(default, 0.12)
        return self._resolve_effect_scalar(
            shot,
            key="vignette_intensity",
            motion_t=motion_t,
            t_frac=t_frac,
            default=default,
            curve="vignette",
            min_value=0.0,
            max_value=0.65,
        )

    def _compute_post_exposure_at_time(self, shot: TemporalShot, motion_t: float, t_frac: float) -> float:
        default = 0.0
        transition = (shot.transition_in or "cut").lower()
        if transition == "flash_cut":
            default = 0.4
        elif transition == "dissolve":
            default = 0.15
        return self._resolve_effect_scalar(
            shot,
            key="post_exposure",
            motion_t=motion_t,
            t_frac=t_frac,
            default=default,
            curve="exposure",
            min_value=-3.0,
            max_value=3.0,
        )

    def _compute_saturation_at_time(self, shot: TemporalShot, motion_t: float) -> float:
        default = 0.0
        keywords = self._shot_language_blob(shot)
        if any(token in keywords for token in ("bleached", "desaturated", "cold")):
            default = -18.0
        elif any(token in keywords for token in ("vibrant", "hyperreal", "pop", "saturated")):
            default = 18.0
        return self._resolve_effect_scalar_pair(
            shot,
            key="saturation",
            motion_t=motion_t,
            default=default,
            curve="grade",
            min_value=-100.0,
            max_value=100.0,
        )

    def _compute_contrast_at_time(self, shot: TemporalShot, motion_t: float) -> float:
        default = 0.0
        keywords = self._shot_language_blob(shot)
        if any(token in keywords for token in ("noir", "hard contrast", "graphic", "punchy")):
            default = 20.0
        elif any(token in keywords for token in ("soft", "hazy", "washed")):
            default = -12.0
        return self._resolve_effect_scalar_pair(
            shot,
            key="contrast",
            motion_t=motion_t,
            default=default,
            curve="grade",
            min_value=-100.0,
            max_value=100.0,
        )

    def _compute_chromatic_aberration_at_time(self, shot: TemporalShot, motion_t: float, t_frac: float) -> float:
        default = 0.0
        transition = (shot.transition_in or "cut").lower()
        keywords = self._shot_language_blob(shot)
        if any(token in keywords for token in ("chromatic aberration", "fringe", "distorted", "surveillance")):
            default = 0.18
        if transition in {"whip", "flash_cut"}:
            default = max(default, 0.22)
        return self._resolve_effect_scalar(
            shot,
            key="chromatic_aberration",
            motion_t=motion_t,
            t_frac=t_frac,
            default=default,
            curve="impulse",
            min_value=0.0,
            max_value=1.0,
        )

    def _compute_film_grain_intensity_at_time(self, shot: TemporalShot, motion_t: float, t_frac: float) -> float:
        default = 0.0
        keywords = self._shot_language_blob(shot)
        if any(token in keywords for token in ("film grain", "gritty", "documentary", "vintage")):
            default = 0.35
        return self._resolve_effect_scalar(
            shot,
            key="film_grain_intensity",
            motion_t=motion_t,
            t_frac=t_frac,
            default=default,
            curve="texture",
            min_value=0.0,
            max_value=1.0,
        )

    def _compute_motion_blur_intensity_at_time(self, shot: TemporalShot, motion_t: float, t_frac: float) -> float:
        default = 0.0
        movement = self._resolve_solver_movement(shot)
        transition = (shot.transition_in or "cut").lower()
        if movement in {"slow_forward", "lateral_slide", "arc", "orbit"}:
            default = 0.18
        if transition in {"whip", "flash_cut"}:
            default = max(default, 0.35)
        return self._resolve_effect_scalar(
            shot,
            key="motion_blur_intensity",
            motion_t=motion_t,
            t_frac=t_frac,
            default=default,
            curve="impulse",
            min_value=0.0,
            max_value=1.0,
        )

    def _resolve_effect_scalar(
        self,
        shot: TemporalShot,
        key: str,
        motion_t: float,
        t_frac: float,
        default: float,
        curve: str,
        min_value: float,
        max_value: float,
    ) -> float:
        value = self._resolve_effect_scalar_pair(shot, key, motion_t, default, curve, min_value, max_value)
        transition = (shot.transition_in or "cut").lower()
        if transition in {"flash_cut", "whip", "smooth", "dissolve", "match_cut"}:
            value += self._transition_effect_impulse(key, transition, t_frac)
        return float(max(min_value, min(max_value, value)))

    def _resolve_effect_scalar_pair(
        self,
        shot: TemporalShot,
        key: str,
        motion_t: float,
        default: float,
        curve: str,
        min_value: float = -10_000.0,
        max_value: float = 10_000.0,
    ) -> float:
        start_value = self._constraint_optional_float(shot, f"{key}_start")
        end_value = self._constraint_optional_float(shot, f"{key}_end")
        static_value = self._constraint_optional_float(shot, key)
        if start_value is not None or end_value is not None:
            start = start_value if start_value is not None else (static_value if static_value is not None else default)
            end = end_value if end_value is not None else (static_value if static_value is not None else default)
            eased = self._shape_effect_progress(motion_t, curve)
            value = start + (end - start) * eased
        elif static_value is not None:
            value = static_value
        else:
            value = default
        return float(max(min_value, min(max_value, value)))

    def _shape_effect_progress(self, motion_t: float, curve: str) -> float:
        t = max(0.0, min(1.0, motion_t))
        profile = (curve or "").strip().lower()
        if profile == "glow":
            return math.sqrt(t)
        if profile == "vignette":
            return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
        if profile == "exposure":
            return t * t * (3.0 - 2.0 * t)
        if profile == "grade":
            return 0.5 - 0.5 * math.cos(math.pi * t)
        if profile == "texture":
            return (0.5 - 0.5 * math.cos(math.pi * t)) ** 0.85
        if profile == "impulse":
            return math.sqrt(t)
        return t

    def _transition_effect_impulse(self, key: str, transition: str, t_frac: float) -> float:
        if transition == "flash_cut":
            window = 0.12
            strength = 1.0 - min(1.0, t_frac / window)
            return {
                "bloom_intensity": 0.7 * strength,
                "post_exposure": 0.55 * strength,
                "chromatic_aberration": 0.25 * strength,
                "motion_blur_intensity": 0.3 * strength,
            }.get(key, 0.0)
        if transition == "whip":
            window = 0.16
            strength = math.sin(min(1.0, t_frac / window) * math.pi)
            return {
                "chromatic_aberration": 0.18 * strength,
                "motion_blur_intensity": 0.28 * strength,
                "vignette_intensity": 0.08 * strength,
            }.get(key, 0.0)
        if transition == "dissolve":
            window = 0.26
            strength = 1.0 - min(1.0, t_frac / window)
            return {
                "vignette_intensity": 0.05 * strength,
                "bloom_intensity": 0.08 * strength,
            }.get(key, 0.0)
        if transition in {"smooth", "match_cut"}:
            window = 0.18
            strength = 1.0 - min(1.0, t_frac / window)
            return {
                "motion_blur_intensity": 0.08 * strength,
                "post_exposure": 0.05 * strength,
            }.get(key, 0.0)
        return 0.0

    def _resolve_camera_height(self, shot: TemporalShot, timeline: SceneTimeline) -> float:
        default = _SHOT_HEIGHTS.get(shot.shot_type, 1.5)
        keywords = self._shot_language_blob(shot)
        if any(token in keywords for token in ("helicopter", "drone", "aerial", "bird", "overhead", "top down", "top-down", "high angle")):
            default = max(default, min(12.0, max(timeline.bounds.height * 0.85, 6.0)))
        if any(token in keywords for token in ("low angle", "low-angle")):
            default = min(default, 0.8)
        if str(shot.constraints.get("height_bias", "")).lower() in {"high", "very_high", "aerial"}:
            default = max(default, min(12.0, max(timeline.bounds.height * 0.8, 5.0)))
        return self._constraint_float(shot, "camera_height", default=default)

    def _resolve_camera_height_at_time(
        self,
        shot: TemporalShot,
        base_height: float,
        motion_t: float,
    ) -> float:
        start_height = self._constraint_optional_float(shot, "camera_height_start")
        if start_height is None:
            start_height = self._constraint_optional_float(shot, "height_start")
        end_height = self._constraint_optional_float(shot, "camera_height_end")
        if end_height is None:
            end_height = self._constraint_optional_float(shot, "height_end")

        if start_height is None and end_height is None:
            return base_height

        start = start_height if start_height is not None else base_height
        end = end_height if end_height is not None else base_height
        return start + (end - start) * motion_t

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
            keywords = self._shot_language_blob(shot)
            if "low angle" in keywords or "low-angle" in keywords:
                return (subject_pos[0], subject_pos[1] + 1.1, subject_pos[2])
            if "high angle" in keywords or "high-angle" in keywords:
                return (subject_pos[0], subject_pos[1] + 0.25, subject_pos[2])
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
            "crane_rise": "slow_backward",
            "crane_drop": "slow_forward",
            "handheld_chase": "slow_forward",
            "steadicam_glide": "slow_forward",
            "swish_pan_reveal": "pan",
            "zoom_in_punch": "static",
            "zoom_out_reveal": "static",
            "low_angle_hero": "slow_forward",
            "wide_lens_rush": "slow_forward",
            "fisheye_surge": "slow_forward",
            "deep_focus_tableau": "static",
            "pov_drive": "slow_forward",
        }
        if dsl in dsl_map:
            return dsl_map[dsl]
        if any(token in movement for token in ("helicopter", "drone", "aerial", "fly", "glide")):
            if any(token in movement for token in ("orbit", "circle", "arc")):
                return "orbit"
            return "slow_forward"
        if any(token in movement for token in ("zoom",)):
            return "static"
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

    def _constraint_optional_float(self, shot: TemporalShot, key: str) -> float | None:
        value = self._constraint_value(shot, key)
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value)
            except ValueError:
                return None
        return None

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

    def _constraint_vec2(self, shot: TemporalShot, key: str) -> tuple[float, float] | None:
        value = self._constraint_value(shot, key)
        if isinstance(value, (list, tuple)) and len(value) >= 2:
            try:
                return (float(value[0]), float(value[1]))
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
            "crane_rise": {"rig_style": "crane", "camera_height_start": 2.6, "camera_height_end": 7.8, "camera_distance": 3.4, "fov_start": 52.0, "fov_end": 68.0},
            "crane_drop": {"rig_style": "crane", "camera_height_start": 7.2, "camera_height_end": 1.8, "camera_distance": 2.8, "fov_start": 68.0, "fov_end": 48.0, "focus_distance": 7.5},
            "handheld_chase": {"rig_style": "handheld", "camera_height": 1.35, "camera_distance": 1.9, "lens_profile": "wide_angle", "fov": 74.0, "aperture": 2.8, "focus_distance": 2.3, "dutch": 2.0, "film_grain_intensity": 0.28, "motion_blur_intensity": 0.24, "chromatic_aberration": 0.12},
            "steadicam_glide": {"rig_style": "steadicam", "camera_height": 1.6, "camera_distance": 2.6, "fov": 58.0, "aperture": 4.0, "focus_distance": 3.0, "vignette_intensity": 0.08},
            "swish_pan_reveal": {"rig_style": "tripod", "fov_start": 74.0, "fov_end": 66.0, "zoom_profile": "crash_zoom_out", "motion_blur_intensity": 0.4, "chromatic_aberration": 0.16, "bloom_intensity": 0.18},
            "zoom_in_punch": {"rig_style": "tripod", "fov_start": 74.0, "fov_end": 42.0, "zoom_profile": "zoom_in", "aperture_start": 5.6, "aperture_end": 2.2, "vignette_intensity_start": 0.02, "vignette_intensity_end": 0.22, "contrast_end": 16.0},
            "zoom_out_reveal": {"rig_style": "tripod", "fov_start": 42.0, "fov_end": 76.0, "zoom_profile": "zoom_out", "aperture_start": 2.8, "aperture_end": 8.0, "post_exposure_end": 0.18, "bloom_intensity_end": 0.12},
            "low_angle_hero": {"vantage": "low_angle", "camera_height": 0.55, "camera_distance": 2.4, "lens_profile": "telephoto", "look_at_offset": [0.0, 0.8, 0.0], "fov": 44.0, "aperture": 2.4, "dutch": 4.0},
            "wide_lens_rush": {"lens_profile": "wide_angle", "camera_height": 1.1, "camera_distance": 1.7, "fov": 84.0, "motion_blur_intensity": 0.22, "chromatic_aberration": 0.08},
            "fisheye_surge": {"lens_profile": "fisheye", "camera_height": 0.75, "camera_distance": 1.2, "fov": 95.0, "chromatic_aberration": 0.24, "film_grain_intensity": 0.18},
            "deep_focus_tableau": {"lens_profile": "wide_angle", "camera_height": 2.4, "camera_distance": 4.0, "fov": 72.0, "aperture": 11.0, "focus_distance": 8.0, "contrast": 10.0, "vignette_intensity": 0.06},
            "pov_drive": {"rig_style": "steadicam", "camera_height": 1.1, "camera_distance": 0.35, "look_at_offset": [0.0, 0.15, 6.0], "fov": 82.0, "film_terms": ["point of view"]},
        }
        return presets.get(dsl, {})

    def _resolve_lens_profile(self, shot: TemporalShot) -> str:
        explicit = str(
            self._constraint_value(shot, "lens_profile")
            or self._constraint_value(shot, "lens_family")
            or ""
        ).strip().lower()
        if explicit in _KNOWN_LENS_PROFILES:
            return explicit

        keywords = self._shot_language_blob(shot)
        if "fisheye" in keywords:
            return "fisheye"
        if "telephoto" in keywords or "long lens" in keywords:
            return "telephoto"
        if "wide-angle" in keywords or "wide angle" in keywords or "wide lens" in keywords:
            return "wide_angle"
        return "normal"

    def _resolve_zoom_profile(self, shot: TemporalShot) -> str:
        explicit = str(self._constraint_value(shot, "zoom_profile") or "").strip().lower()
        if explicit:
            return explicit

        keywords = self._shot_language_blob(shot)
        if "crash zoom" in keywords:
            return "crash_zoom_in" if "in" in keywords else "crash_zoom_out"
        if "zoom in" in keywords or "push in" in keywords:
            return "zoom_in"
        if "zoom out" in keywords or "pull out" in keywords:
            return "zoom_out"
        return ""

    def _shape_zoom_progress(self, motion_t: float, zoom_profile: str) -> float:
        t = max(0.0, min(1.0, motion_t))
        if zoom_profile in {"crash_zoom_in", "crash_zoom_out"}:
            return min(1.0, math.sqrt(t))
        if zoom_profile in {"breathing", "pulse"}:
            return 0.5 - 0.5 * math.cos(math.pi * t)
        return t

    def _compute_zoom_profile_fov(self, base_fov: float, zoom_profile: str, motion_t: float) -> float:
        profile = (zoom_profile or "").strip().lower()
        if profile in {"zoom_in", "push_in"}:
            start = min(95.0, base_fov + 10.0)
            end = max(28.0, base_fov - 8.0)
            return start + (end - start) * motion_t
        if profile == "zoom_out":
            start = max(28.0, base_fov - 8.0)
            end = min(95.0, base_fov + 10.0)
            return start + (end - start) * motion_t
        if profile == "crash_zoom_in":
            start = min(95.0, base_fov + 18.0)
            end = max(28.0, base_fov - 10.0)
            t = min(1.0, math.sqrt(motion_t))
            return start + (end - start) * t
        if profile == "crash_zoom_out":
            start = max(28.0, base_fov - 10.0)
            end = min(95.0, base_fov + 18.0)
            t = min(1.0, math.sqrt(motion_t))
            return start + (end - start) * t
        if profile in {"breathing", "pulse"}:
            return base_fov + 2.8 * math.sin(2.0 * math.pi * motion_t)
        return base_fov

    def _resolve_rig_style(self, shot: TemporalShot) -> str:
        explicit = str(self._constraint_value(shot, "rig_style") or "").strip().lower()
        if explicit:
            return explicit

        keywords = self._shot_language_blob(shot)
        if "handheld" in keywords:
            return "handheld"
        if "steadicam" in keywords:
            return "steadicam"
        if "crane" in keywords:
            return "crane"
        return "default"

    def _apply_rig_style(
        self,
        points: list[Vec3],
        timestamps: list[float],
        shot: TemporalShot,
    ) -> list[Vec3]:
        rig_style = self._resolve_rig_style(shot)
        if rig_style != "handheld" or len(points) < 2:
            return points
        # Runtime noise is now applied in Unity via Cinemachine so the saved trajectory
        # remains readable and deterministic.
        return points

    def _resolve_base_aperture(self, shot: TemporalShot) -> float:
        keywords = self._shot_language_blob(shot)
        if "deep focus" in keywords:
            return 11.0
        if any(token in keywords for token in ("close-up", "close up", "portrait", "intimate", "hero")):
            return 2.8
        if any(token in keywords for token in ("aerial", "overhead", "high angle", "surveillance")):
            return 8.0
        if self._resolve_lens_profile(shot) == "telephoto":
            return 3.2
        return 5.6

    def _resolve_noise_settings(self, shot: TemporalShot, rig_style: str) -> tuple[float, float]:
        if rig_style != "handheld":
            return 0.0, 0.0
        amplitude = self._constraint_float(shot, "shake_amplitude", default=0.06)
        frequency = self._constraint_float(shot, "shake_frequency", default=6.5)
        amplitude_gain = max(0.25, min(4.0, amplitude / 0.06))
        frequency_gain = max(0.35, min(3.0, frequency / 6.5))
        return amplitude_gain, frequency_gain

    def _focal_length_from_fov(self, fov: float) -> float:
        sensor_height = _DEFAULT_SENSOR_SIZE[1]
        radians = math.radians(max(1e-3, min(179.0, fov)))
        return sensor_height / (2.0 * math.tan(radians * 0.5))

    def _shot_language_blob(self, shot: TemporalShot) -> str:
        parts: list[str] = [
            shot.shot_type or "",
            shot.movement or "",
            shot.goal or "",
            shot.rationale or "",
            str(self._constraint_value(shot, "vantage") or ""),
            str(self._constraint_value(shot, "camera_style") or ""),
            str(self._constraint_value(shot, "lens_profile") or ""),
            str(self._constraint_value(shot, "rig_style") or ""),
            str(self._constraint_value(shot, "dsl") or ""),
        ]
        film_terms = self._constraint_value(shot, "film_terms")
        if isinstance(film_terms, list):
            parts.extend(str(term) for term in film_terms)
        elif film_terms:
            parts.append(str(film_terms))
        return " ".join(parts).lower()

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
                dutch=points[j].dutch,
                focus_distance=points[j].focus_distance,
                aperture=points[j].aperture,
                focal_length=points[j].focal_length,
                lens_shift=points[j].lens_shift,
                bloom_intensity=points[j].bloom_intensity,
                bloom_threshold=points[j].bloom_threshold,
                vignette_intensity=points[j].vignette_intensity,
                post_exposure=points[j].post_exposure,
                saturation=points[j].saturation,
                contrast=points[j].contrast,
                chromatic_aberration=points[j].chromatic_aberration,
                film_grain_intensity=points[j].film_grain_intensity,
                motion_blur_intensity=points[j].motion_blur_intensity,
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
                dutch=points[j].dutch,
                focus_distance=points[j].focus_distance,
                aperture=points[j].aperture,
                focal_length=points[j].focal_length,
                lens_shift=points[j].lens_shift,
                bloom_intensity=points[j].bloom_intensity,
                bloom_threshold=points[j].bloom_threshold,
                vignette_intensity=points[j].vignette_intensity,
                post_exposure=points[j].post_exposure,
                saturation=points[j].saturation,
                contrast=points[j].contrast,
                chromatic_aberration=points[j].chromatic_aberration,
                film_grain_intensity=points[j].film_grain_intensity,
                motion_blur_intensity=points[j].motion_blur_intensity,
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
