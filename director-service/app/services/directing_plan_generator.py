"""Generates a DirectingPlan by calling the LLM and parsing the response."""

import json
import re
import uuid
from typing import Any

from pydantic import ValidationError
from app.models.scene_summary import SceneSummary
from app.models.cinematic_scene import CinematicScene
from app.models.directing_plan import DirectingPlan
from app.models.enums import ShotType, Movement, Pacing
from app.services.llm_client import LLMClient
from app.services.prompt_builder import PromptBuilder
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DirectingPlanGenerator:
    def __init__(self, llm_client: LLMClient, prompt_builder: PromptBuilder | None = None):
        self._llm = llm_client
        self._prompt_builder = prompt_builder or PromptBuilder()

    def generate(
        self,
        scene: SceneSummary,
        cinematic: CinematicScene,
        intent: str,
    ) -> DirectingPlan:
        system_prompt, user_prompt = self._prompt_builder.build(scene, cinematic, intent)
        logger.info("Calling LLM for directing plan generation...")
        raw_response = self._llm.generate(system_prompt, user_prompt)
        logger.debug("LLM response received (%d chars)", len(raw_response))

        # Parse JSON response
        try:
            data = json.loads(raw_response)
        except json.JSONDecodeError as e:
            extracted = _extract_json_from_text(raw_response)
            if extracted is None:
                logger.error("Failed to parse LLM response as JSON: %s", e)
                raise ValueError(f"LLM returned invalid JSON: {e}") from e
            try:
                data = json.loads(extracted)
            except json.JSONDecodeError as second_error:
                logger.error("Failed to parse extracted JSON from LLM response: %s", second_error)
                raise ValueError(f"LLM returned invalid JSON after extraction: {second_error}") from second_error

        normalized = _normalize_plan_data(data, scene, intent)
        try:
            plan = DirectingPlan.model_validate(normalized)
        except ValidationError as e:
            logger.warning("Directing plan validation failed after normalization: %s. Falling back to safe template.", e)
            fallback = _build_fallback_plan(scene, intent)
            plan = DirectingPlan.model_validate(fallback)
        logger.info(
            "Directing plan generated: %d shots, %.1fs total",
            len(plan.shots),
            plan.total_duration,
        )
        return plan


def _extract_json_from_text(text: str) -> str | None:
    if not text:
        return None

    fenced = re.search(r"```json\s*(\{.*\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fenced:
        return fenced.group(1)

    brace_start = text.find("{")
    brace_end = text.rfind("}")
    if brace_start != -1 and brace_end != -1 and brace_end > brace_start:
        return text[brace_start:brace_end + 1]
    return None


_VALID_SHOT_TYPES = {item.value for item in ShotType}
_VALID_MOVEMENTS = {item.value for item in Movement}
_VALID_PACING = {item.value for item in Pacing}

_SHOT_ALIASES = {
    "establish": "establishing",
    "establishing_shot": "establishing",
    "closeup": "close_up",
    "close-up": "close_up",
    "cu": "close_up",
}

_MOVEMENT_ALIASES = {
    "dolly_in": "slow_forward",
    "push_in": "slow_forward",
    "forward": "slow_forward",
    "dolly_out": "slow_backward",
    "pull_back": "slow_backward",
    "backward": "slow_backward",
    "slide": "lateral_slide",
    "truck": "lateral_slide",
    "orbiting": "orbit",
}

_PACING_ALIASES = {
    "slow": "calm",
    "fast": "dramatic",
    "dynamic": "dramatic",
    "normal": "steady",
}


def _normalize_plan_data(data: Any, scene: SceneSummary, intent: str) -> dict[str, Any]:
    if not isinstance(data, dict):
        return _build_fallback_plan(scene, intent)

    shots = data.get("shots")
    if not isinstance(shots, list) or len(shots) == 0:
        return _build_fallback_plan(scene, intent)

    normalized_shots: list[dict[str, Any]] = []
    total_duration = 0.0

    for index, raw_shot in enumerate(shots):
        if not isinstance(raw_shot, dict):
            continue
        shot_id = str(raw_shot.get("shot_id") or f"shot_{index + 1}")
        goal = str(raw_shot.get("goal") or f"Shot {index + 1}")
        subject = str(raw_shot.get("subject") or "room")
        shot_type = _normalize_enum(raw_shot.get("shot_type"), _VALID_SHOT_TYPES, _SHOT_ALIASES, "wide")
        movement = _normalize_enum(raw_shot.get("movement"), _VALID_MOVEMENTS, _MOVEMENT_ALIASES, "slow_forward")
        pacing = _normalize_enum(raw_shot.get("pacing"), _VALID_PACING, _PACING_ALIASES, "steady")
        duration = _safe_float(raw_shot.get("duration"), default=3.0, min_value=0.8, max_value=12.0)
        total_duration += duration
        constraints = raw_shot.get("constraints") if isinstance(raw_shot.get("constraints"), dict) else {}
        rationale = str(raw_shot.get("rationale") or "")

        normalized_shots.append(
            {
                "shot_id": shot_id,
                "goal": goal,
                "subject": subject,
                "shot_type": shot_type,
                "movement": movement,
                "duration": duration,
                "pacing": pacing,
                "constraints": constraints,
                "rationale": rationale,
            }
        )

    if not normalized_shots:
        return _build_fallback_plan(scene, intent)

    return {
        "plan_id": str(data.get("plan_id") or f"plan_{uuid.uuid4().hex[:8]}"),
        "scene_id": str(data.get("scene_id") or scene.scene_id),
        "intent": str(data.get("intent") or intent),
        "summary": str(data.get("summary") or f"A cinematic plan for: {intent}"),
        "total_duration": _safe_float(data.get("total_duration"), default=total_duration, min_value=1.0, max_value=120.0),
        "shots": normalized_shots,
    }


def _normalize_enum(value: Any, valid_values: set[str], aliases: dict[str, str], default: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in valid_values:
        return normalized
    alias = aliases.get(normalized)
    if alias in valid_values:
        return alias
    return default


def _safe_float(value: Any, default: float, min_value: float, max_value: float) -> float:
    try:
        cast = float(value)
    except (TypeError, ValueError):
        return default
    return max(min_value, min(max_value, cast))


def _build_fallback_plan(scene: SceneSummary, intent: str) -> dict[str, Any]:
    return {
        "plan_id": f"plan_{uuid.uuid4().hex[:8]}",
        "scene_id": scene.scene_id,
        "intent": intent,
        "summary": f"Fallback cinematic plan for: {intent}",
        "total_duration": 9.0,
        "shots": [
            {
                "shot_id": "shot_1",
                "goal": "Establish the room layout",
                "subject": "room",
                "shot_type": "establishing",
                "movement": "slow_forward",
                "duration": 3.5,
                "pacing": "calm",
                "constraints": {"maintain_room_readability": True},
                "rationale": "Fallback establishing shot.",
            },
            {
                "shot_id": "shot_2",
                "goal": "Explore the main area",
                "subject": "room",
                "shot_type": "wide",
                "movement": "lateral_slide",
                "duration": 3.0,
                "pacing": "steady",
                "constraints": {"preserve_context": True},
                "rationale": "Fallback movement shot.",
            },
            {
                "shot_id": "shot_3",
                "goal": "End on a stronger composition",
                "subject": "room",
                "shot_type": "medium",
                "movement": "slow_forward",
                "duration": 2.5,
                "pacing": "deliberate",
                "constraints": {"end_on_subject": True},
                "rationale": "Fallback closing shot.",
            },
        ],
    }
