# Backend Temporal Planning Interface (for Unity Integration)

## 1. Purpose

This document defines the backend contract for dynamic-scene cinematic planning.

Use it as the implementation reference for Unity-side timeline capture and API integration.
It focuses on data interfaces and runtime behavior, not full Unity architecture.

---

## 2. Main API Endpoint

### `POST /api/unity/temporal/generate`

This is the Unity-facing temporal planning entrypoint.
It accepts a `scene_timeline` payload and returns a full planning bundle.

Request body shape:

```json
{
  "scene_id": "string",
  "intent": "string",
  "scene_timeline": { "...SceneTimeline..." },
  "llm_provider": "openai",
  "llm_model": "gpt-4o",
  "director_hint": "auto",
  "director_notes": "optional"
}
```

Notes:

- `llm_provider`, `llm_model`, `director_hint`, `director_notes` are optional.
- Backward-compatible fields `cinematic_style` and `style_notes` are still accepted but deprecated.

---

## 3. SceneTimeline Contract

Required top-level fields:

- `scene_id`, `scene_name`, `scene_type`, `bounds`, `time_span`
- `objects_static`: static object list
- `object_tracks`: per-object sampled motion track

Event layers:

- `raw_events`: deterministic timeline events (preferred for machine logic)
- `semantic_events`: optional semantic interpretation layer (can be empty from Unity)
- `events`: legacy compatibility mirror (accepted)

Important behavior:

- If `semantic_events` is empty, backend will auto-generate it from `raw_events`.
- Backend also caches semantic interpretation by scene content signature to avoid repeated LLM work.

---

## 4. Semantic Event Auto-Enrichment

When backend enriches semantic events, each semantic event includes:

- `semantic_id`, `label`
- `time_start`, `time_end`
- `object_ids`
- `summary`
- `dramatic_role` (`setup|develop|peak|release`)
- `camera_implication` (camera-language directive)
- `salience`, `confidence`
- `evidence_event_ids`, `tags`

This enriched layer is then used by downstream beat/shot/trajectory planning.

---

## 5. Backend Planning Stages

For each temporal generate request:

1. Validate `scene_timeline` schema.
2. Normalize legacy `events` and `raw_events`.
3. Load semantic-event cache or interpret semantic events (LLM + fallback).
4. Build temporal cinematic abstraction.
5. Run multi-pass directing generation:
   - style/director pass,
   - beat pass,
   - shot pass,
   - critique pass.
6. Solve temporal trajectories (transition-aware + event-aware framing).
7. Validate outputs and persist artifacts.

---

## 6. Response Contract

`/api/unity/temporal/generate` returns:

- `temporal_directing_plan`
- `temporal_trajectory_plan`
- `validation_report`
- `pass_artifacts`
- `scene_timeline` (possibly enriched with semantic events)
- run metadata fields:
  - `output_prefix`
  - `scene_id`, `intent`
  - `llm_provider`, `llm_model`
  - `director_policy`, `director_rationale`
  - `saved_at`

---

## 7. Output Persistence and Debug Retrieval

Artifacts are saved under backend `outputs/` with `output_prefix`.
Useful endpoints:

- `GET /api/temporal/runs` -> list historical temporal runs
- `GET /api/temporal/runs/{prefix}` -> load full run bundle
- `GET /api/temporal/capabilities` -> available director policies
- `GET /api/llm/models` -> backend-supported model aliases/recommendations

---

## 8. Unity Integration Guidance (Minimal)

Unity-side implementation should ensure:

1. Stable object IDs across `objects_static`, `object_tracks`, and events.
2. Consistent timeline timestamps (`time_span` and sample times).
3. `raw_events` remain deterministic and evidence-grounded.
4. No scene-specific hardcoding in payload schema (keep scene-agnostic contract).
5. Submit full `scene_timeline` + `intent` in one request.

That is enough for backend planning to operate correctly.

