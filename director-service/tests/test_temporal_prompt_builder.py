"""Tests for temporal prompt compaction."""

from app.models.temporal_directing_plan import Beat
from app.services.temporal_abstraction import TemporalAbstractor
from app.services.temporal_prompt_builder import TemporalPromptBuilder


def test_shot_prompt_omits_duplicate_replay_description(walking_actor_timeline):
    builder = TemporalPromptBuilder()
    temporal_cinematic = TemporalAbstractor().abstract(walking_actor_timeline)
    beats = [
        Beat(
            beat_id="beat_1",
            time_start=walking_actor_timeline.time_span.start,
            time_end=walking_actor_timeline.time_span.end,
            goal="follow the subject",
            mood="focused",
            subjects=["actor_1"],
        )
    ]

    _, prompt = builder.build_shot_intent_prompt(
        beats,
        walking_actor_timeline,
        temporal_cinematic,
        "Keep the coverage readable",
        style_profile="balanced",
        style_brief="Bias toward clarity over ornament.",
    )

    assert "### Replay Description (Derived from Unity Timeline)" not in prompt
    assert "### Cinematic Style Guidance" in prompt
    assert "## Film Language Glossary" in prompt
    assert "`aerial shot`" in prompt


def test_beat_prompt_truncates_overlong_event_summary(walking_actor_timeline):
    builder = TemporalPromptBuilder()
    temporal_cinematic = TemporalAbstractor().abstract(walking_actor_timeline)
    temporal_cinematic.event_summary = "\n".join(
        f"line_{index}" for index in range(20)
    )

    _, prompt = builder.build_global_beat_prompt(
        walking_actor_timeline,
        temporal_cinematic,
        "Find the core dramatic beats",
    )

    assert "line_0" in prompt
    assert "... (10 additional summary lines omitted)" in prompt
