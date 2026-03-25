"""Validates temporal directing plans and trajectory plans."""

from app.models.scene_timeline import SceneTimeline
from app.models.temporal_directing_plan import TemporalDirectingPlan
from app.models.temporal_trajectory_plan import TemporalTrajectoryPlan
from app.models.validation_report import ValidationIssue, ValidationReport
from app.utils.geometry_utils import vec3_distance, interpolate_track_at_time


class TemporalPlanValidator:
    def validate_temporal_directing_plan(
        self,
        plan: TemporalDirectingPlan,
        timeline: SceneTimeline,
    ) -> ValidationReport:
        """Validate a temporal directing plan against the scene timeline."""
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        valid_ids = {o.id for o in timeline.objects_static}
        valid_ids.update(t.object_id for t in timeline.object_tracks)
        valid_ids.add("room")

        t_start = timeline.time_span.start
        t_end = timeline.time_span.end

        # Structural checks
        if not plan.shots:
            errors.append(ValidationIssue(
                level="error", category="structural",
                message="Plan must contain at least one shot", field="shots",
            ))

        shot_ids = set()
        for shot in plan.shots:
            if shot.shot_id in shot_ids:
                errors.append(ValidationIssue(
                    level="error", category="structural",
                    message=f"Duplicate shot_id: {shot.shot_id}", field="shots",
                ))
            shot_ids.add(shot.shot_id)

            if shot.time_end <= shot.time_start:
                errors.append(ValidationIssue(
                    level="error", category="structural",
                    message=f"Shot {shot.shot_id} has non-positive time span "
                            f"({shot.time_start}s to {shot.time_end}s)",
                    field=f"shots.{shot.shot_id}",
                ))

        # Scene reference checks
        for shot in plan.shots:
            if shot.subject not in valid_ids:
                errors.append(ValidationIssue(
                    level="error", category="scene_reference",
                    message=f"Shot {shot.shot_id} references unknown subject '{shot.subject}'",
                    field=f"shots.{shot.shot_id}.subject",
                ))

        # Time coverage checks
        if plan.shots:
            sorted_shots = sorted(plan.shots, key=lambda s: s.time_start)

            # Check for gaps
            if sorted_shots[0].time_start - t_start > 2.0:
                warnings.append(ValidationIssue(
                    level="warning", category="time_coverage",
                    message=f"Large gap at start: first shot starts at "
                            f"{sorted_shots[0].time_start}s (scene starts at {t_start}s)",
                    field="shots",
                ))

            for i in range(1, len(sorted_shots)):
                gap = sorted_shots[i].time_start - sorted_shots[i - 1].time_end
                if gap > 2.0:
                    warnings.append(ValidationIssue(
                        level="warning", category="time_coverage",
                        message=f"Gap of {gap:.1f}s between {sorted_shots[i-1].shot_id} "
                                f"and {sorted_shots[i].shot_id}",
                        field="shots",
                    ))

            if t_end - sorted_shots[-1].time_end > 2.0:
                warnings.append(ValidationIssue(
                    level="warning", category="time_coverage",
                    message=f"Large gap at end: last shot ends at "
                            f"{sorted_shots[-1].time_end}s (scene ends at {t_end}s)",
                    field="shots",
                ))

            # Check for overlaps
            for i in range(len(sorted_shots)):
                for j in range(i + 1, len(sorted_shots)):
                    s1, s2 = sorted_shots[i], sorted_shots[j]
                    if s1.time_start < s2.time_end and s2.time_start < s1.time_end:
                        overlap = min(s1.time_end, s2.time_end) - max(s1.time_start, s2.time_start)
                        if overlap > 0.1:
                            warnings.append(ValidationIssue(
                                level="warning", category="time_coverage",
                                message=f"Shots {s1.shot_id} and {s2.shot_id} overlap by {overlap:.1f}s",
                                field="shots",
                            ))

        # Subject availability checks
        tracks_by_id = {t.object_id: t for t in timeline.object_tracks}
        for shot in plan.shots:
            if shot.subject == "room":
                continue
            track = tracks_by_id.get(shot.subject)
            if track and track.samples:
                # Check if subject is visible during the shot window
                visible_during_shot = False
                for sample in track.samples:
                    if shot.time_start <= sample.timestamp <= shot.time_end and sample.visible:
                        visible_during_shot = True
                        break
                if not visible_during_shot:
                    warnings.append(ValidationIssue(
                        level="warning", category="subject_availability",
                        message=f"Subject '{shot.subject}' may not be visible during "
                                f"shot {shot.shot_id} [{shot.time_start}s-{shot.time_end}s]",
                        field=f"shots.{shot.shot_id}.subject",
                    ))

        # Beat-shot alignment
        if plan.beats:
            beat_ids = {b.beat_id for b in plan.beats}
            for shot in plan.shots:
                if shot.beat_id and shot.beat_id not in beat_ids:
                    warnings.append(ValidationIssue(
                        level="warning", category="structural",
                        message=f"Shot {shot.shot_id} references unknown beat '{shot.beat_id}'",
                        field=f"shots.{shot.shot_id}.beat_id",
                    ))

        return ValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_temporal_trajectory_plan(
        self,
        trajectory: TemporalTrajectoryPlan,
        plan: TemporalDirectingPlan,
        timeline: SceneTimeline,
    ) -> ValidationReport:
        """Validate a temporal trajectory plan."""
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        plan_shot_ids = {s.shot_id for s in plan.shots}
        w, l = timeline.bounds.width, timeline.bounds.length

        for traj in trajectory.trajectories:
            # Shot reference check
            if traj.shot_id not in plan_shot_ids:
                errors.append(ValidationIssue(
                    level="error", category="trajectory",
                    message=f"Trajectory references unknown shot_id '{traj.shot_id}'",
                    field=f"trajectories.{traj.shot_id}",
                ))

            # Empty points check
            if not traj.timed_points:
                errors.append(ValidationIssue(
                    level="error", category="trajectory",
                    message=f"Trajectory {traj.shot_id} has no timed points",
                    field=f"trajectories.{traj.shot_id}.timed_points",
                ))
                continue

            # Monotonically increasing timestamps
            for i in range(1, len(traj.timed_points)):
                if traj.timed_points[i].timestamp <= traj.timed_points[i - 1].timestamp:
                    errors.append(ValidationIssue(
                        level="error", category="trajectory",
                        message=f"Trajectory {traj.shot_id} timestamps not monotonically "
                                f"increasing at index {i}",
                        field=f"trajectories.{traj.shot_id}.timed_points",
                    ))
                    break

            # Camera within scene bounds
            for i, pt in enumerate(traj.timed_points):
                pos = pt.position
                if pos[0] < -1 or pos[0] > w + 1 or pos[2] < -1 or pos[2] > l + 1:
                    warnings.append(ValidationIssue(
                        level="warning", category="trajectory",
                        message=f"Trajectory {traj.shot_id} point {i} "
                                f"({pos[0]:.1f}, {pos[1]:.1f}, {pos[2]:.1f}) "
                                f"is outside scene bounds",
                        field=f"trajectories.{traj.shot_id}.timed_points",
                    ))
                    break

            # FOV range check
            for pt in traj.timed_points:
                if not (10.0 <= pt.fov <= 120.0):
                    warnings.append(ValidationIssue(
                        level="warning", category="trajectory",
                        message=f"Trajectory {traj.shot_id} has unusual FOV: {pt.fov}",
                        field=f"trajectories.{traj.shot_id}.timed_points",
                    ))
                    break

        # Shot boundary continuity
        sorted_trajs = sorted(trajectory.trajectories, key=lambda t: t.time_start)
        for i in range(1, len(sorted_trajs)):
            prev = sorted_trajs[i - 1]
            curr = sorted_trajs[i]
            if not prev.timed_points or not curr.timed_points:
                continue
            gap = curr.time_start - prev.time_end
            if gap <= 0.5:
                prev_end = prev.timed_points[-1].position
                curr_start = curr.timed_points[0].position
                delta = vec3_distance(prev_end, curr_start)
                if delta > 3.0:
                    warnings.append(ValidationIssue(
                        level="warning", category="trajectory",
                        message=f"Large position jump ({delta:.1f}m) between "
                                f"{prev.shot_id} and {curr.shot_id}",
                        field="trajectories",
                    ))

        return ValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
