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


class LLMClient(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Return raw LLM response text (expected to be JSON)."""
        ...


class MockLLMClient(LLMClient):
    """Template-based mock that parses the prompt to produce realistic plans."""

    def generate(self, system_prompt: str, user_prompt: str) -> str:
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

        self._model = model or settings.llm_model or "gpt-4o"
        self._client = OpenAI(api_key=api_key or settings.llm_api_key)

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        logger.info("Calling OpenAI model=%s ...", self._model)
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.7,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or ""
        logger.info(
            "OpenAI response received (%d chars, tokens: %s prompt + %s completion)",
            len(content),
            response.usage.prompt_tokens if response.usage else "?",
            response.usage.completion_tokens if response.usage else "?",
        )
        return content


def create_llm_client(provider: str | None = None) -> LLMClient:
    """Factory function for LLM clients."""
    provider = provider or settings.llm_provider
    if provider == "mock":
        return MockLLMClient()
    if provider == "openai":
        return OpenAILLMClient()
    raise ValueError(f"Unknown LLM provider: {provider}")
