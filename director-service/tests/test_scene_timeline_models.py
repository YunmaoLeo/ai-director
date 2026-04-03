"""Tests for temporal data model loading and validation."""

import pytest

from app.models.scene_timeline import (
    SceneTimeline, TimeSpan, ObjectTrackSample, ObjectTrack,
    MotionDescriptor, SceneEvent, CameraCandidate, SemanticSceneEvent,
)
from app.models.temporal_enums import EventType, TransitionType, PlanningPassType
from app.models.temporal_directing_plan import Beat, TemporalShot, TemporalDirectingPlan
from app.models.temporal_trajectory_plan import TimedTrajectoryPoint, TemporalShotTrajectory, TemporalTrajectoryPlan
from app.models.planning_pass import PlanningPassArtifact, TemporalRunBundle


class TestTimeSpan:
    def test_create(self):
        ts = TimeSpan(start=0.0, end=10.0, duration=10.0)
        assert ts.start == 0.0
        assert ts.end == 10.0
        assert ts.duration == 10.0


class TestObjectTrack:
    def test_create_with_samples(self):
        samples = [
            ObjectTrackSample(timestamp=0.0, position=(1, 0, 2)),
            ObjectTrackSample(timestamp=1.0, position=(2, 0, 3)),
        ]
        track = ObjectTrack(object_id="actor_1", samples=samples)
        assert track.object_id == "actor_1"
        assert len(track.samples) == 2
        assert track.samples[0].visible is True

    def test_default_values(self):
        sample = ObjectTrackSample(timestamp=0.0, position=(0, 0, 0))
        assert sample.rotation == (0.0, 0.0, 0.0)
        assert sample.velocity == (0.0, 0.0, 0.0)
        assert sample.visible is True


class TestSceneTimeline:
    def test_load_walking_actor(self, walking_actor_timeline):
        tl = walking_actor_timeline
        assert tl.scene_id == "temporal_walking_actor"
        assert tl.time_span.duration == 10.0
        assert len(tl.objects_static) == 4
        assert len(tl.object_tracks) == 1
        assert tl.object_tracks[0].object_id == "actor_1"
        assert len(tl.object_tracks[0].samples) == 11
        assert len(tl.events) == 1

    def test_load_two_actors(self, two_actors_timeline):
        tl = two_actors_timeline
        assert tl.scene_id == "temporal_two_actors"
        assert tl.time_span.duration == 12.0
        assert len(tl.object_tracks) == 2
        assert len(tl.events) == 1
        assert tl.events[0].event_type == "interaction"

    def test_load_occlusion(self, occlusion_test_timeline):
        tl = occlusion_test_timeline
        assert tl.scene_id == "temporal_occlusion_test"
        assert len(tl.events) == 2
        assert tl.events[0].event_type == "occlusion_start"
        assert tl.events[1].event_type == "occlusion_end"

    def test_semantic_event_defaults(self):
        event = SemanticSceneEvent(
            semantic_id="sem_0001",
            label="Lead Change",
            time_start=1.0,
            time_end=1.6,
            summary="Blue briefly overtakes red.",
        )
        assert event.dramatic_role == "develop"
        assert event.camera_implication == "maintain_subject_continuity"


class TestTemporalEnums:
    def test_event_types(self):
        assert EventType.appear.value == "appear"
        assert EventType.interaction.value == "interaction"

    def test_transition_types(self):
        assert TransitionType.cut.value == "cut"
        assert TransitionType.flash_cut.value == "flash_cut"
        assert TransitionType.smooth.value == "smooth"

    def test_planning_pass_types(self):
        assert PlanningPassType.global_beat.value == "global_beat"
        assert PlanningPassType.shot_intent.value == "shot_intent"


class TestTemporalDirectingPlan:
    def test_create_beat(self):
        beat = Beat(
            beat_id="beat_1",
            time_start=0.0,
            time_end=5.0,
            goal="Introduction",
            mood="calm",
            subjects=["actor_1"],
        )
        assert beat.beat_id == "beat_1"
        assert beat.time_end - beat.time_start == 5.0

    def test_create_temporal_shot(self):
        shot = TemporalShot(
            shot_id="shot_1",
            time_start=0.0,
            time_end=3.0,
            goal="Establish scene",
            subject="room",
            shot_type="establishing",
            movement="slow_forward",
        )
        assert shot.pacing == "steady"
        assert shot.transition_in == "cut"

    def test_create_plan(self):
        plan = TemporalDirectingPlan(
            plan_id="test_plan",
            scene_id="test_scene",
            intent="test",
            beats=[Beat(beat_id="b1", time_start=0, time_end=5, goal="test")],
            shots=[TemporalShot(
                shot_id="s1", time_start=0, time_end=5,
                goal="test", subject="room",
                shot_type="wide", movement="static",
            )],
        )
        assert len(plan.beats) == 1
        assert len(plan.shots) == 1


class TestTemporalTrajectoryPlan:
    def test_create_timed_point(self):
        pt = TimedTrajectoryPoint(
            timestamp=1.0,
            position=(3.0, 1.5, 4.0),
            look_at=(2.0, 0.5, 3.0),
            fov=50.0,
            dutch=6.0,
            focus_distance=4.5,
            aperture=2.8,
            focal_length=55.0,
            lens_shift=(0.05, -0.02),
        )
        assert pt.timestamp == 1.0
        assert pt.fov == 50.0
        assert pt.dutch == 6.0
        assert pt.focus_distance == 4.5
        assert pt.aperture == 2.8
        assert pt.focal_length == 55.0
        assert pt.lens_shift == (0.05, -0.02)

    def test_create_trajectory(self):
        traj = TemporalShotTrajectory(
            shot_id="shot_1",
            time_start=0.0,
            time_end=5.0,
            timed_points=[
                TimedTrajectoryPoint(timestamp=0, position=(1, 1, 1), look_at=(2, 0, 2)),
                TimedTrajectoryPoint(timestamp=5, position=(3, 1, 3), look_at=(2, 0, 2)),
            ],
        )
        assert len(traj.timed_points) == 2


class TestPlanningPassArtifact:
    def test_create(self):
        artifact = PlanningPassArtifact(
            pass_type=PlanningPassType.global_beat,
            pass_index=0,
            duration_ms=150.0,
            success=True,
        )
        assert artifact.success is True
        assert artifact.error_message == ""

    def test_run_bundle(self):
        bundle = TemporalRunBundle(
            run_id="test_run",
            scene_id="test_scene",
            intent="test",
        )
        assert bundle.temporal_directing_plan is None
        assert len(bundle.pass_artifacts) == 0
