# Dynamic Scene Planning Roadmap

## 1. Current Baseline

Implemented pipeline behavior:

1. Accept temporal scene timeline input.
2. Maintain dual event layers:
   - deterministic `raw_events`,
   - semantic `semantic_events` (LLM-interpreted, fallback-supported).
3. Build temporal cinematic abstraction.
4. Run multi-pass directing generation (style, beats, shots, critique).
5. Solve temporal trajectories with transition-aware continuity.
6. Validate, persist, and expose artifacts in backend + web debug UI.

---

## 2. Near-Term Priorities

### P1: Better Temporal Coverage Quality

- Add candidate-shot generation + reranking by cinematic quality metrics.
- Improve event-to-shot alignment scoring and corrective rewrites.

### P2: Richer Event Semantics

- Expand `semantic_events` quality checks.
- Improve mapping from semantic event role to camera behavior.
- Keep event semantics grounded in raw evidence.

### P3: Edit-Aware Trajectory Refinement

- Improve transition-specific trajectory behavior and framing continuity.
- Add stronger event-emphasis constraints near decisive moments.

### P4: Unity Handshake Stability

- Lock schema/version strategy for timeline payloads.
- Add compatibility checks for Unity-uploaded scene timeline contracts.

---

## 3. Operational Rules

- Preserve backward compatibility for legacy `events` where possible.
- Prefer scene-agnostic logic over domain-specific hardcoding.
- Keep output artifacts reproducible and inspectable for debugging.

