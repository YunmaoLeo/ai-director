"""Temporal plan orchestrator.

Runs a 3-pass planning flow:
  Style pass: choose cinematic style profile (auto mode)
  Pass 1: Global Beat Planning (intent + abstraction -> beats)
  Pass 2: Shot Intent Planning (beats + constraints -> shots)

Deterministic checks still run for logging/diagnostics, but they do not rewrite shots.
"""

import json
import time
import uuid
from typing import Any

from app.models.scene_timeline import SceneTimeline
from app.models.temporal_cinematic_scene import TemporalCinematicScene
from app.models.temporal_directing_plan import (
    Beat,
    TemporalShot,
    TemporalDirectingPlan,
    CameraProgramItem,
    CutDecisionItem,
)
from app.models.temporal_enums import PlanningPassType
from app.models.planning_pass import PlanningPassArtifact
from app.services.cinematic_style import build_style_brief, normalize_style_profile
from app.services.llm_client import LLMClient
from app.services.temporal_prompt_builder import TemporalPromptBuilder
from app.utils.logger import get_logger

logger = get_logger(__name__)


def _summarize_intent(intent: str, limit: int = 96) -> str:
    normalized = " ".join((intent or "").split())
    if len(normalized) <= limit:
        return normalized
    return f"{normalized[: limit - 3]}..."


def _summarize_issue_counts(issues: dict[str, Any]) -> tuple[int, str]:
    counts: list[str] = []
    total = 0
    for key, value in issues.items():
        count = len(value) if isinstance(value, list) else 0
        total += count
        counts.append(f"{key}={count}")
    return total, ", ".join(counts)


class TemporalPlanOrchestrator:
    def __init__(
        self,
        llm_client: LLMClient,
        prompt_builder: TemporalPromptBuilder | None = None,
    ):
        self._llm = llm_client
        self._prompt_builder = prompt_builder or TemporalPromptBuilder()

    def orchestrate(
        self,
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        intent: str,
        style_profile: str = "auto",
        style_brief: str = "",
        planning_mode: str = "freeform_llm",
    ) -> tuple[TemporalDirectingPlan, list[PlanningPassArtifact], str, str]:
        """Run temporal orchestration and return (plan, artifacts, style_profile, style_rationale)."""
        artifacts: list[PlanningPassArtifact] = []
        logger.info(
            "Orchestration started for scene_id=%s requested_style=%s planning_mode=%s intent='%s'",
            timeline.scene_id,
            style_profile or "auto",
            planning_mode,
            _summarize_intent(intent),
        )
        active_style, active_style_brief, style_rationale, style_artifact = self._resolve_style(
            timeline,
            temporal_cinematic,
            intent,
            style_profile=style_profile,
            style_brief=style_brief,
        )
        artifacts.append(style_artifact)

        # Pass 1: Global Beat Planning
        beats, beat_artifact = self._run_global_beat_pass(
            timeline, temporal_cinematic, intent, active_style, active_style_brief
        )
        artifacts.append(beat_artifact)

        # Pass 2: Shot Intent Planning
        shots, shot_artifact = self._run_shot_intent_pass(
            beats, timeline, temporal_cinematic, intent, active_style, active_style_brief, planning_mode
        )
        artifacts.append(shot_artifact)

        # Deterministic checks remain diagnostic only and do not rewrite shots.
        deterministic_checks = self._run_deterministic_checks(
            shots, timeline
        )

        logger.info(
            "Constraint critique pass disabled for scene_id=%s; preserving Pass 2 shot output",
            timeline.scene_id,
        )
        revised_shots = shots
        total_issues, issue_summary = _summarize_issue_counts(deterministic_checks)
        critique_artifact = PlanningPassArtifact(
            pass_type=PlanningPassType.constraint_critique,
            pass_index=3,
            input_summary=(
                "Critique pass disabled; deterministic checks are advisory only. "
                f"issues={total_issues} ({issue_summary})"
            ),
            output_raw="",
            output_parsed={
                "enabled": False,
                "deterministic_checks": deterministic_checks,
                "shots": [s.model_dump(mode="json") for s in shots],
            },
            duration_ms=0,
            success=True,
        )
        artifacts.append(critique_artifact)

        plan = TemporalDirectingPlan(
            plan_id=f"tplan_{uuid.uuid4().hex[:8]}",
            scene_id=timeline.scene_id,
            intent=intent,
            summary=f"Temporal directing plan for: {intent}",
            time_span=timeline.time_span,
            director_policy=active_style,
            director_rationale=style_rationale,
            beats=beats,
            shots=revised_shots,
            camera_program=self._build_camera_program(revised_shots),
            edit_decision_list=self._build_edit_decision_list(revised_shots),
        )

        logger.info(
            "Orchestration completed for scene_id=%s plan_id=%s style=%s beats=%d shots=%d",
            timeline.scene_id,
            plan.plan_id,
            active_style,
            len(beats),
            len(revised_shots),
        )

        return plan, artifacts, active_style, style_rationale

    def _resolve_style(
        self,
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        intent: str,
        style_profile: str,
        style_brief: str,
    ) -> tuple[str, str, str, PlanningPassArtifact]:
        requested = (style_profile or "auto").strip().lower()
        logger.info(
            "Pass 0/3 [style] starting for scene_id=%s requested_style=%s",
            timeline.scene_id,
            requested or "auto",
        )
        if requested and requested not in ("auto", "llm", "default"):
            profile, brief = build_style_brief(requested, style_brief)
            artifact = PlanningPassArtifact(
                pass_type=PlanningPassType.director_intent,
                pass_index=0,
                input_summary=f"requested_style={requested}",
                output_raw="",
                output_parsed={
                    "requested_style": requested,
                    "style_profile": profile,
                    "mode": "manual_override",
                },
                duration_ms=0,
                success=True,
            )
            logger.info(
                "Pass 0/3 [style] completed via manual override profile=%s",
                profile,
            )
            return profile, brief, "Manual style override requested by caller.", artifact

        sys_prompt, user_prompt = self._prompt_builder.build_style_intent_prompt(
            timeline, temporal_cinematic, intent
        )
        start_ms = time.time() * 1000
        try:
            raw = self._llm.generate(sys_prompt, user_prompt)
            duration_ms = time.time() * 1000 - start_ms
            data = _parse_json(raw)
            profile = normalize_style_profile(str(data.get("style_profile", "default")))
            rationale = str(data.get("style_rationale", "")).strip()
            llm_notes = str(data.get("style_notes", "")).strip()
            profile, brief = build_style_brief(profile, llm_notes)
            artifact = PlanningPassArtifact(
                pass_type=PlanningPassType.director_intent,
                pass_index=0,
                input_summary=f"auto_style scene={timeline.scene_id}",
                output_raw=raw,
                output_parsed={**data, "style_profile": profile},
                duration_ms=duration_ms,
                success=True,
            )
            logger.info(
                "Pass 0/3 [style] completed in %.0fms profile=%s rationale='%s'",
                duration_ms,
                profile,
                _summarize_intent(rationale, limit=120),
            )
            return profile, brief, rationale, artifact
        except Exception as e:
            duration_ms = time.time() * 1000 - start_ms
            logger.warning("Style pass failed: %s. Falling back to default style.", e)
            profile, brief = build_style_brief("default", style_brief)
            artifact = PlanningPassArtifact(
                pass_type=PlanningPassType.director_intent,
                pass_index=0,
                input_summary=f"auto_style scene={timeline.scene_id}",
                output_raw=str(e),
                output_parsed={"style_profile": profile, "mode": "fallback_default"},
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
            )
            logger.info(
                "Pass 0/3 [style] fell back to default in %.0fms profile=%s",
                duration_ms,
                profile,
            )
            return profile, brief, "Fallback to default style due to style pass failure.", artifact

    def _run_global_beat_pass(
        self,
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        intent: str,
        style_profile: str,
        style_brief: str,
    ) -> tuple[list[Beat], PlanningPassArtifact]:
        """Pass 1: Generate beat timeline from intent + temporal abstraction."""
        logger.info(
            "Pass 1/3 [beat] starting for scene_id=%s style=%s replay_desc_chars=%d",
            timeline.scene_id,
            style_profile,
            len(temporal_cinematic.replay_description),
        )
        sys_prompt, user_prompt = self._prompt_builder.build_global_beat_prompt(
            timeline, temporal_cinematic, intent, style_profile=style_profile, style_brief=style_brief
        )

        start_ms = time.time() * 1000
        try:
            raw = self._llm.generate(sys_prompt, user_prompt)
            duration_ms = time.time() * 1000 - start_ms
            data = _parse_json(raw)
            beats = _parse_beats(data, timeline)
            logger.info(
                "Pass 1/3 [beat] completed in %.0fms beats=%d",
                duration_ms,
                len(beats),
            )

            return beats, PlanningPassArtifact(
                pass_type=PlanningPassType.global_beat,
                pass_index=1,
                input_summary=(
                    f"intent={intent}, scene={timeline.scene_id}, style={style_profile}, "
                    f"replay_desc_chars={len(temporal_cinematic.replay_description)}"
                ),
                output_raw=raw,
                output_parsed=data,
                duration_ms=duration_ms,
                success=True,
            )
        except Exception as e:
            duration_ms = time.time() * 1000 - start_ms
            logger.warning("Beat pass failed: %s. Using single-beat fallback.", e)
            fallback_beats = [Beat(
                beat_id="beat_1",
                time_start=timeline.time_span.start,
                time_end=timeline.time_span.end,
                goal=intent,
                mood="steady",
                subjects=[],
            )]
            return fallback_beats, PlanningPassArtifact(
                pass_type=PlanningPassType.global_beat,
                pass_index=1,
                input_summary=(
                    f"intent={intent}, scene={timeline.scene_id}, style={style_profile}, "
                    f"replay_desc_chars={len(temporal_cinematic.replay_description)}"
                ),
                output_raw=str(e),
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
            )
            logger.info(
                "Pass 1/3 [beat] fell back in %.0fms beats=%d",
                duration_ms,
                len(fallback_beats),
            )

    def _run_shot_intent_pass(
        self,
        beats: list[Beat],
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        intent: str,
        style_profile: str,
        style_brief: str,
        planning_mode: str = "freeform_llm",
    ) -> tuple[list[TemporalShot], PlanningPassArtifact]:
        """Pass 2: Generate shots from beats + scene constraints."""
        logger.info(
            "Pass 2/3 [shot] starting for scene_id=%s beats=%d style=%s planning_mode=%s",
            timeline.scene_id,
            len(beats),
            style_profile,
            planning_mode,
        )
        sys_prompt, user_prompt = self._prompt_builder.build_shot_intent_prompt(
            beats,
            timeline,
            temporal_cinematic,
            intent,
            style_profile=style_profile,
            style_brief=style_brief,
            planning_mode=planning_mode,
        )

        start_ms = time.time() * 1000
        try:
            raw = self._llm.generate(sys_prompt, user_prompt)
            duration_ms = time.time() * 1000 - start_ms
            data = _parse_json(raw)
            shots = _parse_shots(data, timeline)
            logger.info(
                "Pass 2/3 [shot] completed in %.0fms shots=%d",
                duration_ms,
                len(shots),
            )

            return shots, PlanningPassArtifact(
                pass_type=PlanningPassType.shot_intent,
                pass_index=2,
                input_summary=f"{len(beats)} beats, style={style_profile}, planning_mode={planning_mode}",
                output_raw=raw,
                output_parsed=data,
                duration_ms=duration_ms,
                success=True,
            )
        except Exception as e:
            duration_ms = time.time() * 1000 - start_ms
            logger.warning("Shot pass failed: %s. Using 3-shot template fallback.", e)
            fallback_shots = _build_fallback_shots(timeline, beats)
            logger.info(
                "Pass 2/3 [shot] fell back in %.0fms shots=%d",
                duration_ms,
                len(fallback_shots),
            )
            return fallback_shots, PlanningPassArtifact(
                pass_type=PlanningPassType.shot_intent,
                pass_index=2,
                input_summary=f"{len(beats)} beats, style={style_profile}, planning_mode={planning_mode}",
                output_raw=str(e),
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
            )

    def _run_deterministic_checks(
        self,
        shots: list[TemporalShot],
        timeline: SceneTimeline,
    ) -> dict[str, Any]:
        """Run deterministic checks between Pass 2 and 3."""
        logger.info(
            "Deterministic checks starting for scene_id=%s shots=%d",
            timeline.scene_id,
            len(shots),
        )
        issues: dict[str, list[str]] = {
            "time_coverage": [],
            "subject_availability": [],
            "overlap": [],
            "duration_sanity": [],
        }

        valid_ids = {o.id for o in timeline.objects_static}
        valid_ids.update(t.object_id for t in timeline.object_tracks)
        valid_ids.add("room")

        # Time coverage: check for gaps > 1s
        if shots:
            sorted_shots = sorted(shots, key=lambda s: s.time_start)
            if sorted_shots[0].time_start - timeline.time_span.start > 1.0:
                issues["time_coverage"].append(
                    f"Gap at start: scene starts at {timeline.time_span.start}s "
                    f"but first shot starts at {sorted_shots[0].time_start}s"
                )
            for i in range(1, len(sorted_shots)):
                gap = sorted_shots[i].time_start - sorted_shots[i - 1].time_end
                if gap > 1.0:
                    issues["time_coverage"].append(
                        f"Gap of {gap:.1f}s between {sorted_shots[i-1].shot_id} "
                        f"and {sorted_shots[i].shot_id}"
                    )
            if timeline.time_span.end - sorted_shots[-1].time_end > 1.0:
                issues["time_coverage"].append(
                    f"Gap at end: last shot ends at {sorted_shots[-1].time_end}s "
                    f"but scene ends at {timeline.time_span.end}s"
                )

        # Subject availability
        for shot in shots:
            if shot.subject not in valid_ids:
                issues["subject_availability"].append(
                    f"Shot {shot.shot_id} references unknown subject '{shot.subject}'"
                )

        # Overlap detection
        for i in range(len(shots)):
            for j in range(i + 1, len(shots)):
                s1, s2 = shots[i], shots[j]
                if s1.time_start < s2.time_end and s2.time_start < s1.time_end:
                    overlap = min(s1.time_end, s2.time_end) - max(s1.time_start, s2.time_start)
                    if overlap > 0.1:
                        issues["overlap"].append(
                            f"Shots {s1.shot_id} and {s2.shot_id} overlap by {overlap:.1f}s"
                        )

        # Duration sanity
        for shot in shots:
            dur = shot.time_end - shot.time_start
            if dur < 1.5:
                issues["duration_sanity"].append(
                    f"Shot {shot.shot_id} duration {dur:.1f}s is below minimum 1.5s"
                )
            if dur > 30.0:
                issues["duration_sanity"].append(
                    f"Shot {shot.shot_id} duration {dur:.1f}s exceeds 30s"
                )

        total_issues, issue_summary = _summarize_issue_counts(issues)
        logger.info(
            "Deterministic checks completed for scene_id=%s total_issues=%d (%s)",
            timeline.scene_id,
            total_issues,
            issue_summary,
        )
        return issues

    def _run_constraint_critique_pass(
        self,
        shots: list[TemporalShot],
        timeline: SceneTimeline,
        intent: str,
        deterministic_checks: dict,
        style_profile: str,
        style_brief: str,
        replay_description: str,
    ) -> tuple[list[TemporalShot], PlanningPassArtifact]:
        """Pass 3: LLM reviews + fixes shots based on deterministic checks."""
        total_issues, issue_summary = _summarize_issue_counts(deterministic_checks)
        # Check if there are any issues
        has_issues = any(
            isinstance(v, list) and len(v) > 0
            for v in deterministic_checks.values()
        )

        if not has_issues:
            # No issues: skip LLM call, return shots as-is
            logger.info(
                "Pass 3/3 [critique] skipped for scene_id=%s because deterministic checks found no issues",
                timeline.scene_id,
            )
            return shots, PlanningPassArtifact(
                pass_type=PlanningPassType.constraint_critique,
                pass_index=3,
                input_summary="No issues found, skipping critique",
                output_raw="",
                output_parsed={"shots": [s.model_dump(mode="json") for s in shots]},
                duration_ms=0,
                success=True,
            )

        logger.info(
            "Pass 3/3 [critique] starting for scene_id=%s shots=%d issues=%d (%s)",
            timeline.scene_id,
            len(shots),
            total_issues,
            issue_summary,
        )
        sys_prompt, user_prompt = self._prompt_builder.build_constraint_critique_prompt(
            shots,
            timeline,
            intent,
            deterministic_checks,
            style_profile=style_profile,
            style_brief=style_brief,
            replay_description=replay_description,
        )

        start_ms = time.time() * 1000
        try:
            raw = self._llm.generate(sys_prompt, user_prompt)
            duration_ms = time.time() * 1000 - start_ms
            data = _parse_json(raw)
            revised_shots = _parse_shots(data, timeline, baseline_shots=shots)
            logger.info(
                "Pass 3/3 [critique] completed in %.0fms revised_shots=%d",
                duration_ms,
                len(revised_shots),
            )

            return revised_shots, PlanningPassArtifact(
                pass_type=PlanningPassType.constraint_critique,
                pass_index=3,
                input_summary=f"{len(shots)} shots, deterministic checks",
                output_raw=raw,
                output_parsed=data,
                duration_ms=duration_ms,
                success=True,
            )
        except Exception as e:
            duration_ms = time.time() * 1000 - start_ms
            logger.warning("Critique pass failed: %s. Using Pass 2 output.", e)
            logger.info(
                "Pass 3/3 [critique] failed in %.0fms; keeping original shots=%d",
                duration_ms,
                len(shots),
            )
            return shots, PlanningPassArtifact(
                pass_type=PlanningPassType.constraint_critique,
                pass_index=3,
                input_summary=f"{len(shots)} shots",
                output_raw=str(e),
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
            )

    def _build_camera_program(self, shots: list[TemporalShot]) -> list[CameraProgramItem]:
        cameras: list[CameraProgramItem] = []
        for index, shot in enumerate(shots):
            cameras.append(
                CameraProgramItem(
                    camera_id=f"cam_{index + 1}",
                    role="virtual_camera",
                    primary_subject=shot.subject,
                    shot_type_bias=shot.shot_type,
                    movement_bias=shot.movement,
                    notes=shot.goal,
                )
            )
        return cameras

    def _build_edit_decision_list(self, shots: list[TemporalShot]) -> list[CutDecisionItem]:
        edits: list[CutDecisionItem] = []
        previous_camera = ""
        for index, shot in enumerate(shots):
            current_camera = f"cam_{index + 1}"
            edits.append(
                CutDecisionItem(
                    cut_id=f"cut_{index + 1}",
                    timestamp=shot.time_start,
                    from_camera_id=previous_camera,
                    to_camera_id=current_camera,
                    transition=shot.transition_in,
                    reason=shot.goal or f"Switch to {shot.subject}",
                    shot_id=shot.shot_id,
                )
            )
            previous_camera = current_camera
        return edits


def _parse_json(raw: str) -> dict:
    """Parse JSON from LLM response, handling markdown fences."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        import re
        fenced = re.search(r"```json\s*(\{.*\})\s*```", raw, re.DOTALL | re.IGNORECASE)
        if fenced:
            return json.loads(fenced.group(1))
        brace_start = raw.find("{")
        brace_end = raw.rfind("}")
        if brace_start != -1 and brace_end > brace_start:
            return json.loads(raw[brace_start:brace_end + 1])
        raise


def _parse_beats(data: dict, timeline: SceneTimeline) -> list[Beat]:
    """Parse beats from LLM response data."""
    raw_beats = data.get("beats", [])
    if not isinstance(raw_beats, list) or not raw_beats:
        raise ValueError("No beats in response")

    beats: list[Beat] = []
    for raw in raw_beats:
        if not isinstance(raw, dict):
            continue
        beats.append(Beat(
            beat_id=str(raw.get("beat_id", f"beat_{len(beats) + 1}")),
            time_start=float(raw.get("time_start", timeline.time_span.start)),
            time_end=float(raw.get("time_end", timeline.time_span.end)),
            goal=str(raw.get("goal", "")),
            mood=str(raw.get("mood", "neutral")),
            subjects=raw.get("subjects", []) if isinstance(raw.get("subjects"), list) else [],
        ))

    if not beats:
        raise ValueError("No valid beats parsed")
    return beats


_TRANSITION_ALIASES = {
    "hardcut": "hard_cut",
    "hard-cut": "hard_cut",
    "smash_cut": "hard_cut",
    "smash-cut": "hard_cut",
    "flash": "flash_cut",
    "flashcut": "flash_cut",
    "flash-cut": "flash_cut",
    "flicker": "flash_cut",
    "flicker_cut": "flash_cut",
    "flicker-cut": "flash_cut",
    "crossfade": "dissolve",
    "cross_fade": "dissolve",
}


def _normalize_transition(value: str) -> str:
    normalized = value.strip().lower()
    normalized = _TRANSITION_ALIASES.get(normalized, normalized)
    if not normalized:
        return "cut"
    return normalized


def _parse_shots(
    data: dict,
    timeline: SceneTimeline,
    baseline_shots: list[TemporalShot] | None = None,
) -> list[TemporalShot]:
    """Parse temporal shots from LLM response data."""
    raw_shots = data.get("shots", [])
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("No shots in response")

    baseline_by_id = {shot.shot_id: shot for shot in baseline_shots or []}
    shots: list[TemporalShot] = []
    for index, raw in enumerate(raw_shots):
        if not isinstance(raw, dict):
            continue
        baseline = None
        raw_shot_id = raw.get("shot_id")
        if isinstance(raw_shot_id, str):
            baseline = baseline_by_id.get(raw_shot_id)
        if baseline is None and baseline_shots and index < len(baseline_shots):
            baseline = baseline_shots[index]

        shot_type = str(
            raw.get("shot_type")
            if raw.get("shot_type") is not None
            else (baseline.shot_type if baseline else "wide")
        ).lower()

        movement = str(
            raw.get("movement")
            if raw.get("movement") is not None
            else (baseline.movement if baseline else "slow_forward")
        ).lower()

        pacing = str(
            raw.get("pacing")
            if raw.get("pacing") is not None
            else (baseline.pacing if baseline else "steady")
        ).lower()

        transition_source = raw.get("transition_in")
        if transition_source is None and baseline is not None:
            transition_source = baseline.transition_in
        transition = _normalize_transition(str(transition_source or "cut"))

        constraints = raw.get("constraints")
        if not isinstance(constraints, dict):
            constraints = dict(baseline.constraints) if baseline else {}

        shot_id = str(raw.get("shot_id") or (baseline.shot_id if baseline else f"shot_{len(shots) + 1}"))
        time_start = float(raw.get("time_start", baseline.time_start if baseline else timeline.time_span.start))
        time_end = float(raw.get("time_end", baseline.time_end if baseline else timeline.time_span.end))
        goal = str(raw.get("goal") if raw.get("goal") is not None else (baseline.goal if baseline else ""))
        subject = str(raw.get("subject") if raw.get("subject") is not None else (baseline.subject if baseline else "room"))
        rationale = str(raw.get("rationale") if raw.get("rationale") is not None else (baseline.rationale if baseline else ""))
        beat_id = str(raw.get("beat_id") if raw.get("beat_id") is not None else (baseline.beat_id if baseline else ""))

        shots.append(TemporalShot(
            shot_id=shot_id,
            time_start=time_start,
            time_end=time_end,
            goal=goal,
            subject=subject,
            shot_type=shot_type,
            movement=movement,
            pacing=pacing,
            constraints=constraints,
            rationale=rationale,
            transition_in=transition,
            beat_id=beat_id,
        ))

    if not shots:
        raise ValueError("No valid shots parsed")
    return shots


def _build_fallback_shots(
    timeline: SceneTimeline,
    beats: list[Beat],
) -> list[TemporalShot]:
    """Build a safe 3-shot fallback template."""
    t0 = timeline.time_span.start
    t1 = timeline.time_span.end
    dur = t1 - t0
    third = dur / 3

    subject = "room"
    for track in timeline.object_tracks:
        subject = track.object_id
        break
    for obj in timeline.objects_static:
        if obj.importance >= 0.6:
            subject = obj.id
            break

    beat_id = beats[0].beat_id if beats else ""

    return [
        TemporalShot(
            shot_id="shot_1",
            time_start=t0,
            time_end=t0 + third,
            goal="Establish the scene",
            subject="room",
            shot_type="establishing",
            movement="slow_forward",
            pacing="calm",
            rationale="Fallback establishing shot",
            transition_in="cut",
            beat_id=beat_id,
        ),
        TemporalShot(
            shot_id="shot_2",
            time_start=t0 + third,
            time_end=t0 + 2 * third,
            goal=f"Follow {subject}",
            subject=subject,
            shot_type="medium",
            movement="lateral_slide",
            pacing="steady",
            rationale="Fallback tracking shot",
            transition_in="smooth",
            beat_id=beats[min(1, len(beats) - 1)].beat_id if beats else "",
        ),
        TemporalShot(
            shot_id="shot_3",
            time_start=t0 + 2 * third,
            time_end=t1,
            goal=f"Close on {subject}",
            subject=subject,
            shot_type="close_up",
            movement="slow_forward",
            pacing="dramatic",
            rationale="Fallback closing shot",
            transition_in="smooth",
            beat_id=beats[-1].beat_id if beats else "",
        ),
    ]
