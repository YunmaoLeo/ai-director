# Project Goal (Dynamic Scene Cinematic Planning)

## 1. Core Objective

Build an AI-director pipeline that plans cinematic camera coverage for **time-varying 3D scenes**.

The primary product behavior is:

1. ingest a temporal scene replay description (scene timeline),
2. interpret user intent,
3. generate a multi-shot directing plan with edit logic,
4. solve camera trajectories for playback/simulation,
5. provide debug visualization and artifact persistence.

The project is no longer centered on static scene-only planning.

---

## 2. Product Scope

### In Scope

- Temporal scene understanding from structured replay data.
- Dual-layer event representation:
  - `raw_events` (deterministic signals),
  - `semantic_events` (LLM-readable cinematic moments).
- Multi-pass directing generation (style/beat/shot/critique).
- Trajectory solving and validation.
- Backend + web debug tooling for iteration.
- Unity-to-backend data contract support.

### Out of Scope

- Hardcoded game-specific camera logic (for example, race-only handcrafted rules).
- Manual camera-node authoring as the primary planning mechanism.
- Requiring Unity runtime execution for everyday planning/debug iteration.

---

## 3. Design Principles

1. **Scene-agnostic intelligence first**  
   The backend should work across different dynamic scenes, not only racing.

2. **LLM as director, deterministic geometry as executor**  
   LLM decides intent-level cinematography; deterministic code enforces feasibility.

3. **Evidence-grounded semantics**  
   `semantic_events` must remain grounded in timeline evidence (`raw_events`, tracks).

4. **Edit-aware planning**  
   Shot and trajectory output should encode transition intent, continuity, and emphasis timing.

5. **Debuggability**  
   All important outputs are persisted as JSON artifacts and replayable in the web UI.

---

## 4. Current End-to-End Planning Flow

1. **Input**: `scene_timeline` + user `intent`.
2. **Semantic enrichment**:
   - if `semantic_events` missing, backend derives them from `raw_events` (LLM + fallback).
   - cache semantic interpretation for repeated timeline content.
3. **Temporal abstraction**: derive cinematic temporal context.
4. **Multi-pass LLM planning**:
   - style/director policy,
   - global beats,
   - shot intents,
   - critique/refine.
5. **Deterministic solve**:
   - temporal trajectory generation,
   - transition-aware continuity handling,
   - validation.
6. **Output**:
   - temporal directing plan,
   - temporal trajectory plan,
   - validation report,
   - pass artifacts,
   - persisted scene timeline.

---

## 5. Success Criteria

- Temporal scenes produce stable, schema-valid plans.
- Plans show clear cinematic structure (beats, shot intent, transition intent).
- Generated trajectories are replayable and physically plausible.
- Unity integration can submit timelines and consume outputs through a documented contract.
- Iteration can be done quickly from backend/frontend tooling without Unity launch dependency.

