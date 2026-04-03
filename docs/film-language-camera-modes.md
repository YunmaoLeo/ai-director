# Film Language and Camera Modes

## Purpose

This document explains how film-language terminology is used in the dynamic-scene directing pipeline.

Reference source for the vocabulary direction:

- Columbia Film Language Glossary: <https://filmglossary.ccnmtl.columbia.edu/term/>

The implementation does **not** dump the full glossary into prompts. Instead, it uses a curated subset of terms that map cleanly to the current camera solver.

---

## Planning Modes

### `freeform_llm`

Use this mode when you want the model to invent camera language more freely.

Behavior:

- The shot prompt includes a compact film-language glossary.
- The model can use terms such as `aerial shot`, `crane shot`, `handheld shot`, `Steadicam shot`, `zoom shot`, `high-angle shot`, `low-angle shot`, `wide-angle lens`, and `fisheye lens`.
- The backend solver then tries to interpret those terms from shot labels, movement labels, rationale text, and `constraints`.

Best for:

- exploratory ideation,
- unusual cinematic phrasing,
- testing whether user intent alone can produce expressive shot design.

### `camera_dsl`

Use this mode when you want stronger reproducibility and more controllable outputs.

Behavior:

- The shot prompt includes both the curated film-language glossary and the camera DSL catalog.
- The model is encouraged to choose explicit DSL rigs and pair them with physical camera constraints.
- The solver reads `constraints.dsl` plus lens/FOV/height parameters to produce more stable trajectories.

Best for:

- consistent iteration,
- replayable camera behavior,
- intentionally authored rig families.

---

## Curated Film Terms

The current glossary-aware prompt layer focuses on terms that can be realized in code:

- `aerial shot`
- `crane shot`
- `high-angle shot`
- `low-angle shot`
- `handheld shot`
- `Steadicam shot`
- `swish pan`
- `dutch angle / canted angle`
- `tracking (trucking) shot`
- `zoom shot`
- `wide-angle lens`
- `fisheye lens`
- `rack focus`
- `shallow focus`
- `deep focus`
- `point of view`
- `establishing shot`
- `close-up / medium shot / long shot`

---

## Executable Camera Controls

The solver currently supports these physical controls in shot `constraints`:

- `camera_height`
- `camera_height_start`
- `camera_height_end`
- `camera_distance`
- `distance_scale`
- `fov`
- `fov_start`
- `fov_end`
- `dutch`
- `dutch_start`
- `dutch_end`
- `focus_distance`
- `focus_distance_start`
- `focus_distance_end`
- `aperture`
- `aperture_start`
- `aperture_end`
- `focal_length`
- `focal_length_start`
- `focal_length_end`
- `lens_shift`
- `lens_shift_start`
- `lens_shift_end`
- `bloom_intensity`
- `bloom_intensity_start`
- `bloom_intensity_end`
- `bloom_threshold`
- `vignette_intensity`
- `post_exposure`
- `saturation`
- `contrast`
- `chromatic_aberration`
- `film_grain_intensity`
- `motion_blur_intensity`
- `lens_profile`
- `zoom_profile`
- `rig_style`
- `camera_offset`
- `look_at_offset`
- `overhead`
- `top_down`
- `height_bias`
- `vantage`
- `orbit_arc_degrees`
- `dsl`
- `film_terms`

This means the system can now vary not only camera position and look-at, but also:

- lens width,
- zoom progression,
- vertical crane movement,
- dutch / roll,
- focus distance,
- aperture / depth-of-field feel,
- physical lens shift,
- rig feel such as handheld vs. steadicam.

At runtime, Unity now executes this through `Cinemachine` plus URP post-processing. That means `Depth Of Field`, `Bloom`, `Vignette`, `Color Adjustments`, `Chromatic Aberration`, `Film Grain`, and `Motion Blur` can all become part of the actual playback path instead of staying prompt-level language only.

---

## Glossary-Derived DSL Examples

The DSL catalog includes glossary-inspired rigs such as:

- `crane_rise`
- `crane_drop`
- `handheld_chase`
- `steadicam_glide`
- `swish_pan_reveal`
- `zoom_in_punch`
- `zoom_out_reveal`
- `low_angle_hero`
- `wide_lens_rush`
- `fisheye_surge`
- `deep_focus_tableau`
- `pov_drive`

These sit alongside the existing tactical/racing-oriented DSLs like `aerial_follow`, `top_lock`, `helicopter_orbit`, and `parallel_strafe`.

---

## Design Constraint

Film language should improve expression without reintroducing prompt bloat.

So the pipeline follows three guardrails:

1. Raw event noise is compacted before semantic interpretation.
2. Prompts only include a selected glossary subset.
3. DSL terms are favored when they can be translated into deterministic camera behavior.
