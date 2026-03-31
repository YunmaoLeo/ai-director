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
        system = self._load_system_prompt()
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
            objects_text=self._format_static_objects(timeline, max_items=5),
            subject_profiles_text=self._format_subject_profiles(temporal_cinematic, max_profiles=4),
            event_summary=self._format_event_summary(temporal_cinematic.event_summary, max_lines=10),
            spacetime_affordances_text=self._format_spacetime_affordances(
                temporal_cinematic,
                max_items=4,
            ),
            intent=intent,
        )
        user_prompt += self._append_extra_context(
            replay_description=temporal_cinematic.replay_description,
            style_profile=style_profile,
            style_brief=style_brief,
            include_replay=False,
        )
        return system, user_prompt

    def build_style_intent_prompt(
        self,
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        intent: str,
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for style selection pre-pass."""
        system = self._load_system_prompt()
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
        intent: str,
        style_profile: str = "default",
        style_brief: str = "",
        planning_mode: str = "freeform_llm",
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the shot intent pass."""
        system = self._load_system_prompt(planning_mode)
        template_name = (
            "temporal_shot_pass_dsl_template.txt"
            if (planning_mode or "").strip().lower() == "camera_dsl"
            else "temporal_shot_pass_template.txt"
        )
        template = (self._dir / template_name).read_text(encoding="utf-8")

        user_prompt = template.format(
            scene_name=timeline.scene_name,
            scene_type=timeline.scene_type,
            width=timeline.bounds.width,
            length=timeline.bounds.length,
            height=timeline.bounds.height,
            time_start=timeline.time_span.start,
            time_end=timeline.time_span.end,
            duration=timeline.time_span.duration,
            objects_text=self._format_static_objects(timeline, max_items=4),
            subject_profiles_text=self._format_subject_profiles(temporal_cinematic, max_profiles=3),
            event_summary=self._format_event_summary(temporal_cinematic.event_summary, max_lines=12),
            semantic_event_directives_text=self._format_semantic_event_directives(timeline, max_items=6),
            occlusion_risks_text=self._format_occlusion_risks(temporal_cinematic, max_items=4),
            reveal_opportunities_text=self._format_reveal_opportunities(temporal_cinematic, max_items=4),
            beats_text=self._format_beats(beats),
            intent=intent,
            camera_dsl_catalog_text=self._format_camera_dsl_catalog(),
        )
        user_prompt += self._append_extra_context(
            replay_description=temporal_cinematic.replay_description,
            style_profile=style_profile,
            style_brief=style_brief,
            include_replay=False,
        )
        return system, user_prompt

    def build_constraint_critique_prompt(
        self,
        shots: list[TemporalShot],
        timeline: SceneTimeline,
        intent: str,
        deterministic_checks: dict,
        style_profile: str = "default",
        style_brief: str = "",
        replay_description: str = "",
    ) -> tuple[str, str]:
        """Return (system_prompt, user_prompt) for the constraint critique pass."""
        system = self._load_system_prompt()
        template = (self._dir / "temporal_critique_pass_template.txt").read_text(encoding="utf-8")

        user_prompt = template.format(
            time_start=timeline.time_span.start,
            time_end=timeline.time_span.end,
            duration=timeline.time_span.duration,
            objects_text=self._format_static_objects(timeline, max_items=4),
            shots_text=self._format_shots(shots),
            deterministic_checks_text=self._format_deterministic_checks(deterministic_checks),
            intent=intent,
        )
        user_prompt += self._append_extra_context(
            replay_description=replay_description,
            style_profile=style_profile,
            style_brief=style_brief,
            include_replay=False,
        )
        return system, user_prompt

    def _load_system_prompt(self, planning_mode: str = "freeform_llm") -> str:
        prompt_name = (
            "temporal_system_prompt_dsl.txt"
            if (planning_mode or "").strip().lower() == "camera_dsl"
            else "temporal_system_prompt.txt"
        )
        return (self._dir / prompt_name).read_text(encoding="utf-8")

    @staticmethod
    def _append_extra_context(
        replay_description: str,
        style_profile: str,
        style_brief: str,
        include_replay: bool = True,
    ) -> str:
        sections: list[str] = []
        replay = (replay_description or "").strip()
        if include_replay and replay:
            sections.append(f"\n\n### Replay Description (Derived from Unity Timeline)\n{replay}")
        style = (style_brief or "").strip()
        if style:
            sections.append(
                "\n\n### Cinematic Style Guidance\n"
                f"style_profile={style_profile}\n"
                f"{style}"
        )
        return "".join(sections)

    def _format_static_objects(self, timeline: SceneTimeline, max_items: int = 6) -> str:
        tracked_ids = {track.object_id for track in timeline.object_tracks}
        salient_categories = {"vehicle", "car", "person", "character", "actor"}
        ranked_objects = sorted(
            timeline.objects_static,
            key=lambda obj: (
                obj.id in tracked_ids,
                obj.category.lower() in salient_categories,
                obj.importance,
                obj.name.lower(),
            ),
            reverse=True,
        )
        lines = []
        for o in ranked_objects[:max_items]:
            tags = ", ".join(o.tags) if o.tags else "none"
            lines.append(
                f"- {o.id} ({o.name}): category={o.category}, "
                f"tracked={'yes' if o.id in tracked_ids else 'no'}, "
                f"pos=({o.position[0]}, {o.position[1]}, {o.position[2]}), "
                f"importance={o.importance}, tags=[{tags}]"
            )
        omitted_objects = len(ranked_objects) - len(lines)
        if omitted_objects > 0:
            lines.append(f"- +{omitted_objects} lower-priority static objects omitted")
        # Add tracked object IDs
        for track in timeline.object_tracks:
            if not any(o.id == track.object_id for o in timeline.objects_static):
                lines.append(f"- {track.object_id} (moving): tracked with {len(track.samples)} samples")
        return "\n".join(lines) if lines else "No objects."

    def _format_subject_profiles(self, tc: TemporalCinematicScene, max_profiles: int = 4) -> str:
        profiles = sorted(
            tc.subject_profiles,
            key=lambda profile: (-profile.salience_score, profile.object_id),
        )
        lines = []
        for p in profiles[:max_profiles]:
            windows = ", ".join(f"[{w[0]:.1f}s-{w[1]:.1f}s]" for w in p.active_windows)
            lines.append(
                f"- {p.object_id}: role={p.role}, salience={p.salience_score:.2f}, "
                f"windows=[{windows}], motion={p.motion_summary}"
            )
        omitted = len(profiles) - len(lines)
        if omitted > 0:
            lines.append(f"- +{omitted} lower-salience subjects omitted")
        return "\n".join(lines) if lines else "No temporal profiles."

    def _format_spacetime_affordances(
        self,
        tc: TemporalCinematicScene,
        max_items: int = 4,
    ) -> str:
        affordances = [
            affordance for affordance in tc.spacetime_affordances
            if affordance.type != "camera_opportunity" or affordance.score >= 0.75
        ]
        if not affordances:
            affordances = list(tc.spacetime_affordances)
        ranked_affordances = sorted(
            affordances,
            key=lambda affordance: (
                affordance.type != "interaction_moment",
                -affordance.score,
                affordance.time_start,
            ),
        )
        lines = []
        for a in ranked_affordances[:max_items]:
            objs = ", ".join(a.object_ids)
            lines.append(
                f"- [{a.time_start:.1f}s-{a.time_end:.1f}s] {a.type}: "
                f"{a.description} (objects: {objs}, score={a.score:.2f})"
            )
        omitted = len(ranked_affordances) - len(lines)
        if omitted > 0:
            lines.append(f"- +{omitted} lower-value spacetime affordances omitted")
        return "\n".join(lines) if lines else "No spacetime affordances."

    def _format_occlusion_risks(
        self,
        tc: TemporalCinematicScene,
        max_items: int = 4,
    ) -> str:
        risks = sorted(
            tc.occlusion_risks,
            key=lambda risk: (-risk.severity, risk.time_start, risk.blocked_id),
        )
        lines = []
        for r in risks[:max_items]:
            lines.append(
                f"- [{r.time_start:.1f}s-{r.time_end:.1f}s] "
                f"{r.blocker_id} blocks {r.blocked_id} (severity={r.severity:.2f})"
            )
        omitted = len(risks) - len(lines)
        if omitted > 0:
            lines.append(f"- +{omitted} lower-severity occlusion windows omitted")
        return "\n".join(lines) if lines else "No occlusion risks detected."

    def _format_reveal_opportunities(
        self,
        tc: TemporalCinematicScene,
        max_items: int = 4,
    ) -> str:
        opportunities = sorted(
            tc.reveal_opportunities,
            key=lambda opportunity: (-opportunity.score, opportunity.time, opportunity.object_id),
        )
        lines = []
        for r in opportunities[:max_items]:
            lines.append(f"- [{r.time:.1f}s] {r.object_id}: {r.description} (score={r.score:.2f})")
        omitted = len(opportunities) - len(lines)
        if omitted > 0:
            lines.append(f"- +{omitted} lower-value reveal opportunities omitted")
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

    def _format_semantic_event_directives(
        self,
        timeline: SceneTimeline,
        max_items: int = 6,
    ) -> str:
        semantic_events = timeline.semantic_events or []
        if not semantic_events:
            return "No semantic event directives."
        ranked_events = sorted(
            semantic_events,
            key=lambda event: (-event.salience, event.time_start, event.semantic_id),
        )
        lines: list[str] = []
        for event in sorted(ranked_events[:max_items], key=lambda item: item.time_start):
            subjects = ", ".join(event.object_ids) if event.object_ids else "none"
            lines.append(
                f"- [{event.time_start:.1f}s-{event.time_end:.1f}s] "
                f"{event.label}: role={event.dramatic_role}, subjects=[{subjects}], "
                f"camera_implication=\"{event.camera_implication}\""
            )
        omitted = len(ranked_events) - len(lines)
        if omitted > 0:
            lines.append(f"- +{omitted} lower-salience semantic directives omitted")
        return "\n".join(lines)

    @staticmethod
    def _format_event_summary(event_summary: str, max_lines: int = 10) -> str:
        lines = [line for line in (event_summary or "").splitlines() if line.strip()]
        if not lines:
            return "No notable events in this timeline."
        if len(lines) <= max_lines:
            return "\n".join(lines)
        kept = lines[:max_lines]
        kept.append(f"... ({len(lines) - max_lines} additional summary lines omitted)")
        return "\n".join(kept)

    def _format_camera_dsl_catalog(self) -> str:
        path = self._dir / "temporal_camera_dsl_catalog.txt"
        if not path.exists():
            return "No camera DSL catalog available."
        return path.read_text(encoding="utf-8").strip()
