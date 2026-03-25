"""Multi-pass temporal plan orchestrator.

Runs a 4-step planning flow:
  Style pass: choose cinematic style profile (auto mode)
  Pass 1: Global Beat Planning (intent + abstraction -> beats)
  Pass 2: Shot Intent Planning (beats + constraints -> shots)
  Pass 3: Constraint Critique (deterministic checks + LLM review -> revised shots)
"""

import json
import time
import uuid
from typing import Any

from pydantic import ValidationError

from app.models.scene_timeline import SceneTimeline
from app.models.temporal_cinematic_scene import TemporalCinematicScene
from app.models.temporal_directing_plan import (
    Beat,
    TemporalShot,
    TemporalDirectingPlan,
)
from app.models.temporal_enums import PlanningPassType
from app.models.planning_pass import PlanningPassArtifact
from app.services.cinematic_style import build_style_brief, normalize_style_profile
from app.services.llm_client import LLMClient
from app.services.temporal_prompt_builder import TemporalPromptBuilder
from app.utils.logger import get_logger

logger = get_logger(__name__)


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
    ) -> tuple[TemporalDirectingPlan, list[PlanningPassArtifact], str, str]:
        """Run temporal orchestration and return (plan, artifacts, style_profile, style_rationale)."""
        artifacts: list[PlanningPassArtifact] = []
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
            beats, timeline, temporal_cinematic, active_style, active_style_brief
        )
        artifacts.append(shot_artifact)

        # Between Pass 2 and 3: Deterministic checks
        deterministic_checks = self._run_deterministic_checks(
            shots, timeline
        )

        # Pass 3: Constraint Critique
        revised_shots, critique_artifact = self._run_constraint_critique_pass(
            shots, timeline, deterministic_checks, active_style, active_style_brief, temporal_cinematic.replay_description
        )
        artifacts.append(critique_artifact)

        plan = TemporalDirectingPlan(
            plan_id=f"tplan_{uuid.uuid4().hex[:8]}",
            scene_id=timeline.scene_id,
            intent=intent,
            summary=f"Temporal directing plan for: {intent}",
            time_span=timeline.time_span,
            beats=beats,
            shots=revised_shots,
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
        if requested and requested not in ("auto", "llm", "default"):
            profile, brief = build_style_brief(requested, style_brief)
            artifact = PlanningPassArtifact(
                pass_type=PlanningPassType.style_intent,
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
                pass_type=PlanningPassType.style_intent,
                pass_index=0,
                input_summary=f"auto_style scene={timeline.scene_id}",
                output_raw=raw,
                output_parsed={**data, "style_profile": profile},
                duration_ms=duration_ms,
                success=True,
            )
            return profile, brief, rationale, artifact
        except Exception as e:
            duration_ms = time.time() * 1000 - start_ms
            logger.warning("Style pass failed: %s. Falling back to default style.", e)
            profile, brief = build_style_brief("default", style_brief)
            artifact = PlanningPassArtifact(
                pass_type=PlanningPassType.style_intent,
                pass_index=0,
                input_summary=f"auto_style scene={timeline.scene_id}",
                output_raw=str(e),
                output_parsed={"style_profile": profile, "mode": "fallback_default"},
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
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
        sys_prompt, user_prompt = self._prompt_builder.build_global_beat_prompt(
            timeline, temporal_cinematic, intent, style_profile=style_profile, style_brief=style_brief
        )

        start_ms = time.time() * 1000
        try:
            raw = self._llm.generate(sys_prompt, user_prompt)
            duration_ms = time.time() * 1000 - start_ms
            data = _parse_json(raw)
            beats = _parse_beats(data, timeline)

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

    def _run_shot_intent_pass(
        self,
        beats: list[Beat],
        timeline: SceneTimeline,
        temporal_cinematic: TemporalCinematicScene,
        style_profile: str,
        style_brief: str,
    ) -> tuple[list[TemporalShot], PlanningPassArtifact]:
        """Pass 2: Generate shots from beats + scene constraints."""
        sys_prompt, user_prompt = self._prompt_builder.build_shot_intent_prompt(
            beats, timeline, temporal_cinematic, style_profile=style_profile, style_brief=style_brief
        )

        start_ms = time.time() * 1000
        try:
            raw = self._llm.generate(sys_prompt, user_prompt)
            duration_ms = time.time() * 1000 - start_ms
            data = _parse_json(raw)
            shots = _parse_shots(data, timeline)

            return shots, PlanningPassArtifact(
                pass_type=PlanningPassType.shot_intent,
                pass_index=2,
                input_summary=f"{len(beats)} beats, style={style_profile}",
                output_raw=raw,
                output_parsed=data,
                duration_ms=duration_ms,
                success=True,
            )
        except Exception as e:
            duration_ms = time.time() * 1000 - start_ms
            logger.warning("Shot pass failed: %s. Using 3-shot template fallback.", e)
            fallback_shots = _build_fallback_shots(timeline, beats)
            return fallback_shots, PlanningPassArtifact(
                pass_type=PlanningPassType.shot_intent,
                pass_index=2,
                input_summary=f"{len(beats)} beats, style={style_profile}",
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

        return issues

    def _run_constraint_critique_pass(
        self,
        shots: list[TemporalShot],
        timeline: SceneTimeline,
        deterministic_checks: dict,
        style_profile: str,
        style_brief: str,
        replay_description: str,
    ) -> tuple[list[TemporalShot], PlanningPassArtifact]:
        """Pass 3: LLM reviews + fixes shots based on deterministic checks."""
        # Check if there are any issues
        has_issues = any(
            isinstance(v, list) and len(v) > 0
            for v in deterministic_checks.values()
        )

        if not has_issues:
            # No issues: skip LLM call, return shots as-is
            return shots, PlanningPassArtifact(
                pass_type=PlanningPassType.constraint_critique,
                pass_index=3,
                input_summary="No issues found, skipping critique",
                output_raw="",
                output_parsed={"shots": [s.model_dump(mode="json") for s in shots]},
                duration_ms=0,
                success=True,
            )

        sys_prompt, user_prompt = self._prompt_builder.build_constraint_critique_prompt(
            shots,
            timeline,
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
            revised_shots = _parse_shots(data, timeline)

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
            return shots, PlanningPassArtifact(
                pass_type=PlanningPassType.constraint_critique,
                pass_index=3,
                input_summary=f"{len(shots)} shots",
                output_raw=str(e),
                duration_ms=duration_ms,
                success=False,
                error_message=str(e),
            )


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


_VALID_SHOT_TYPES = {"establishing", "wide", "medium", "close_up", "detail", "reveal"}
_VALID_MOVEMENTS = {"static", "slow_forward", "slow_backward", "lateral_slide", "arc", "pan", "orbit"}
_VALID_PACING = {"calm", "steady", "dramatic", "deliberate"}
_VALID_TRANSITIONS = {"cut", "smooth", "match_cut", "whip"}


def _parse_shots(data: dict, timeline: SceneTimeline) -> list[TemporalShot]:
    """Parse temporal shots from LLM response data."""
    raw_shots = data.get("shots", [])
    if not isinstance(raw_shots, list) or not raw_shots:
        raise ValueError("No shots in response")

    shots: list[TemporalShot] = []
    for raw in raw_shots:
        if not isinstance(raw, dict):
            continue
        shot_type = str(raw.get("shot_type", "wide")).lower()
        if shot_type not in _VALID_SHOT_TYPES:
            shot_type = "wide"
        movement = str(raw.get("movement", "slow_forward")).lower()
        if movement not in _VALID_MOVEMENTS:
            movement = "slow_forward"
        pacing = str(raw.get("pacing", "steady")).lower()
        if pacing not in _VALID_PACING:
            pacing = "steady"
        transition = str(raw.get("transition_in", "cut")).lower()
        if transition not in _VALID_TRANSITIONS:
            transition = "cut"

        shots.append(TemporalShot(
            shot_id=str(raw.get("shot_id", f"shot_{len(shots) + 1}")),
            time_start=float(raw.get("time_start", timeline.time_span.start)),
            time_end=float(raw.get("time_end", timeline.time_span.end)),
            goal=str(raw.get("goal", "")),
            subject=str(raw.get("subject", "room")),
            shot_type=shot_type,
            movement=movement,
            pacing=pacing,
            constraints=raw.get("constraints", {}) if isinstance(raw.get("constraints"), dict) else {},
            rationale=str(raw.get("rationale", "")),
            transition_in=transition,
            beat_id=str(raw.get("beat_id", "")),
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
