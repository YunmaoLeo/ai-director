"""Temporal scene abstraction: derives a TemporalCinematicScene from a SceneTimeline.

Reuses static SceneAbstractor + AffordanceAnalyzer for spatial aspects,
then adds temporal-specific analysis layers.
"""

from app.models.scene_summary import SceneSummary
from app.models.scene_timeline import SceneTimeline, ObjectTrack, SceneEvent
from app.models.temporal_cinematic_scene import (
    TemporalCinematicScene,
    SubjectTemporalProfile,
    SpaceTimeAffordance,
    OcclusionRiskWindow,
    RevealOpportunity,
)
from app.models.temporal_enums import EventType
from app.services.scene_abstraction import SceneAbstractor
from app.services.affordance_analyzer import AffordanceAnalyzer
from app.utils.geometry_utils import (
    compute_motion_descriptor,
    xz_distance,
    interpolate_track_at_time,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TemporalAbstractor:
    def __init__(self):
        self._static_abstractor = SceneAbstractor()
        self._affordance_analyzer = AffordanceAnalyzer()

    def abstract(self, timeline: SceneTimeline) -> TemporalCinematicScene:
        """Build a TemporalCinematicScene from a SceneTimeline."""
        # Build a static SceneSummary snapshot for reuse
        snapshot = SceneSummary(
            scene_id=timeline.scene_id,
            scene_name=timeline.scene_name,
            scene_type=timeline.scene_type,
            description=timeline.description,
            bounds=timeline.bounds,
            objects=timeline.objects_static,
            relations=timeline.relations,
            free_space=timeline.free_space,
        )

        # Reuse static abstraction
        cinematic = self._static_abstractor.abstract(snapshot)
        cinematic = self._affordance_analyzer.analyze(snapshot, cinematic)

        # Build temporal layers
        subject_profiles = self._build_subject_profiles(timeline)
        spacetime_affordances = self._build_spacetime_affordances(timeline)
        occlusion_risks = self._detect_occlusion_risks(timeline)
        reveal_opportunities = self._detect_reveal_opportunities(timeline)
        event_summary = self._summarize_events(timeline)
        replay_description = self._build_replay_description(timeline, subject_profiles, event_summary)

        return TemporalCinematicScene(
            scene_id=timeline.scene_id,
            semantic_regions=cinematic.semantic_regions,
            primary_subjects=cinematic.primary_subjects,
            secondary_subjects=cinematic.secondary_subjects,
            object_groups=cinematic.object_groups,
            spatial_summary=cinematic.spatial_summary,
            cinematic_affordances=cinematic.cinematic_affordances,
            visibility_hints=cinematic.visibility_hints,
            framing_hints=cinematic.framing_hints,
            subject_profiles=subject_profiles,
            spacetime_affordances=spacetime_affordances,
            occlusion_risks=occlusion_risks,
            reveal_opportunities=reveal_opportunities,
            event_summary=event_summary,
            replay_description=replay_description,
            time_span=timeline.time_span,
        )

    def _build_subject_profiles(
        self, timeline: SceneTimeline
    ) -> list[SubjectTemporalProfile]:
        """Rank subjects by motion magnitude + importance; compute active windows."""
        profiles: list[SubjectTemporalProfile] = []
        obj_importance = {o.id: o.importance for o in timeline.objects_static}

        for track in timeline.object_tracks:
            samples_dicts = [s.model_dump() for s in track.samples]
            motion = compute_motion_descriptor(samples_dicts)

            # Active windows = contiguous visibility windows
            active_windows = self._compute_active_windows(track)

            importance = obj_importance.get(track.object_id, 0.5)
            salience = importance * 0.6 + min(motion["average_speed"] / 2.0, 0.4)
            role = "primary" if salience >= 0.5 else "secondary"

            motion_summary = (
                f"avg_speed={motion['average_speed']:.2f}, "
                f"max_speed={motion['max_speed']:.2f}, "
                f"displacement={motion['total_displacement']:.2f}, "
                f"accel={motion['acceleration_bucket']}"
            )

            profiles.append(SubjectTemporalProfile(
                object_id=track.object_id,
                role=role,
                salience_score=round(salience, 3),
                active_windows=active_windows,
                motion_summary=motion_summary,
            ))

        # Also add static objects without tracks
        tracked_ids = {t.object_id for t in timeline.object_tracks}
        for obj in timeline.objects_static:
            if obj.id not in tracked_ids:
                profiles.append(SubjectTemporalProfile(
                    object_id=obj.id,
                    role="primary" if obj.importance >= 0.6 else "secondary",
                    salience_score=round(obj.importance * 0.6, 3),
                    active_windows=[(timeline.time_span.start, timeline.time_span.end)],
                    motion_summary="static",
                ))

        profiles.sort(key=lambda p: -p.salience_score)
        return profiles

    def _compute_active_windows(
        self, track: ObjectTrack
    ) -> list[tuple[float, float]]:
        """Compute contiguous windows where the object is visible."""
        if not track.samples:
            return []

        windows: list[tuple[float, float]] = []
        window_start: float | None = None

        for sample in track.samples:
            if sample.visible:
                if window_start is None:
                    window_start = sample.timestamp
            else:
                if window_start is not None:
                    windows.append((window_start, sample.timestamp))
                    window_start = None

        if window_start is not None:
            windows.append((window_start, track.samples[-1].timestamp))

        return windows

    def _build_spacetime_affordances(
        self, timeline: SceneTimeline
    ) -> list[SpaceTimeAffordance]:
        """Time-windowed filming opportunities from camera candidates + tracks."""
        affordances: list[SpaceTimeAffordance] = []
        idx = 0

        for cc in timeline.camera_candidates:
            # Find tracks active during this camera candidate window
            active_obj_ids: list[str] = []
            for track in timeline.object_tracks:
                for sample in track.samples:
                    if cc.time_start <= sample.timestamp <= cc.time_end and sample.visible:
                        active_obj_ids.append(track.object_id)
                        break

            affordances.append(SpaceTimeAffordance(
                affordance_id=f"sta_{idx}",
                type="camera_opportunity",
                description=(
                    f"Camera region {cc.region_id} available "
                    f"[{cc.time_start:.1f}s-{cc.time_end:.1f}s] "
                    f"with {len(active_obj_ids)} active subjects"
                ),
                time_start=cc.time_start,
                time_end=cc.time_end,
                object_ids=active_obj_ids,
                score=cc.clearance_score,
            ))
            idx += 1

        # Also generate affordances from events
        for event in timeline.events:
            if event.event_type in (EventType.interaction.value, "interaction"):
                affordances.append(SpaceTimeAffordance(
                    affordance_id=f"sta_{idx}",
                    type="interaction_moment",
                    description=f"Interaction event: {event.description}",
                    time_start=event.timestamp,
                    time_end=event.timestamp + event.duration,
                    object_ids=event.object_ids,
                    score=0.8,
                ))
                idx += 1

        return affordances

    def _detect_occlusion_risks(
        self, timeline: SceneTimeline
    ) -> list[OcclusionRiskWindow]:
        """Pairwise XZ overlap checks across time for moving objects."""
        risks: list[OcclusionRiskWindow] = []
        tracks = timeline.object_tracks
        static_objs = {o.id: o for o in timeline.objects_static}
        time_step = 0.5  # Check every 0.5s

        if not tracks:
            return risks

        t = timeline.time_span.start
        while t <= timeline.time_span.end:
            # Check each track against static objects and other tracks
            for i, track_a in enumerate(tracks):
                samples_a = [s.model_dump() for s in track_a.samples]
                pos_a = interpolate_track_at_time(samples_a, t)

                # Check against static objects
                for obj in timeline.objects_static:
                    if obj.id == track_a.object_id:
                        continue
                    dist = xz_distance(pos_a, obj.position)
                    overlap_threshold = (obj.size[0] + obj.size[2]) / 4 + 0.5
                    if dist < overlap_threshold:
                        # Check if this risk window already exists
                        existing = None
                        for r in risks:
                            if (r.blocker_id == obj.id and r.blocked_id == track_a.object_id
                                    and abs(r.time_end - t) < time_step * 1.5):
                                existing = r
                                break
                        if existing:
                            existing.time_end = t
                        else:
                            risks.append(OcclusionRiskWindow(
                                time_start=t,
                                time_end=t + time_step,
                                blocker_id=obj.id,
                                blocked_id=track_a.object_id,
                                severity=min(1.0, overlap_threshold / max(dist, 0.01)),
                            ))

                # Check against other tracks
                for j in range(i + 1, len(tracks)):
                    track_b = tracks[j]
                    samples_b = [s.model_dump() for s in track_b.samples]
                    pos_b = interpolate_track_at_time(samples_b, t)
                    dist = xz_distance(pos_a, pos_b)
                    if dist < 1.0:
                        existing = None
                        for r in risks:
                            if (r.blocker_id == track_b.object_id
                                    and r.blocked_id == track_a.object_id
                                    and abs(r.time_end - t) < time_step * 1.5):
                                existing = r
                                break
                        if existing:
                            existing.time_end = t
                        else:
                            risks.append(OcclusionRiskWindow(
                                time_start=t,
                                time_end=t + time_step,
                                blocker_id=track_b.object_id,
                                blocked_id=track_a.object_id,
                                severity=min(1.0, 1.0 / max(dist, 0.01)),
                            ))

            t += time_step

        return risks

    def _detect_reveal_opportunities(
        self, timeline: SceneTimeline
    ) -> list[RevealOpportunity]:
        """Detect reveal opportunities from appear and occlusion_end events."""
        opportunities: list[RevealOpportunity] = []

        for event in timeline.events:
            if event.event_type in (EventType.appear.value, "appear"):
                for obj_id in event.object_ids:
                    opportunities.append(RevealOpportunity(
                        time=event.timestamp,
                        object_id=obj_id,
                        description=f"{obj_id} appears: {event.description}",
                        score=0.7,
                    ))
            elif event.event_type in (EventType.occlusion_end.value, "occlusion_end"):
                for obj_id in event.object_ids:
                    opportunities.append(RevealOpportunity(
                        time=event.timestamp,
                        object_id=obj_id,
                        description=f"{obj_id} becomes visible again: {event.description}",
                        score=0.6,
                    ))

        return opportunities

    def _summarize_events(self, timeline: SceneTimeline) -> str:
        """Textual summary of timeline events for LLM context."""
        if not timeline.events:
            return "No notable events in this timeline."

        lines = [
            f"Timeline spans {timeline.time_span.duration:.1f}s "
            f"with {len(timeline.events)} events:"
        ]
        for event in timeline.events:
            lines.append(
                f"  - [{event.timestamp:.1f}s] {event.event_type}: {event.description}"
            )
        return "\n".join(lines)

    def _build_replay_description(
        self,
        timeline: SceneTimeline,
        subject_profiles: list[SubjectTemporalProfile],
        event_summary: str,
    ) -> str:
        """Build a compact narrative description from timeline replay data."""
        top_subjects = subject_profiles[:3]
        if top_subjects:
            subjects_text = ", ".join(
                f"{s.object_id}({s.role}, salience={s.salience_score:.2f})"
                for s in top_subjects
            )
        else:
            subjects_text = "none"

        track_count = len(timeline.object_tracks)
        event_count = len(timeline.events)
        duration = timeline.time_span.duration
        room_text = (
            f"{timeline.scene_name} ({timeline.scene_type}), "
            f"{timeline.bounds.width:.1f}m x {timeline.bounds.length:.1f}m x {timeline.bounds.height:.1f}m"
        )

        lines = [
            f"Replay timeline summary for {room_text}.",
            f"Time window: {timeline.time_span.start:.1f}s to {timeline.time_span.end:.1f}s ({duration:.1f}s).",
            f"Tracked dynamic subjects: {track_count}. Notable events: {event_count}.",
            f"Primary temporal subjects: {subjects_text}.",
            "Event timeline:",
            event_summary,
        ]
        return "\n".join(lines)
