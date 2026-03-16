import os
import tempfile
from pathlib import Path

import pytest

from app.pipelines.generate_plan_pipeline import GeneratePlanPipeline


@pytest.mark.skipif(
    os.getenv("RUN_OPENAI_LIVE_TESTS") != "1",
    reason="Set RUN_OPENAI_LIVE_TESTS=1 to run live OpenAI integration tests.",
)
def test_openai_gpt_5_2_live_generation():
    if not os.getenv("LLM_API_KEY"):
        pytest.skip("LLM_API_KEY is not set for live OpenAI test.")

    with tempfile.TemporaryDirectory() as tmpdir:
        pipeline = GeneratePlanPipeline(
            llm_provider="openai",
            llm_model="gpt-5.2",
            output_dir=tmpdir,
            scenes_dir="scenes",
        )
        result = pipeline.run(
            "scenes/apartment_living_room.json",
            "我想要一个快速运镜，像是电影里面一样深邃",
            save=True,
        )

        assert result.directing_plan.plan_id
        assert len(result.directing_plan.shots) >= 1
        assert len(result.trajectory_plan.trajectories) == len(result.directing_plan.shots)
        assert isinstance(result.validation_report.is_valid, bool)

        output_files = list(Path(tmpdir).glob("*.json"))
        assert len(output_files) == 3
