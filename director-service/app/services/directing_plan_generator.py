"""Generates a DirectingPlan by calling the LLM and parsing the response."""

import json

from app.models.scene_summary import SceneSummary
from app.models.cinematic_scene import CinematicScene
from app.models.directing_plan import DirectingPlan
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
            logger.error("Failed to parse LLM response as JSON: %s", e)
            raise ValueError(f"LLM returned invalid JSON: {e}") from e

        plan = DirectingPlan.model_validate(data)
        logger.info(
            "Directing plan generated: %d shots, %.1fs total",
            len(plan.shots),
            plan.total_duration,
        )
        return plan
