"""Generate a semantic event layer from raw timeline events."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

from app.models.scene_timeline import SceneEvent, SceneTimeline, SemanticSceneEvent
from app.services.llm_client import LLMClient
from app.utils.logger import get_logger

logger = get_logger(__name__)


class TemporalEventInterpreter:
    """Build a human-readable semantic event layer from raw motion events."""

    def __init__(self, max_semantic_events: int = 12):
        self._max_semantic_events = max(1, max_semantic_events)
        self._max_prompt_events = max(8, self._max_semantic_events * 2)

    def interpret(
        self,
        timeline: SceneTimeline,
        intent: str,
        llm_client: LLMClient | None,
    ) -> list[SemanticSceneEvent]:
        raw_events = timeline.raw_events or timeline.events
        if not raw_events:
            return []

        system_prompt = (
            "You are a temporal scene analyst. Convert low-level timeline signals into "
            "high-level semantic events for cinematic planning. Use only evidence from "
            "the provided raw events and object tracks. Return strict JSON."
        )
        user_prompt = self._build_user_prompt(timeline, intent, raw_events)

        if llm_client is not None:
            try:
                response_text = llm_client.generate(system_prompt, user_prompt)
                parsed = self._parse_semantic_events(response_text, timeline)
                if parsed:
                    return parsed[: self._max_semantic_events]
            except Exception as exc:  # noqa: BLE001
                logger.warning("Semantic event interpretation failed; falling back: %s", exc)

        return self._fallback_semantic_events(raw_events, timeline)

    def _build_user_prompt(
        self,
        timeline: SceneTimeline,
        intent: str,
        raw_events: list[SceneEvent],
    ) -> str:
        selected_events = self._select_prompt_events(raw_events)
        object_lines = []
        for obj in timeline.objects_static:
            object_lines.append(
                f"- {obj.id} ({obj.category}, importance={obj.importance:.2f}, tags={','.join(obj.tags)})"
            )
        if not object_lines:
            object_lines.append("- none")

        event_lines = []
        for event in selected_events:
            event_lines.append(
                f"- id={event.event_id}, type={event.event_type}, "
                f"t={event.timestamp:.2f}, d={event.duration:.2f}, "
                f"objects={','.join(event.object_ids)}, desc={event.description}"
            )
        if not event_lines:
            event_lines.append("- none")

        event_count_lines = self._summarize_event_counts(raw_events)

        return (
            "Semantic Event Interpretation Task\n\n"
            "Output JSON format:\n"
            "{\n"
            '  "semantic_events": [\n'
            "    {\n"
            '      "semantic_id": "sem_0001",\n'
            '      "label": "string",\n'
            '      "time_start": 0.0,\n'
            '      "time_end": 0.5,\n'
            '      "object_ids": ["obj_a"],\n'
            '      "summary": "human-readable cinematic moment",\n'
            '      "dramatic_role": "setup|develop|peak|release",\n'
            '      "camera_implication": "short camera-language directive",\n'
            '      "salience": 0.0,\n'
            '      "confidence": 0.0,\n'
            '      "evidence_event_ids": ["evt_0001"],\n'
            '      "tags": ["string"]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Do not invent objects or timestamps not supported by evidence.\n"
            "- Favor concise, human-readable moments that help directing decisions.\n"
            "- Prefer 3-10 semantic events.\n"
            "- Assign dramatic_role from setup/develop/peak/release.\n"
            "- camera_implication should be actionable and generic (e.g., track rivalry, hold context, punch-in on lead change).\n"
            "- salience and confidence must be in [0,1].\n\n"
            f"Scene: {timeline.scene_id} ({timeline.scene_type})\n"
            f"Time Span: {timeline.time_span.start:.2f}s to {timeline.time_span.end:.2f}s\n"
            f"Intent: {intent}\n\n"
            "Objects:\n"
            f"{chr(10).join(object_lines)}\n\n"
            "Raw Event Distribution:\n"
            f"{chr(10).join(event_count_lines)}\n\n"
            f"Representative Raw Events (selected {len(selected_events)} of {len(raw_events)} after de-noising):\n"
            f"{chr(10).join(event_lines)}\n"
        )

    def _parse_semantic_events(
        self,
        response_text: str,
        timeline: SceneTimeline,
    ) -> list[SemanticSceneEvent]:
        payload: Any = json.loads(response_text)
        if isinstance(payload, list):
            items = payload
        elif isinstance(payload, dict):
            items = (
                payload.get("semantic_events")
                or payload.get("events")
                or payload.get("highlights")
                or []
            )
        else:
            items = []

        if not isinstance(items, list):
            return []

        result: list[SemanticSceneEvent] = []
        for index, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue

            semantic_id = str(raw.get("semantic_id") or raw.get("id") or f"sem_{index + 1:04d}")
            label = str(raw.get("label") or raw.get("event_type") or "moment").strip() or "moment"
            time_start = self._clamp_time(
                self._to_float(raw.get("time_start"), timeline.time_span.start),
                timeline,
            )
            time_end_raw = raw.get("time_end")
            if time_end_raw is None:
                time_end_raw = time_start + self._to_float(raw.get("duration"), 0.0)
            time_end = self._clamp_time(self._to_float(time_end_raw, time_start), timeline)
            if time_end < time_start:
                time_end = time_start

            object_ids = raw.get("object_ids") or raw.get("subjects") or []
            if not isinstance(object_ids, list):
                object_ids = []
            object_ids = [str(obj_id) for obj_id in object_ids if str(obj_id).strip()]

            summary = str(raw.get("summary") or raw.get("description") or "").strip()
            if not summary:
                summary = f"{label} around {time_start:.2f}s"
            dramatic_role = str(raw.get("dramatic_role") or "").strip().lower()
            if dramatic_role not in {"setup", "develop", "peak", "release"}:
                dramatic_role = self._infer_dramatic_role(label=label, tags=raw.get("tags"), salience=self._to_float(raw.get("salience"), 0.5))
            camera_implication = str(raw.get("camera_implication") or "").strip()
            if not camera_implication:
                camera_implication = self._infer_camera_implication(label=label, dramatic_role=dramatic_role, object_ids=object_ids)

            evidence_ids = raw.get("evidence_event_ids") or raw.get("event_ids") or []
            if not isinstance(evidence_ids, list):
                evidence_ids = []
            evidence_ids = [str(event_id) for event_id in evidence_ids if str(event_id).strip()]

            tags = raw.get("tags") or []
            if not isinstance(tags, list):
                tags = []
            tags = [str(tag) for tag in tags if str(tag).strip()]

            result.append(
                SemanticSceneEvent(
                    semantic_id=semantic_id,
                    label=label,
                    time_start=time_start,
                    time_end=time_end,
                    object_ids=object_ids,
                    summary=summary,
                    dramatic_role=dramatic_role,
                    camera_implication=camera_implication,
                    salience=self._clamp_unit(self._to_float(raw.get("salience"), 0.5)),
                    confidence=self._clamp_unit(self._to_float(raw.get("confidence"), 0.5)),
                    evidence_event_ids=evidence_ids,
                    tags=tags,
                )
            )

        result.sort(key=lambda item: (item.time_start, item.time_end, item.semantic_id))
        return result

    def _fallback_semantic_events(
        self,
        raw_events: list[SceneEvent],
        timeline: SceneTimeline,
    ) -> list[SemanticSceneEvent]:
        salience_by_type = {
            "interaction": 0.85,
            "occlusion_start": 0.75,
            "occlusion_end": 0.7,
            "appear": 0.65,
            "disappear": 0.65,
            "speed_change": 0.6,
            "direction_change": 0.58,
        }

        selected_events = self._select_prompt_events(raw_events)[: self._max_semantic_events]
        result: list[SemanticSceneEvent] = []
        for index, event in enumerate(selected_events):
            start = self._clamp_time(event.timestamp, timeline)
            end = self._clamp_time(event.timestamp + max(event.duration, 0.05), timeline)
            label = event.event_type.replace("_", " ").strip().title()
            summary = event.description.strip() or f"{label} involving {', '.join(event.object_ids)}."
            dramatic_role = self._infer_dramatic_role(
                label=label,
                tags=[event.event_type],
                salience=salience_by_type.get(event.event_type, 0.55),
            )
            result.append(
                SemanticSceneEvent(
                    semantic_id=f"sem_{index + 1:04d}",
                    label=label,
                    time_start=start,
                    time_end=max(start, end),
                    object_ids=list(event.object_ids),
                    summary=summary,
                    dramatic_role=dramatic_role,
                    camera_implication=self._infer_camera_implication(
                        label=label,
                        dramatic_role=dramatic_role,
                        object_ids=list(event.object_ids),
                    ),
                    salience=salience_by_type.get(event.event_type, 0.55),
                    confidence=0.45,
                    evidence_event_ids=[event.event_id],
                    tags=[event.event_type],
                )
            )

        return result

    def _select_prompt_events(self, raw_events: list[SceneEvent]) -> list[SceneEvent]:
        if not raw_events:
            return []

        collapsed: list[SceneEvent] = []
        last_signature: tuple[str, tuple[str, ...]] | None = None
        last_timestamp: float | None = None
        for event in sorted(raw_events, key=lambda item: (item.timestamp, item.event_id)):
            signature = (event.event_type, tuple(event.object_ids))
            dedupe_window = 1.0 if event.event_type == "speed_change" else 0.5
            if (
                signature == last_signature
                and last_timestamp is not None
                and event.timestamp - last_timestamp < dedupe_window
            ):
                continue
            collapsed.append(event)
            last_signature = signature
            last_timestamp = event.timestamp

        if len(collapsed) <= self._max_prompt_events:
            return collapsed

        priority = {
            "interaction": 6,
            "occlusion_start": 5,
            "occlusion_end": 5,
            "appear": 4,
            "disappear": 4,
            "direction_change": 3,
            "speed_change": 1,
        }

        selected: list[SceneEvent] = []
        seen_ids: set[str] = set()

        def add(event: SceneEvent) -> None:
            if event.event_id in seen_ids:
                return
            selected.append(event)
            seen_ids.add(event.event_id)

        add(collapsed[0])
        add(collapsed[-1])

        ranked_middle = sorted(
            collapsed[1:-1],
            key=lambda event: (
                -priority.get(event.event_type, 2),
                event.timestamp,
            ),
        )
        for event in ranked_middle:
            if len(selected) >= self._max_prompt_events:
                break
            add(event)

        return sorted(selected, key=lambda item: (item.timestamp, item.event_id))

    @staticmethod
    def _summarize_event_counts(raw_events: list[SceneEvent]) -> list[str]:
        if not raw_events:
            return ["- none"]

        counts = Counter(event.event_type for event in raw_events)
        lines = [f"- total_events: {len(raw_events)}"]
        for event_type, count in counts.most_common(6):
            lines.append(f"- {event_type}: {count}")
        remaining = len(counts) - 6
        if remaining > 0:
            lines.append(f"- other_event_types: {remaining}")
        return lines

    @staticmethod
    def _to_float(value: Any, fallback: float) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _clamp_unit(value: float) -> float:
        return max(0.0, min(1.0, value))

    @staticmethod
    def _clamp_time(value: float, timeline: SceneTimeline) -> float:
        return max(timeline.time_span.start, min(timeline.time_span.end, value))

    @staticmethod
    def _infer_dramatic_role(label: str, tags: Any, salience: float) -> str:
        text = f"{label} {' '.join(tags) if isinstance(tags, list) else ''}".lower()
        if any(token in text for token in ["start", "appear", "setup", "opening"]):
            return "setup"
        if any(token in text for token in ["lead", "climax", "peak", "collision", "overtake", "critical"]):
            return "peak"
        if any(token in text for token in ["final", "resolve", "release", "aftermath"]):
            return "release"
        if salience >= 0.8:
            return "peak"
        return "develop"

    @staticmethod
    def _infer_camera_implication(label: str, dramatic_role: str, object_ids: list[str]) -> str:
        label_text = label.lower()
        if "lead" in label_text or "overtake" in label_text:
            return "punch-in on position change while preserving both competitors in frame"
        if "start" in label_text:
            return "establish geography then commit to primary movers"
        if dramatic_role == "setup":
            return "hold contextual framing and orient subject positions"
        if dramatic_role == "peak":
            return "tighten framing and emphasize decisive action beat"
        if dramatic_role == "release":
            return "widen slightly to show aftermath and reset spatial context"
        if len(object_ids) >= 2:
            return "track interaction with readable two-subject composition"
        return "maintain_subject_continuity"
