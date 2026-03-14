from app.services.scene_abstraction import SceneAbstractor
from app.services.affordance_analyzer import AffordanceAnalyzer
from app.models.scene_summary import SceneSummary


def test_abstract_produces_regions(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    cinematic = abstractor.abstract(apartment_scene)
    assert len(cinematic.semantic_regions) > 0


def test_abstract_produces_subjects(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    cinematic = abstractor.abstract(apartment_scene)
    assert len(cinematic.primary_subjects) > 0
    assert len(cinematic.secondary_subjects) >= 0


def test_abstract_produces_spatial_summary(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    cinematic = abstractor.abstract(apartment_scene)
    assert "Apartment Living Room" in cinematic.spatial_summary


def test_abstract_produces_visibility_hints(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    cinematic = abstractor.abstract(apartment_scene)
    assert len(cinematic.visibility_hints) == len(apartment_scene.objects)


def test_abstract_produces_framing_hints(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    cinematic = abstractor.abstract(apartment_scene)
    assert len(cinematic.framing_hints) == len(apartment_scene.objects)


def test_affordances_populated(apartment_scene: SceneSummary):
    abstractor = SceneAbstractor()
    analyzer = AffordanceAnalyzer()
    cinematic = abstractor.abstract(apartment_scene)
    cinematic = analyzer.analyze(apartment_scene, cinematic)
    assert len(cinematic.cinematic_affordances) > 0


def test_works_for_all_scenes(apartment_scene, office_scene, corridor_scene):
    abstractor = SceneAbstractor()
    analyzer = AffordanceAnalyzer()
    for scene in [apartment_scene, office_scene, corridor_scene]:
        cinematic = abstractor.abstract(scene)
        cinematic = analyzer.analyze(scene, cinematic)
        assert len(cinematic.semantic_regions) > 0
        assert len(cinematic.cinematic_affordances) > 0
