"""Validates directing plans and trajectory plans against schemas and scene data."""

from app.models.scene_summary import SceneSummary
from app.models.directing_plan import DirectingPlan
from app.models.trajectory_plan import TrajectoryPlan
from app.models.validation_report import ValidationIssue, ValidationReport
from app.models.enums import ShotType, Movement, Pacing


class PlanValidator:
    def validate_directing_plan(
        self, plan: DirectingPlan, scene: SceneSummary
    ) -> ValidationReport:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []
        object_ids = {o.id for o in scene.objects}
        object_ids.add("room")  # "room" is a valid virtual subject

        # Structural
        if not plan.shots:
            errors.append(ValidationIssue(
                level="error", category="structural",
                message="Plan must contain at least one shot", field="shots",
            ))

        if plan.total_duration <= 0:
            errors.append(ValidationIssue(
                level="error", category="structural",
                message="total_duration must be positive", field="total_duration",
            ))

        shot_ids = set()
        for shot in plan.shots:
            if shot.shot_id in shot_ids:
                errors.append(ValidationIssue(
                    level="error", category="structural",
                    message=f"Duplicate shot_id: {shot.shot_id}", field="shots",
                ))
            shot_ids.add(shot.shot_id)

            if shot.duration <= 0:
                errors.append(ValidationIssue(
                    level="error", category="structural",
                    message=f"Shot {shot.shot_id} has non-positive duration",
                    field=f"shots.{shot.shot_id}.duration",
                ))

        # Scene reference
        if plan.scene_id != scene.scene_id:
            errors.append(ValidationIssue(
                level="error", category="scene_reference",
                message=f"Plan scene_id '{plan.scene_id}' does not match scene '{scene.scene_id}'",
                field="scene_id",
            ))

        for shot in plan.shots:
            if shot.subject not in object_ids:
                errors.append(ValidationIssue(
                    level="error", category="scene_reference",
                    message=f"Shot {shot.shot_id} references unknown subject '{shot.subject}'",
                    field=f"shots.{shot.shot_id}.subject",
                ))
            for vis_obj in shot.constraints.keep_objects_visible:
                if vis_obj not in object_ids:
                    warnings.append(ValidationIssue(
                        level="warning", category="scene_reference",
                        message=f"Shot {shot.shot_id} constraint references unknown object '{vis_obj}'",
                        field=f"shots.{shot.shot_id}.constraints.keep_objects_visible",
                    ))

        # Semantic
        if not plan.summary:
            warnings.append(ValidationIssue(
                level="warning", category="semantic",
                message="Plan is missing a summary", field="summary",
            ))

        computed_duration = sum(s.duration for s in plan.shots)
        if abs(computed_duration - plan.total_duration) > 0.5:
            warnings.append(ValidationIssue(
                level="warning", category="semantic",
                message=(
                    f"total_duration ({plan.total_duration}s) differs from "
                    f"sum of shot durations ({computed_duration}s)"
                ),
                field="total_duration",
            ))

        return ValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

    def validate_trajectory_plan(
        self,
        trajectory: TrajectoryPlan,
        plan: DirectingPlan,
        scene: SceneSummary,
    ) -> ValidationReport:
        errors: list[ValidationIssue] = []
        warnings: list[ValidationIssue] = []

        plan_shot_ids = {s.shot_id for s in plan.shots}
        for traj in trajectory.trajectories:
            if traj.shot_id not in plan_shot_ids:
                errors.append(ValidationIssue(
                    level="error", category="trajectory",
                    message=f"Trajectory references unknown shot_id '{traj.shot_id}'",
                    field=f"trajectories.{traj.shot_id}",
                ))

            if traj.duration <= 0:
                errors.append(ValidationIssue(
                    level="error", category="trajectory",
                    message=f"Trajectory {traj.shot_id} has non-positive duration",
                    field=f"trajectories.{traj.shot_id}.duration",
                ))

            if not traj.sampled_points:
                errors.append(ValidationIssue(
                    level="error", category="trajectory",
                    message=f"Trajectory {traj.shot_id} has no sampled points",
                    field=f"trajectories.{traj.shot_id}.sampled_points",
                ))

            if not (10.0 <= traj.fov <= 120.0):
                warnings.append(ValidationIssue(
                    level="warning", category="trajectory",
                    message=f"Trajectory {traj.shot_id} has unusual fov: {traj.fov}",
                    field=f"trajectories.{traj.shot_id}.fov",
                ))

            # Check sampled points are broadly within scene bounds
            w, l = scene.bounds.width, scene.bounds.length
            for i, pt in enumerate(traj.sampled_points):
                if pt[0] < -1 or pt[0] > w + 1 or pt[2] < -1 or pt[2] > l + 1:
                    warnings.append(ValidationIssue(
                        level="warning", category="trajectory",
                        message=(
                            f"Trajectory {traj.shot_id} point {i} "
                            f"({pt[0]:.1f}, {pt[1]:.1f}, {pt[2]:.1f}) "
                            f"is outside scene bounds"
                        ),
                        field=f"trajectories.{traj.shot_id}.sampled_points",
                    ))
                    break  # One warning is enough

        return ValidationReport(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )
