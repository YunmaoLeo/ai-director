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
  "llm_model": "gpt-5",
  "planning_mode": "freeform_llm",
  "director_hint": "auto",
  "director_notes": "optional"
}
```

Notes:

- `llm_provider`, `llm_model`, `planning_mode`, `director_hint`, `director_notes` are optional.
- Backward-compatible fields `cinematic_style` and `style_notes` are still accepted but deprecated.

Planning modes:

- `freeform_llm`: open camera language with curated film-language glossary support in the shot prompt.
- `camera_dsl`: glossary-aware camera DSL mode with reusable rig and lens primitives.

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

The semantic prompt is intentionally compacted before LLM use:

- repetitive raw events are de-noised into representative samples,
- event-type distribution is preserved,
- the backend avoids injecting duplicate narrative summaries across passes.

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
   - shot pass.
6. Run deterministic checks for diagnostics only (does not rewrite the LLM shot plan).
7. Solve temporal trajectories (transition-aware + event-aware framing, plus lens/FOV control).
8. Validate outputs and persist artifacts.

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
  - `planning_mode`
  - `director_policy`, `director_rationale`
  - `saved_at`

Trajectory timed points include:

- `position`
- `look_at`
- `fov`
- `dutch`
- `focus_distance`
- `aperture`
- `focal_length`
- `lens_shift`

Shot constraints may also include lens-oriented controls such as:

- `fov`, `fov_start`, `fov_end`
- `dutch`, `dutch_start`, `dutch_end`
- `focus_distance`, `focus_distance_start`, `focus_distance_end`
- `aperture`, `aperture_start`, `aperture_end`
- `focal_length`, `focal_length_start`, `focal_length_end`
- `lens_shift`, `lens_shift_start`, `lens_shift_end`
- `lens_profile`
- `zoom_profile`
- `camera_height_start`, `camera_height_end`
- `rig_style`
- `dsl`
- `film_terms`

Unity playback now consumes these through `Cinemachine` and URP `Depth Of Field`, so the contract no longer stops at camera position and FOV alone.

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
