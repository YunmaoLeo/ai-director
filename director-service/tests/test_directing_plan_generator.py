from app.services.directing_plan_generator import DirectingPlanGenerator
from app.services.scene_abstraction import SceneAbstractor
from app.services.affordance_analyzer import AffordanceAnalyzer
from app.services.llm_client import LLMClient


class _FakeLLM(LLMClient):
    def __init__(self, payload: str):
        self._payload = payload

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        return self._payload


def test_generator_normalizes_nonstandard_enums(apartment_scene):
    payload = """
    {
      "plan_id": "p1",
      "scene_id": "apartment_living_room",
      "intent": "test",
      "summary": "test summary",
      "total_duration": 9.5,
      "shots": [
        {
          "shot_id": "shot_1",
          "goal": "Start quickly",
          "subject": "room",
          "shot_type": "establish",
          "movement": "push_in",
          "duration": 3.0,
          "pacing": "fast"
        }
      ]
    }
    """
    generator = DirectingPlanGenerator(_FakeLLM(payload))
    abstractor = SceneAbstractor()
    affordance = AffordanceAnalyzer()
    cinematic = affordance.analyze(apartment_scene, abstractor.abstract(apartment_scene))
    plan = generator.generate(apartment_scene, cinematic=cinematic, intent="test")
    assert plan.shots[0].shot_type.value == "establishing"
    assert plan.shots[0].movement.value == "slow_forward"
    assert plan.shots[0].pacing.value == "dramatic"
