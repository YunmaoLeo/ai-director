import tempfile
from pathlib import Path

from app.pipelines.generate_plan_pipeline import GeneratePlanPipeline


def test_pipeline_apartment_overview():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GeneratePlanPipeline(
            llm_provider="mock",
            output_dir=tmpdir,
        )
        result = pipeline.run("scenes/apartment_living_room.json", "Give me an overview of this room")

        assert len(result.directing_plan.shots) >= 2
        assert len(result.trajectory_plan.trajectories) == len(result.directing_plan.shots)
        assert result.validation_report.is_valid

        # Check files were saved
        output_files = list(Path(tmpdir).glob("*.json"))
        assert len(output_files) == 3


def test_pipeline_reveal_intent():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GeneratePlanPipeline(llm_provider="mock", output_dir=tmpdir)
        result = pipeline.run("scenes/apartment_living_room.json", "Reveal the window after focusing on the desk")

        assert result.validation_report.is_valid
        # Reveal recipe should produce a reveal shot type
        shot_types = [s.shot_type.value for s in result.directing_plan.shots]
        assert "reveal" in shot_types


def test_pipeline_cinematic_intent():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GeneratePlanPipeline(llm_provider="mock", output_dir=tmpdir)
        result = pipeline.run(
            "scenes/apartment_living_room.json",
            "Create a slow cinematic exploration of the room",
        )

        assert result.validation_report.is_valid
        assert result.directing_plan.total_duration >= 10.0


def test_pipeline_office_scene():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GeneratePlanPipeline(llm_provider="mock", output_dir=tmpdir)
        result = pipeline.run("scenes/office_room.json", "Show me this office")

        assert result.validation_report.is_valid
        assert result.directing_plan.scene_id == "office_room"


def test_pipeline_corridor_scene():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GeneratePlanPipeline(llm_provider="mock", output_dir=tmpdir)
        result = pipeline.run("scenes/corridor_scene.json", "Walk through the corridor")

        assert result.validation_report.is_valid


def test_pipeline_focus_intent():
    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GeneratePlanPipeline(llm_provider="mock", output_dir=tmpdir)
        result = pipeline.run("scenes/apartment_living_room.json", "Focus on the sofa in detail")

        assert result.validation_report.is_valid
        shot_types = [s.shot_type.value for s in result.directing_plan.shots]
        assert "close_up" in shot_types
