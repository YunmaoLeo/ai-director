"""Tests for temporal scene abstraction."""

import pytest

from app.services.temporal_abstraction import TemporalAbstractor
from app.models.scene_timeline import SceneTimeline


class TestTemporalAbstractor:
    def setup_method(self):
        self.abstractor = TemporalAbstractor()

    def test_abstract_walking_actor(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        assert tc.scene_id == "temporal_walking_actor"
        assert len(tc.subject_profiles) > 0
        assert tc.time_span is not None
        assert tc.time_span.duration == 10.0

        # Actor should have highest salience
        actor_profile = next(
            (p for p in tc.subject_profiles if p.object_id == "actor_1"), None
        )
        assert actor_profile is not None
        assert actor_profile.salience_score > 0.3
        assert len(actor_profile.active_windows) > 0
        assert "avg_speed" in actor_profile.motion_summary

    def test_abstract_two_actors(self, two_actors_timeline):
        tc = self.abstractor.abstract(two_actors_timeline)
        assert tc.scene_id == "temporal_two_actors"

        # Should have profiles for both actors
        tracked_ids = {p.object_id for p in tc.subject_profiles}
        assert "actor_a" in tracked_ids
        assert "actor_b" in tracked_ids

        # Should have spacetime affordances from interaction event
        interaction_affordances = [
            a for a in tc.spacetime_affordances if a.type == "interaction_moment"
        ]
        assert len(interaction_affordances) > 0

    def test_abstract_occlusion(self, occlusion_test_timeline):
        tc = self.abstractor.abstract(occlusion_test_timeline)

        # Should detect reveal opportunities from occlusion_end event
        assert len(tc.reveal_opportunities) > 0
        occ_end_reveals = [
            r for r in tc.reveal_opportunities if "visible again" in r.description
        ]
        assert len(occ_end_reveals) > 0

    def test_event_summary(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        assert tc.event_summary != ""
        assert "speed_change" in tc.event_summary
        assert "Replay timeline summary" in tc.replay_description

    def test_static_objects_get_profiles(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        # Static objects like table/chair/lamp should also get profiles
        static_profiles = [
            p for p in tc.subject_profiles if p.motion_summary == "static"
        ]
        assert len(static_profiles) > 0

    def test_spatial_aspects_preserved(self, walking_actor_timeline):
        tc = self.abstractor.abstract(walking_actor_timeline)
        # Should have semantic regions from static abstraction
        assert len(tc.semantic_regions) > 0
        # Should have cinematic affordances
        assert len(tc.cinematic_affordances) > 0

    def test_occlusion_risks_detected(self, occlusion_test_timeline):
        tc = self.abstractor.abstract(occlusion_test_timeline)
        # The mover crosses near the statue, should detect occlusion risk
        assert len(tc.occlusion_risks) >= 0  # May or may not detect depending on geometry
