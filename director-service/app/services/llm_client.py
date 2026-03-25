"""LLM client abstraction with mock and OpenAI implementations.

The MockLLMClient reads actual scene data from the prompt, applies template
shot recipes based on intent keywords, and produces structurally valid
DirectingPlan JSON.

The OpenAILLMClient calls the OpenAI Chat Completions API.
"""

from abc import ABC, abstractmethod
import json
import re
import uuid

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_OPENAI_CHAT_MODEL_ALIASES: dict[str, str] = {
    "gpt-5": "gpt-5-chat-latest",
    "gpt-5.1": "gpt-5.1-chat-latest",
    "gpt-5.2": "gpt-5.2-chat-latest",
}

_RECOMMENDED_OPENAI_CHAT_MODELS: list[str] = [
    "gpt-5.2-chat-latest",
    "gpt-5.1-chat-latest",
    "gpt-5-chat-latest",
    "gpt-4.1",
    "gpt-4.1-mini",
    "gpt-4o",
    "gpt-4o-mini",
]


class LLMClient(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        """Return raw LLM response text (expected to be JSON)."""
        ...


class MockLLMClient(LLMClient):
    """Template-based mock that parses the prompt to produce realistic plans."""

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        scene_id = self._extract_scene_id(user_prompt)
        intent = self._extract_intent(user_prompt)
        object_ids = self._extract_object_ids(user_prompt)

        shots = self._build_shots(intent, object_ids)
        total_duration = sum(s["duration"] for s in shots)

        plan = {
            "plan_id": f"plan_{uuid.uuid4().hex[:8]}",
            "scene_id": scene_id,
            "intent": intent,
            "summary": f"A cinematic sequence responding to: {intent}",
            "total_duration": total_duration,
            "shots": shots,
        }
        return json.dumps(plan, indent=2)

    def _extract_scene_id(self, prompt: str) -> str:
        m = re.search(r'scene_id:\s*"([^"]+)"', prompt)
        return m.group(1) if m else "unknown_scene"

    def _extract_intent(self, prompt: str) -> str:
        m = re.search(r"## User Intent\s*\n(.+?)(?:\n##|\Z)", prompt, re.DOTALL)
        return m.group(1).strip() if m else "general overview"

    def _extract_object_ids(self, prompt: str) -> list[str]:
        """Extract object IDs from the Objects section of the prompt."""
        ids: list[str] = []
        m = re.search(r"### Objects\s*\n(.+?)(?:\n###|\Z)", prompt, re.DOTALL)
        if m:
            for line in m.group(1).strip().split("\n"):
                obj_match = re.match(r"- (\w+)\s+\(", line)
                if obj_match:
                    ids.append(obj_match.group(1))
        return ids

    def _build_shots(self, intent: str, object_ids: list[str]) -> list[dict]:
        """Select a shot recipe based on intent keywords."""
        intent_lower = intent.lower()

        if any(kw in intent_lower for kw in ["overview", "preview", "layout", "overall"]):
            return self._overview_recipe(object_ids)
        elif any(kw in intent_lower for kw in ["reveal", "discover", "unveil"]):
            return self._reveal_recipe(object_ids)
        elif any(kw in intent_lower for kw in ["slow", "cinematic", "exploration", "explore"]):
            return self._cinematic_recipe(object_ids)
        elif any(kw in intent_lower for kw in ["focus", "detail", "inspect", "close"]):
            return self._focus_recipe(object_ids)
        else:
            return self._overview_recipe(object_ids)

    def _overview_recipe(self, object_ids: list[str]) -> list[dict]:
        shots = []
        # Shot 1: Establishing wide
        shots.append(self._make_shot(
            idx=1,
            goal="Establish the overall room layout",
            subject="room",
            shot_type="establishing",
            movement="slow_forward",
            duration=4.0,
            pacing="calm",
            constraints={"keep_objects_visible": object_ids[:3], "maintain_room_readability": True},
            rationale="Opening establishing shot to orient the viewer",
        ))
        # Shot 2: Wide pan
        shots.append(self._make_shot(
            idx=2,
            goal="Survey the space from a lateral perspective",
            subject="room",
            shot_type="wide",
            movement="lateral_slide",
            duration=3.5,
            pacing="steady",
            constraints={"preserve_context": True},
            rationale="Lateral movement reveals spatial relationships between objects",
        ))
        # Shot 3: Medium on primary subject
        primary = object_ids[0] if object_ids else "room"
        shots.append(self._make_shot(
            idx=3,
            goal=f"Highlight the main subject: {primary}",
            subject=primary,
            shot_type="medium",
            movement="slow_forward",
            duration=3.0,
            pacing="steady",
            constraints={"end_on_subject": True, "avoid_occlusion": True},
            rationale="Draw attention to the primary subject in the scene",
        ))
        return shots

    def _reveal_recipe(self, object_ids: list[str]) -> list[dict]:
        shots = []
        # Start on a secondary object, then reveal the primary
        secondary = object_ids[1] if len(object_ids) > 1 else (object_ids[0] if object_ids else "room")
        primary = object_ids[0] if object_ids else "room"

        shots.append(self._make_shot(
            idx=1,
            goal=f"Open on {secondary} to build anticipation",
            subject=secondary,
            shot_type="medium",
            movement="static",
            duration=2.5,
            pacing="deliberate",
            constraints={"end_on_subject": True},
            rationale="Start with a secondary element to create contrast for the reveal",
        ))
        shots.append(self._make_shot(
            idx=2,
            goal=f"Transition toward {primary}",
            subject="room",
            shot_type="wide",
            movement="lateral_slide",
            duration=3.0,
            pacing="dramatic",
            constraints={"preserve_context": True},
            rationale="Camera movement builds momentum toward the reveal",
        ))
        shots.append(self._make_shot(
            idx=3,
            goal=f"Reveal {primary}",
            subject=primary,
            shot_type="reveal",
            movement="slow_forward",
            duration=4.0,
            pacing="dramatic",
            constraints={"end_on_subject": True, "avoid_occlusion": True},
            rationale="Final reveal of the primary subject with dramatic pacing",
        ))
        return shots

    def _cinematic_recipe(self, object_ids: list[str]) -> list[dict]:
        shots = []
        shots.append(self._make_shot(
            idx=1,
            goal="Slow establishing shot of the entire space",
            subject="room",
            shot_type="establishing",
            movement="slow_forward",
            duration=5.0,
            pacing="calm",
            constraints={"maintain_room_readability": True, "keep_objects_visible": object_ids[:3]},
            rationale="A long, calm opening sets a contemplative mood",
        ))
        shots.append(self._make_shot(
            idx=2,
            goal="Orbit around the central area",
            subject="room",
            shot_type="wide",
            movement="arc",
            duration=5.0,
            pacing="calm",
            constraints={"preserve_context": True},
            rationale="Orbital movement provides a cinematic exploration feel",
        ))
        if len(object_ids) >= 2:
            shots.append(self._make_shot(
                idx=3,
                goal=f"Close detail on {object_ids[-1]}",
                subject=object_ids[-1],
                shot_type="detail",
                movement="slow_forward",
                duration=3.0,
                pacing="deliberate",
                constraints={"end_on_subject": True},
                rationale="End with an intimate detail to leave a lasting impression",
            ))
        return shots

    def _focus_recipe(self, object_ids: list[str]) -> list[dict]:
        primary = object_ids[0] if object_ids else "room"
        shots = []
        shots.append(self._make_shot(
            idx=1,
            goal=f"Approach {primary} from a distance",
            subject=primary,
            shot_type="wide",
            movement="slow_forward",
            duration=3.0,
            pacing="steady",
            constraints={"avoid_occlusion": True},
            rationale="Start wide and move in to build focus",
        ))
        shots.append(self._make_shot(
            idx=2,
            goal=f"Close-up on {primary}",
            subject=primary,
            shot_type="close_up",
            movement="slow_forward",
            duration=3.5,
            pacing="deliberate",
            constraints={"end_on_subject": True, "avoid_high_angle": True},
            rationale="Tight framing draws the viewer's attention to detail",
        ))
        return shots

    def _make_shot(
        self,
        idx: int,
        goal: str,
        subject: str,
        shot_type: str,
        movement: str,
        duration: float,
        pacing: str,
        constraints: dict | None = None,
        rationale: str = "",
    ) -> dict:
        return {
            "shot_id": f"shot_{idx}",
            "goal": goal,
            "subject": subject,
            "shot_type": shot_type,
            "movement": movement,
            "duration": duration,
            "pacing": pacing,
            "constraints": constraints or {},
            "rationale": rationale,
        }


class OpenAILLMClient(LLMClient):
    """Calls OpenAI Chat Completions API."""

    def __init__(self, model: str | None = None, api_key: str | None = None):
        from openai import OpenAI

        self._model = resolve_openai_chat_model(model or settings.llm_model or "gpt-4o")
        self._client = OpenAI(api_key=api_key or settings.llm_api_key)

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        effective_model = resolve_openai_chat_model(model_override) if model_override else self._model
        logger.info("Calling OpenAI model=%s ...", effective_model)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            response = self._client.chat.completions.create(
                model=effective_model,
                messages=messages,
                temperature=0.7,
                response_format={"type": "json_object"},
            )
        except Exception as first_error:
            logger.warning(
                "Primary chat.completions request failed for model=%s (%s). Retrying with compatible fallback.",
                effective_model,
                first_error,
            )
            response = self._retry_compatible_request(messages, first_error, effective_model)
        content = response.choices[0].message.content or ""
        logger.info(
            "OpenAI response received (%d chars, tokens: %s prompt + %s completion)",
            len(content),
            response.usage.prompt_tokens if response.usage else "?",
            response.usage.completion_tokens if response.usage else "?",
        )
        return content

    def _retry_compatible_request(self, messages: list[dict], first_error: Exception, model: str | None = None):
        effective = model or self._model
        # Retry strategy:
        # 1) Keep JSON response format but remove temperature (some GPT-5 chat models enforce default temp)
        # 2) Remove both response_format and temperature as last compatibility fallback
        try:
            return self._client.chat.completions.create(
                model=effective,
                messages=messages,
                response_format={"type": "json_object"},
            )
        except Exception as second_error:
            logger.warning(
                "Second compatibility retry failed for model=%s (%s). "
                "Retrying without response_format and temperature.",
                effective,
                second_error,
            )
            try:
                return self._client.chat.completions.create(
                    model=effective,
                    messages=messages,
                )
            except Exception:
                # Bubble up the original first error context for easier debugging.
                raise first_error


class MockTemporalLLMClient(LLMClient):
    """Mock LLM client for temporal multi-pass planning.

    Detects the pass type from prompt content and returns valid temporal JSON.
    """

    def generate(self, system_prompt: str, user_prompt: str, model_override: str | None = None) -> str:
        prompt_lower = user_prompt.lower()

        if "style selection task" in prompt_lower or "pre-pass" in prompt_lower:
            return self._style_response(user_prompt)
        if "global beat planning" in prompt_lower or "pass 1 of 3" in prompt_lower:
            return self._beat_response(user_prompt)
        elif "shot intent planning" in prompt_lower or "pass 2 of 3" in prompt_lower:
            return self._shot_response(user_prompt)
        elif "constraint critique" in prompt_lower or "pass 3 of 3" in prompt_lower:
            return self._critique_response(user_prompt)
        else:
            return self._beat_response(user_prompt)

    def _style_response(self, prompt: str) -> str:
        prompt_lower = prompt.lower()
        if any(token in prompt_lower for token in ["f1", "race", "racing", "motorsport", "lap", "overtake"]):
            style_profile = "motorsport_f1"
            style_rationale = "Intent and replay imply fast race-like tracking with broadcast pacing."
            style_notes = "Prioritize readable speed, anticipatory framing, and continuity on the lead subject."
        elif any(token in prompt_lower for token in ["match", "sport", "stadium", "broadcast"]):
            style_profile = "sports_broadcast"
            style_rationale = "Action-oriented coverage benefits from sports broadcast style."
            style_notes = "Keep action centered and maintain contextual continuity."
        elif any(token in prompt_lower for token in ["emotion", "dramatic", "story", "cinematic"]):
            style_profile = "cinematic_drama"
            style_rationale = "Narrative-oriented language suggests dramatic cinematic style."
            style_notes = "Use deliberate reveal and transition pacing."
        else:
            style_profile = "default"
            style_rationale = "No dominant genre signal; default style is safest."
            style_notes = "Keep motion coherent and subject readability high."
        return json.dumps(
            {
                "style_profile": style_profile,
                "style_rationale": style_rationale,
                "style_notes": style_notes,
            },
            indent=2,
        )

    def _beat_response(self, prompt: str) -> str:
        time_start, time_end = self._extract_time_span(prompt)
        duration = time_end - time_start
        subjects = self._extract_subject_ids(prompt)
        mid = time_start + duration / 2

        beats = [
            {
                "beat_id": "beat_1",
                "time_start": time_start,
                "time_end": mid,
                "goal": "Establish the scene and introduce subjects",
                "mood": "calm",
                "subjects": subjects[:2] if subjects else ["room"],
            },
            {
                "beat_id": "beat_2",
                "time_start": mid,
                "time_end": time_end,
                "goal": "Focus on key action and resolve",
                "mood": "dramatic",
                "subjects": subjects[:2] if subjects else ["room"],
            },
        ]
        return json.dumps({"beats": beats}, indent=2)

    def _shot_response(self, prompt: str) -> str:
        time_start, time_end = self._extract_time_span(prompt)
        duration = time_end - time_start
        subjects = self._extract_subject_ids(prompt)
        primary = subjects[0] if subjects else "room"
        third = duration / 3
        is_f1_style = "style_profile=motorsport_f1" in prompt.lower() or "motorsport_f1" in prompt.lower()

        if is_f1_style:
            shots = [
                {
                    "shot_id": "shot_1",
                    "time_start": time_start,
                    "time_end": time_start + third,
                    "goal": "Race-context opener with speed readability",
                    "subject": "room",
                    "shot_type": "wide",
                    "movement": "arc",
                    "pacing": "dramatic",
                    "constraints": {"maintain_room_readability": True},
                    "rationale": "Broadcast-like opener for track context",
                    "transition_in": "cut",
                    "beat_id": "beat_1",
                },
                {
                    "shot_id": "shot_2",
                    "time_start": time_start + third,
                    "time_end": time_start + 2 * third,
                    "goal": f"Primary tracking pass on {primary}",
                    "subject": primary,
                    "shot_type": "medium",
                    "movement": "lateral_slide",
                    "pacing": "dramatic",
                    "constraints": {"avoid_occlusion": True},
                    "rationale": "Lateral race-follow behavior",
                    "transition_in": "smooth",
                    "beat_id": "beat_1",
                },
                {
                    "shot_id": "shot_3",
                    "time_start": time_start + 2 * third,
                    "time_end": time_end,
                    "goal": f"Finish with directional pan on {primary}",
                    "subject": primary,
                    "shot_type": "reveal",
                    "movement": "pan",
                    "pacing": "dramatic",
                    "constraints": {"end_on_subject": True, "avoid_occlusion": True},
                    "rationale": "Broadcast-style finish preserving continuity",
                    "transition_in": "match_cut",
                    "beat_id": "beat_2",
                },
            ]
        else:
            shots = [
                {
                    "shot_id": "shot_1",
                    "time_start": time_start,
                    "time_end": time_start + third,
                    "goal": "Establish the scene layout",
                    "subject": "room",
                    "shot_type": "establishing",
                    "movement": "slow_forward",
                    "pacing": "calm",
                    "constraints": {},
                    "rationale": "Opening establishing shot",
                    "transition_in": "cut",
                    "beat_id": "beat_1",
                },
                {
                    "shot_id": "shot_2",
                    "time_start": time_start + third,
                    "time_end": time_start + 2 * third,
                    "goal": f"Track {primary} movement",
                    "subject": primary,
                    "shot_type": "medium",
                    "movement": "lateral_slide",
                    "pacing": "steady",
                    "constraints": {"avoid_occlusion": True},
                    "rationale": "Follow the primary subject",
                    "transition_in": "smooth",
                    "beat_id": "beat_1",
                },
                {
                    "shot_id": "shot_3",
                    "time_start": time_start + 2 * third,
                    "time_end": time_end,
                    "goal": f"Close on {primary}",
                    "subject": primary,
                    "shot_type": "close_up",
                    "movement": "slow_forward",
                    "pacing": "dramatic",
                    "constraints": {"end_on_subject": True},
                    "rationale": "Dramatic close to emphasize subject",
                    "transition_in": "smooth",
                    "beat_id": "beat_2",
                },
            ]
        return json.dumps({"shots": shots}, indent=2)

    def _critique_response(self, prompt: str) -> str:
        # Parse existing shots from the prompt and return them unchanged
        import re as _re
        m = _re.search(r'"shots"\s*:\s*\[', prompt)
        if m:
            # Try to extract the shots JSON from the prompt
            start = prompt.find("[", m.start())
            if start != -1:
                depth = 0
                for i in range(start, len(prompt)):
                    if prompt[i] == "[":
                        depth += 1
                    elif prompt[i] == "]":
                        depth -= 1
                        if depth == 0:
                            try:
                                shots = json.loads(prompt[start:i + 1])
                                return json.dumps({"shots": shots}, indent=2)
                            except json.JSONDecodeError:
                                break
        # Fallback: return the shot response
        return self._shot_response(prompt)

    def _extract_time_span(self, prompt: str) -> tuple[float, float]:
        import re as _re
        m = _re.search(r"Time Span:\s*([\d.]+)s\s+to\s+([\d.]+)s", prompt)
        if m:
            return float(m.group(1)), float(m.group(2))
        m = _re.search(r"([\d.]+)s\s+to\s+([\d.]+)s", prompt)
        if m:
            return float(m.group(1)), float(m.group(2))
        return 0.0, 10.0

    def _extract_subject_ids(self, prompt: str) -> list[str]:
        import re as _re
        ids: list[str] = []
        for line in prompt.split("\n"):
            m = _re.match(r"- (\w+)\s+\(", line.strip())
            if m:
                obj_id = m.group(1)
                if obj_id not in ("No", "none"):
                    ids.append(obj_id)
        return ids


def create_llm_client(
    provider: str | None = None,
    model: str | None = None,
) -> LLMClient:
    """Factory function for LLM clients."""
    provider = provider or settings.llm_provider
    if provider == "mock":
        return MockLLMClient()
    if provider == "openai":
        return OpenAILLMClient(model=model)
    raise ValueError(f"Unknown LLM provider: {provider}")


def resolve_openai_chat_model(model: str) -> str:
    """Resolve common model aliases to chat-compatible model ids."""
    normalized = (model or "").strip()
    if not normalized:
        return "gpt-4o"
    if normalized in _OPENAI_CHAT_MODEL_ALIASES:
        resolved = _OPENAI_CHAT_MODEL_ALIASES[normalized]
        logger.info("Resolved model alias %s -> %s", normalized, resolved)
        return resolved
    return normalized


def recommended_openai_chat_models() -> list[str]:
    return list(_RECOMMENDED_OPENAI_CHAT_MODELS)
