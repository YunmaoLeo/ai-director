"""Builds LLM prompts for temporal multi-pass planning."""

from pathlib import Path

from app.models.scene_timeline import SceneTimeline
from app.models.temporal_cinematic_scene import TemporalCinematicScene
from app.models.temporal_directing_plan import Beat, TemporalShot


_PROMPTS_DIR = Path(__file__).resolve().parent.parent.parent / "prompts"


class TemporalPromptBuilder:
    def __init__(self, prompts_dir: Path | None = None):
        self._dir = prompts_dir or _PROMPTS_DIR

    def build_global_beat_prompt(
        self,
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        intent: str,
        style_profile: str = "default",
        style_brief: str = "",
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the beat planning pass."""
        system = (self._dir / "temporal_system_prompt.txt").read_text(encoding="utf-8")
        template = (self._dir / "temporal_beat_pass_template.txt").read_text(encoding="utf-8")

        user_prompt = template.format(
            scene_name=timeline.scene_name,
            scene_type=timeline.scene_type,
            width=timeline.bounds.width,
            length=timeline.bounds.length,
            height=timeline.bounds.height,
            time_start=timeline.time_span.start,
            time_end=timeline.time_span.end,
            duration=timeline.time_span.duration,
            spatial_summary=temporal_cinematic.spatial_summary,
            objects_text=self._format_static_objects(timeline),
            subject_profiles_text=self._format_subject_profiles(temporal_cinematic),
            event_summary=temporal_cinematic.event_summary,
            spacetime_affordances_text=self._format_spacetime_affordances(temporal_cinematic),
            intent=intent,
        )
        user_prompt += self._append_extra_context(
            replay_description=temporal_cinematic.replay_description,
            style_profile=style_profile,
            style_brief=style_brief,
        )
        return system, user_prompt

    def build_style_intent_prompt(
        self,
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        intent: str,
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for style selection pre-pass."""
        system = (self._dir / "temporal_system_prompt.txt").read_text(encoding="utf-8")
        template = (self._dir / "temporal_style_intent_template.txt").read_text(encoding="utf-8")
        user_prompt = template.format(
            scene_name=timeline.scene_name,
            scene_type=timeline.scene_type,
            time_start=timeline.time_span.start,
            time_end=timeline.time_span.end,
            duration=timeline.time_span.duration,
            replay_description=temporal_cinematic.replay_description,
            intent=intent,
        )
        return system, user_prompt

    def build_shot_intent_prompt(
        self,
        beats: list[Beat],
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        style_profile: str = "default",
        style_brief: str = "",
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the shot intent pass."""
        system = (self._dir / "temporal_system_prompt.txt").read_text(encoding="utf-8")
        template = (self._dir / "temporal_shot_pass_template.txt").read_text(encoding="utf-8")

        user_prompt = template.format(
            scene_name=timeline.scene_name,
            scene_type=timeline.scene_type,
            width=timeline.bounds.width,
            length=timeline.bounds.length,
            height=timeline.bounds.height,
            time_start=timeline.time_span.start,
            time_end=timeline.time_span.end,
            duration=timeline.time_span.duration,
            objects_text=self._format_static_objects(timeline),
            subject_profiles_text=self._format_subject_profiles(temporal_cinematic),
            event_summary=temporal_cinematic.event_summary,
            semantic_event_directives_text=self._format_semantic_event_directives(timeline),
            occlusion_risks_text=self._format_occlusion_risks(temporal_cinematic),
            reveal_opportunities_text=self._format_reveal_opportunities(temporal_cinematic),
            beats_text=self._format_beats(beats),
        )
        user_prompt += self._append_extra_context(
            replay_description=temporal_cinematic.replay_description,
            style_profile=style_profile,
            style_brief=style_brief,
        )
        return system, user_prompt

    def build_constraint_critique_prompt(
        self,
        shots: list[TemporalShot],
        timeline: SceneTimeline,
        deterministic_checks: dict,
        style_profile: str = "default",
        style_brief: str = "",
        replay_description: str = "",
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the constraint critique pass."""
        system = (self._dir / "temporal_system_prompt.txt").read_text(encoding="utf-8")
        template = (self._dir / "temporal_critique_pass_template.txt").read_text(encoding="utf-8")

        user_prompt = template.format(
            time_start=timeline.time_span.start,
            time_end=timeline.time_span.end,
            duration=timeline.time_span.duration,
            objects_text=self._format_static_objects(timeline),
            shots_text=self._format_shots(shots),
            deterministic_checks_text=self._format_deterministic_checks(deterministic_checks),
        )
        user_prompt += self._append_extra_context(
            replay_description=replay_description,
            style_profile=style_profile,
            style_brief=style_brief,
        )
        return system, user_prompt

    @staticmethod
    def _append_extra_context(
        replay_description: str,
        style_profile: str,
        style_brief: str,
    ) -> str:
        sections: list[str] = []
        replay = (replay_description or "").strip()
        if replay:
            sections.append(f"\n\n### Replay Description (Derived from Unity Timeline)\n{replay}")
        style = (style_brief or "").strip()
        if style:
            sections.append(
                "\n\n### Cinematic Style Guidance\n"
                f"style_profile={style_profile}\n"
                f"{style}"
            )
        return "".join(sections)

    def _format_static_objects(self, timeline: SceneTimeline) -> str:
        lines = []
        for o in timeline.objects_static:
            tags = ", ".join(o.tags) if o.tags else "none"
            lines.append(
                f"- {o.id} ({o.name}): category={o.category}, "
                f"pos=({o.position[0]}, {o.position[1]}, {o.position[2]}), "
                f"importance={o.importance}, tags=[{tags}]"
            )
        # Add tracked object IDs
        for track in timeline.object_tracks:
            if not any(o.id == track.object_id for o in timeline.objects_static):
                lines.append(f"- {track.object_id} (moving): tracked with {len(track.samples)} samples")
        return "\n".join(lines) if lines else "No objects."

    def _format_subject_profiles(self, tc: TemporalCinematicScene) -> str:
        lines = []
        for p in tc.subject_profiles:
            windows = ", ".join(f"[{w[0]:.1f}s-{w[1]:.1f}s]" for w in p.active_windows)
            lines.append(
                f"- {p.object_id}: role={p.role}, salience={p.salience_score:.2f}, "
                f"windows=[{windows}], motion={p.motion_summary}"
            )
        return "\n".join(lines) if lines else "No temporal profiles."

    def _format_spacetime_affordances(self, tc: TemporalCinematicScene) -> str:
        lines = []
        for a in tc.spacetime_affordances:
            objs = ", ".join(a.object_ids)
            lines.append(
                f"- [{a.time_start:.1f}s-{a.time_end:.1f}s] {a.type}: "
                f"{a.description} (objects: {objs}, score={a.score:.2f})"
            )
        return "\n".join(lines) if lines else "No spacetime affordances."

    def _format_occlusion_risks(self, tc: TemporalCinematicScene) -> str:
        lines = []
        for r in tc.occlusion_risks:
            lines.append(
                f"- [{r.time_start:.1f}s-{r.time_end:.1f}s] "
                f"{r.blocker_id} blocks {r.blocked_id} (severity={r.severity:.2f})"
            )
        return "\n".join(lines) if lines else "No occlusion risks detected."

    def _format_reveal_opportunities(self, tc: TemporalCinematicScene) -> str:
        lines = []
        for r in tc.reveal_opportunities:
            lines.append(f"- [{r.time:.1f}s] {r.object_id}: {r.description} (score={r.score:.2f})")
        return "\n".join(lines) if lines else "No reveal opportunities."

    def _format_beats(self, beats: list[Beat]) -> str:
        lines = []
        for b in beats:
            subjects = ", ".join(b.subjects) if b.subjects else "none"
            lines.append(
                f"- {b.beat_id}: [{b.time_start:.1f}s-{b.time_end:.1f}s] "
                f"goal=\"{b.goal}\", mood={b.mood}, subjects=[{subjects}]"
            )
        return "\n".join(lines) if lines else "No beats defined."

    def _format_shots(self, shots: list[TemporalShot]) -> str:
        lines = []
        for s in shots:
            lines.append(
                f"- {s.shot_id}: [{s.time_start:.1f}s-{s.time_end:.1f}s] "
                f"subject={s.subject}, type={s.shot_type}, movement={s.movement}, "
                f"beat={s.beat_id}, transition={s.transition_in}"
            )
        return "\n".join(lines) if lines else "No shots."

    def _format_deterministic_checks(self, checks: dict) -> str:
        lines = []
        for key, value in checks.items():
            if isinstance(value, list):
                for item in value:
                    lines.append(f"- [{key}] {item}")
            elif isinstance(value, dict):
                for sub_key, sub_val in value.items():
                    lines.append(f"- [{key}.{sub_key}] {sub_val}")
            else:
                lines.append(f"- [{key}] {value}")
        return "\n".join(lines) if lines else "All deterministic checks passed."

    def _format_semantic_event_directives(self, timeline: SceneTimeline) -> str:
        semantic_events = timeline.semantic_events or []
        if not semantic_events:
            return "No semantic event directives."
        lines: list[str] = []
        for event in semantic_events:
            subjects = ", ".join(event.object_ids) if event.object_ids else "none"
            lines.append(
                f"- [{event.time_start:.1f}s-{event.time_end:.1f}s] "
                f"{event.label}: role={event.dramatic_role}, subjects=[{subjects}], "
                f"camera_implication=\"{event.camera_implication}\""
            )
        return "\n".join(lines)
