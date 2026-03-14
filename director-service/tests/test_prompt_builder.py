from app.services.scene_abstraction import SceneAbstractor
from app.services.affordance_analyzer import AffordanceAnalyzer
from app.services.prompt_builder import PromptBuilder
from app.models.scene_summary import SceneSummary


def test_prompt_contains_intent(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    analyzer = AffordanceAnalyzer()
    cinematic = abstractor.abstract(apartment_scene)
    cinematic = analyzer.analyze(apartment_scene, cinematic)

    builder = PromptBuilder()
    system, user = builder.build(apartment_scene, cinematic, "Show me the room")

    assert "Show me the room" in user


def test_prompt_contains_scene_data(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    analyzer = AffordanceAnalyzer()
    cinematic = abstractor.abstract(apartment_scene)
    cinematic = analyzer.analyze(apartment_scene, cinematic)

    builder = PromptBuilder()
    system, user = builder.build(apartment_scene, cinematic, "overview")

    assert "apartment_living_room" in user
    assert "sofa" in user
    assert "desk" in user


def test_system_prompt_has_output_rules(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    cinematic = abstractor.abstract(apartment_scene)

    builder = PromptBuilder()
    system, user = builder.build(apartment_scene, cinematic, "overview")

    assert "JSON" in system
    assert "shot_type" in system


def test_prompt_includes_regions_and_affordances(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    analyzer = AffordanceAnalyzer()
    cinematic = abstractor.abstract(apartment_scene)
    cinematic = analyzer.analyze(apartment_scene, cinematic)

    builder = PromptBuilder()
    _, user = builder.build(apartment_scene, cinematic, "overview")

    assert "Semantic Regions" in user
    assert "Cinematic Affordances" in user
