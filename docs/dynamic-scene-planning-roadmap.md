# Dynamic Scene Cinematic Planning Roadmap

## Goal

Upgrade the current static-scene pipeline to support **time-varying scenes** and produce camera plans that remain cinematic while responding to motion over a time window.

This roadmap is planning-only. No implementation is included here.

---

## Scope and Non-Goals

### In Scope

- Capture temporal scene descriptions from Unity (instead of a single snapshot).
- Extend backend planning from one-shot generation to temporal/multi-pass planning.
- Add frontend debugging tools for timeline-based inspection and playback comparison.
- Support iterative LLM planning loops where useful.

### Out of Scope (Initial Phase)

- Full real-time frame-by-frame re-planning at game framerate.
- Multi-camera switching across many physical cameras.
- Production-grade distributed orchestration.

---

## Target System Workflow (Dynamic Version)

1. Unity records a scene window (for example 5-20 seconds) as temporal samples.
2. Unity sends one planning request containing:
   - user intent
   - scene timeline summary
   - optional keyframe images / vision notes
3. Backend builds a temporal cinematic abstraction.
4. Backend runs multi-stage planning:
   - stage A: global directing beats over time
   - stage B: shot-level temporal constraints
   - stage C: trajectory solving and smoothing
   - stage D: validation and confidence checks
5. Backend returns:
   - temporal directing plan
   - temporal trajectory plan
   - validation report
   - run metadata
6. Frontend and Unity replay and debug with timeline controls.

---

## Unity Layer Plan

## 1) Runtime Temporal Capture

Introduce a timeline capture mode in runtime components:

- Sampling strategy:
  - fixed interval sampling (for example 5-10 Hz), not every rendered frame
  - configurable capture duration
- Per-sample data:
  - timestamp
  - object transforms for tracked objects
  - object visibility proxy (in view / off-screen / occluded estimate)
  - scene-level events (object appears/disappears, interaction changes)
- Compression/aggregation:
  - keyframe extraction (reduce redundant samples)
  - motion stats per object (speed, direction trend, acceleration buckets)

## 2) Temporal Scene Description Schema (Unity Output)

Add a new payload mode next to current static summary:

- `scene_timeline`:
  - `time_span`: start/end/duration
  - `objects_static`: static semantics and dimensions
  - `object_tracks`: time-series transforms and derived motion descriptors
  - `events`: detected semantic events
  - `camera_candidates` (optional): suggested safe regions over time
- Keep backward compatibility with static `scene_summary` mode.

## 3) Vision Augmentation Strategy

Use OpenAI vision selectively on keyframes:

- Trigger only when:
  - semantic uncertainty is high
  - tracked objects are untagged/unknown
  - critical events are hard to infer from geometry alone
- Send keyframes + concise context, receive semantic annotations.
- Merge vision annotations into timeline abstraction, not raw per-frame chat output.

## 4) Unity Playback Updates

- Support trajectory plans with timeline mapping:
  - camera pose as function of time
  - optional re-timing policy if Unity runtime time differs
- Add debug overlays:
  - current shot segment
  - current target subject
  - look-at and FOV trace

---

## Backend Layer Plan

## 1) Data Model and API Evolution

Add dynamic endpoints and models while keeping existing APIs stable:

- New request shape:
  - `scene_timeline` + `intent` + `planning_config`
- New response shape:
  - temporal directing plan
  - temporal trajectory plan
  - validation with temporal checks
- Keep `/api/generate` and static schemas as compatibility mode.

## 2) Temporal Abstraction Service

Create a temporal abstraction step before directing:

- Track-level summarization:
  - primary subjects over time
  - motion salience ranking
  - event windows and transitions
- Space-time affordances:
  - where camera can move safely over time
  - occlusion-risk windows
  - reveal opportunities and conflict windows

## 3) Iterative LLM Planning Strategy (Recommended)

Use structured multi-pass planning instead of one large prompt:

1. **Global Beat Pass**
   - Input: intent + temporal abstraction summary
   - Output: high-level beat timeline and cinematic goals
2. **Shot Intent Pass**
   - Input: beats + scene-time constraints
   - Output: shot segments with targets, movement style, pacing, transitions
3. **Constraint Critique Pass**
   - Input: draft shots + deterministic checks
   - Output: revised constraints or fallback edits
4. **Deterministic Solve**
   - Convert shot intents into time-parameterized trajectories
5. **Validation Pass**
   - Schema + temporal continuity + safety + target coverage

Why iterative:
- lower hallucination risk
- better control and observability
- easier partial retries (retry one pass instead of whole generation)

## 4) Solver Refactor for Time-Varying Targets

- Trajectory solver must support moving targets.
- Add objective terms:
  - smoothness
  - subject framing continuity
  - collision/clearance margin over time
  - cinematic pace adherence
- Add temporal constraints:
  - shot boundary continuity
  - transition feasibility
  - FOV continuity rules

## 5) Debug Persistence

Persist full dynamic run bundles:

- input timeline snapshot
- intermediate LLM pass artifacts
- final plans
- validation and metrics
- model/provider/version used per pass

This is required for reproducible debugging and A/B comparison.

---

## Frontend Debug UI Plan

## 1) Timeline-Centric Workspace

Extend current panels with temporal controls:

- global timeline scrubber
- shot segment markers
- event markers
- playback speed controls

## 2) 3D Preview Enhancements

- Show animated camera and moving objects over time.
- Show FOV frustum and look-at target along timeline.
- Allow toggling layers:
  - trajectories
  - subjects
  - occlusion risk heat hints (if available)

## 3) Run Comparison

- Compare two runs side-by-side:
  - different models
  - different iterative strategies
  - different intents
- Show per-run metadata and per-pass model info clearly.

## 4) Artifact Browser

- Browse saved run bundles.
- Inspect intermediate pass outputs (Beat/Shot/Critique) with timestamps.
- One-click replay from selected run.

---

## Implementation Phases

## Phase 0: Design Freeze (1 week)

- Finalize temporal schemas and API contracts.
- Decide sampling defaults and payload size limits.
- Define deterministic checks used between LLM passes.

Exit criteria:
- schema docs approved
- sample payloads validated end-to-end (without solver changes)

## Phase 1: Unity Temporal Capture + Backend Ingestion (1-2 weeks)

- Unity captures timeline and uploads `scene_timeline`.
- Backend accepts, validates, stores timeline bundles.
- Keep planning static for now (temporal data stored, not fully used).

Exit criteria:
- stable upload for long enough clips
- reproducible stored input bundles

## Phase 2: Temporal Abstraction + Iterative Directing (2 weeks)

- Implement temporal abstraction service.
- Implement multi-pass LLM orchestration and artifact persistence.
- Add robust fallback path if one pass fails.

Exit criteria:
- directing plans include meaningful time segments
- retries/fallbacks avoid hard 500 failures

## Phase 3: Temporal Trajectory Solver (2-3 weeks)

- Refactor solver for moving targets and time-parametric output.
- Add temporal validation rules.

Exit criteria:
- smooth and valid camera motion across full clip
- measurable improvement vs static baseline on test scenes

## Phase 4: Frontend Timeline Debug + Comparison (1-2 weeks)

- Add timeline UI and run comparison workflow.
- Add 3D dynamic preview controls and pass inspection.

Exit criteria:
- debug workflow can identify failure source per pipeline stage

## Phase 5: Hardening and Evaluation (1-2 weeks)

- Performance profiling and payload optimization.
- Regression suite for static and dynamic modes.
- Documentation and operator playbook updates.

---

## Testing Strategy

## Unity

- deterministic playback test scenes:
  - slow actor motion
  - sudden direction change
  - object occlusion crossing
- payload size and sampling stress tests

## Backend

- schema and contract tests for dynamic payloads
- orchestration tests for iterative pass retries/fallbacks
- solver continuity and safety tests over timeline

## Frontend

- timeline controls behavior tests
- run-history and comparison integrity tests
- preview sync accuracy tests

---

## Key Risks and Mitigations

- **Risk:** payload too large for practical iteration  
  **Mitigation:** keyframe extraction, motion summarization, configurable sampling

- **Risk:** iterative LLM loop increases latency/cost  
  **Mitigation:** per-pass model selection, pass-level caching, selective retry

- **Risk:** dynamic solver instability on abrupt motion  
  **Mitigation:** transition constraints, continuity penalties, fallback shot templates

- **Risk:** debugging complexity rises sharply  
  **Mitigation:** persist intermediate artifacts and add timeline-centric UI inspection

---

## Immediate Next Decisions

1. Choose default capture window and sampling rate for first implementation.
2. Freeze `scene_timeline` schema v1 with strict size budget.
3. Decide first iterative planning profile:
   - 2-pass (Beat + Shot) or
   - 3-pass (Beat + Shot + Critique)
4. Select baseline dynamic test scenes for acceptance benchmarks.
