# Dynamic Scene Planning Roadmap (Updated)

## 1) Current Status (Implemented)

The project now supports temporal planning with a dual-layer event model:

- Unity/runtime side captures `scene_timeline` with:
  - `object_tracks`
  - `events` (legacy compatibility)
  - `raw_events` (deterministic geometric events)
  - `semantic_events` (optional; can be empty from Unity)
- Backend temporal pipeline:
  - auto-syncs legacy `events` with `raw_events`
  - runs LLM semantic-event interpretation when `semantic_events` is missing
  - keeps fallback behavior so planning does not fail if semantic interpretation fails
- Frontend debug UI:
  - Scene panel shows semantic events first (falls back to raw)
  - Temporal trajectory timeline can render semantic events as markers

This means Unity remains scenario-agnostic, while semantic readability is delegated to backend LLM interpretation.

---

## 2) Canonical Event Contract (Now)

### Raw Event Layer (`raw_events`)

Machine-oriented, deterministic, geometry/timing derived:

- `event_id`
- `event_type`
- `timestamp`
- `duration`
- `object_ids`
- `description`

Typical `event_type`: `appear`, `disappear`, `speed_change`, `direction_change`, `interaction`, `occlusion_start`, `occlusion_end`.

### Semantic Event Layer (`semantic_events`)

Human-readable interpretation layer for directing/debug:

- `semantic_id`
- `label`
- `time_start`, `time_end`
- `object_ids`
- `summary`
- `salience`, `confidence`
- `evidence_event_ids`
- `tags`

Important rule: semantic events must be evidence-grounded in raw events and tracks.

---

## 3) Recommended Data Flow (Target-Steady)

1. Unity captures temporal data and emits `raw_events` (plus legacy `events` for compatibility).
2. Unity sends timeline + user intent to backend.
3. Backend enriches with `semantic_events` (LLM pass + validator + fallback).
4. Backend runs beat/shot/trajectory planning.
5. Frontend/Unity playback tools visualize both layers.

---

## 4) Sample Scene Policy (Updated)

We keep temporal sample files in:

- `director-service/scenes/temporal_*.json`

Each temporal sample should:

- include `raw_events`
- include `events` as compatibility mirror
- allow `semantic_events` to be empty (recommended for testing interpretation pass), or pre-filled for fixed regression scenes

Current slot-car reference sample:

- `director-service/scenes/temporal_slot_car_compact_track.json`

---

## 5) Next Development Priorities

### P1: Generic Raw Event Coverage (Unity + backend deterministic layer)

- Add pairwise, scene-agnostic relation events:
  - proximity start/end
  - contact start/end
  - sustained co-motion
- Add hysteresis/cooldown to reduce event noise.

### P2: Semantic Event Quality Loop (Backend)

- Add stricter semantic event validation:
  - time window sanity
  - object ID existence
  - evidence linkage checks
- Add optional critique/rewrite pass for semantic event clarity.

### P3: Frontend Explainability

- Add explicit toggle between raw and semantic event tracks.
- Add hover cards showing semantic event evidence mapping (`evidence_event_ids`).

### P4: Evaluation Harness (Engineering, not thesis export)

- Compare before/after plans using:
  - event coverage in shot windows
  - subject continuity
  - cut readability under motion

---

## 6) Versioning/Compatibility Notes

- `events` remains accepted and emitted for old clients.
- New clients should prefer:
  - `raw_events` for deterministic logic
  - `semantic_events` for UI readability and directing context
- Backward compatibility is intentionally maintained in both Unity payloads and backend models.
