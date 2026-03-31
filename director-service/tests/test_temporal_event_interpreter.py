"""Tests for semantic event prompt compaction."""

from app.models.scene_summary import Bounds, SceneObject
from app.models.scene_timeline import SceneEvent, SceneTimeline, TimeSpan
from app.services.temporal_event_interpreter import TemporalEventInterpreter


def _build_noisy_timeline() -> SceneTimeline:
    raw_events = [
        SceneEvent(
            event_id=f"speed_{index}",
            event_type="speed_change",
            timestamp=index * 0.1,
            duration=0.0,
            object_ids=["car_a"],
            description=f"minor speed fluctuation {index}",
        )
        for index in range(20)
    ]
    raw_events.append(
        SceneEvent(
            event_id="appear_1",
            event_type="appear",
            timestamp=0.0,
            duration=0.0,
            object_ids=["car_b"],
            description="car_b enters the frame",
        )
    )
    raw_events.append(
        SceneEvent(
            event_id="interaction_1",
            event_type="interaction",
            timestamp=1.4,
            duration=0.4,
            object_ids=["car_a", "car_b"],
            description="cars converge into a close duel",
        )
    )
    return SceneTimeline(
        scene_id="noisy_events",
        scene_name="Noisy Events",
        scene_type="test",
        bounds=Bounds(width=20.0, length=30.0, height=8.0),
        time_span=TimeSpan(start=0.0, end=4.0, duration=4.0),
        objects_static=[
            SceneObject(
                id="car_a",
                name="Car A",
                category="vehicle",
                position=(0.0, 0.0, 0.0),
                size=(2.0, 1.0, 4.0),
                forward=(0.0, 0.0, 1.0),
                importance=0.9,
                tags=["hero"],
            ),
            SceneObject(
                id="car_b",
                name="Car B",
                category="vehicle",
                position=(1.0, 0.0, 0.0),
                size=(2.0, 1.0, 4.0),
                forward=(0.0, 0.0, 1.0),
                importance=0.8,
                tags=["rival"],
            ),
        ],
        raw_events=raw_events,
    )


def test_user_prompt_compacts_repetitive_raw_events():
    interpreter = TemporalEventInterpreter(max_semantic_events=6)
    timeline = _build_noisy_timeline()

    prompt = interpreter._build_user_prompt(
        timeline,
        "Emphasize the rivalry cleanly",
        timeline.raw_events,
    )

    assert "Raw Event Distribution:" in prompt
    assert "- speed_change: 20" in prompt
    assert "Representative Raw Events" in prompt
    assert "type=interaction" in prompt
    assert prompt.count("type=speed_change") < 8


def test_fallback_semantic_events_prioritize_salient_moments():
    interpreter = TemporalEventInterpreter(max_semantic_events=4)
    timeline = _build_noisy_timeline()

    semantic_events = interpreter._fallback_semantic_events(timeline.raw_events, timeline)

    labels = {event.label for event in semantic_events}
    assert "Interaction" in labels
    interaction_event = next(event for event in semantic_events if event.label == "Interaction")
    assert interaction_event.object_ids == ["car_a", "car_b"]
    assert len(semantic_events) <= 4
