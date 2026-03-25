# Unity Runtime Integration

This document describes how to use the runtime components added under `unity-director-scene/Assets/Scripts/DirectorRuntime`.

## What was added

The Unity side is split into independent components:

- `DirectorSceneObjectTag`
  - Attach to important scene objects to provide stable IDs, categories, importance, and tags.
- `DirectorSceneAnalyzer`
  - Scans the current Unity scene and builds a `SceneSummaryData` that matches the existing backend schema shape.
- `DirectorTemporalSceneAnalyzer`
  - Captures a time window of the Unity scene and builds a `SceneTimelineData` for temporal planning.
- `OpenAIVisionClient`
  - Captures a camera view, sends the image to OpenAI, and returns a text summary that can help scene understanding.
- `DirectorBackendClient`
  - Sends static and temporal requests to the backend and receives plan responses.
- `DirectorCameraPlayback`
  - Replays static `trajectory_plan` and temporal `temporal_trajectory_plan`.
- `DirectorRuntimeController`
  - Orchestrates static or temporal flow: analyze/capture -> optional OpenAI vision -> backend request -> playback.

## Files

- `unity-director-scene/Assets/Scripts/DirectorRuntime/DirectorRuntimeModels.cs`
- `unity-director-scene/Assets/Scripts/DirectorRuntime/DirectorJsonUtility.cs`
- `unity-director-scene/Assets/Scripts/DirectorRuntime/DirectorSceneObjectTag.cs`
- `unity-director-scene/Assets/Scripts/DirectorRuntime/DirectorSceneAnalyzer.cs`
- `unity-director-scene/Assets/Scripts/DirectorRuntime/DirectorTemporalSceneAnalyzer.cs`
- `unity-director-scene/Assets/Scripts/DirectorRuntime/OpenAIVisionClient.cs`
- `unity-director-scene/Assets/Scripts/DirectorRuntime/DirectorBackendClient.cs`
- `unity-director-scene/Assets/Scripts/DirectorRuntime/DirectorCameraPlayback.cs`
- `unity-director-scene/Assets/Scripts/DirectorRuntime/DirectorRuntimeController.cs`

## Recommended setup

1. Pick an existing empty or manager object in the scene and attach:
   - `DirectorSceneAnalyzer`
   - `DirectorTemporalSceneAnalyzer`
   - `DirectorBackendClient`
   - `DirectorRuntimeController`
2. Pick the camera you want to animate and attach:
   - `DirectorCameraPlayback`
3. If you want image-assisted parsing, attach `OpenAIVisionClient` to any existing object.
4. Attach `DirectorSceneObjectTag` to the important objects you want the backend to reason about.

No Unity object creation is required by the scripts themselves.

## Coordinate setup

The backend trajectory solver assumes:

- `X` = room width axis
- `Z` = room length axis
- `Y` = height
- object positions are inside `[0, width] x [0, length]`

To make Unity world coordinates line up with backend coordinates:

1. Assign `coordinateOrigin` on `DirectorSceneAnalyzer`.
2. Assign the same `coordinateOrigin` on `DirectorCameraPlayback`.
3. Use a transform whose local axes represent the room axes.
4. Ideally place that transform near the room floor corner.

The analyzer normalizes object coordinates before sending them to the backend, and the playback component adds the offset back when applying the returned trajectory.

## Minimal usage flow (static)

1. On important scene objects, set:
   - `objectId`
   - `category`
   - `importance`
   - `tags`
2. On `DirectorSceneAnalyzer`, set:
   - `sceneId`
   - `sceneName`
   - `sceneType`
   - `sceneDescription`
   - `coordinateOrigin`
3. On `DirectorBackendClient`, set:
   - `baseUrl`
   - `generatePath`
   - `runtimeGeneratePath`
   - optional `bearerToken`
4. On `DirectorCameraPlayback`, set:
   - `targetCamera`
   - `coordinateOrigin`
5. On `DirectorRuntimeController`, wire:
   - `sceneAnalyzer`
   - `backendClient`
   - `cameraPlayback`
   - optional `openAIVisionClient`
   - `intent`
6. In the component context menu, click:
   - `Run Director Pipeline`

If `autoPlayTrajectory` is enabled, the returned camera path starts automatically.

## Minimal usage flow (temporal)

1. Keep the same setup as static mode, and additionally wire:
   - `DirectorRuntimeController.temporalSceneAnalyzer`
2. On `DirectorRuntimeController`:
   - set `planningMode = TemporalScene`
3. On `DirectorTemporalSceneAnalyzer`, set:
   - `sceneAnalyzer`
   - `captureDurationSeconds`
   - `sampleRateHz`
4. Run:
   - `Run Director Pipeline`

The controller captures a `scene_timeline` over time, sends it to backend temporal API, and can auto-play `temporal_trajectory_plan`.
By default, style selection is `auto` (LLM decides from replay + intent).  
If you need forced style for debugging, set `cinematicStyle` and `styleNotes` on `DirectorRuntimeController`.
For racing shots, a typical override is `cinematicStyle = motorsport_f1`.

## OpenAI vision setup

Set these fields on `OpenAIVisionClient`:

- `apiKey`
- `model`
- `analysisCamera`
- `captureResolution`

The current implementation sends:

- a text prompt
- one captured PNG image as a `data:image/png;base64,...` URL

The returned text is stored in `vision_analysis.analysis_text` and can be forwarded to the backend.

## Backend compatibility

There are three request modes.

### Mode 1: Existing backend API

Set `sendRuntimeSceneSummary = false` on `DirectorRuntimeController`.

This calls your current endpoint:

- `POST /api/generate`

Payload:

```json
{
  "scene_id": "office_room",
  "intent": "Create a slow cinematic exploration of the room."
}
```

This works with the current `director-service/app/api.py`.

### Mode 2: Runtime scene upload from Unity

Set `sendRuntimeSceneSummary = true` on `DirectorRuntimeController`.

This calls:

- `POST /api/unity/generate`

Payload shape:

```json
{
  "scene_id": "unity_scene",
  "intent": "Create a slow cinematic exploration of the room.",
  "scene_summary": {
    "scene_id": "unity_scene",
    "scene_name": "Unity Scene",
    "scene_type": "interior",
    "description": "Runtime-generated scene summary from Unity.",
    "bounds": {
      "width": 5.0,
      "length": 6.0,
      "height": 3.0
    },
    "objects": [
      {
        "id": "desk",
        "name": "Desk",
        "category": "furniture",
        "position": [3.5, 0.8, 2.0],
        "size": [1.4, 0.75, 0.7],
        "forward": [0.0, 0.0, 1.0],
        "importance": 0.8,
        "tags": ["workspace", "anchor"]
      }
    ],
    "relations": [
      {
        "type": "near",
        "source": "desk",
        "target": "chair"
      }
    ]
  },
  "vision_analysis": {
    "provider": "openai",
    "model": "gpt-4o-mini",
    "prompt": "Analyze this Unity scene for cinematic camera planning.",
    "analysis_text": "The desk is the anchor subject...",
    "image_data_url": null
  }
}
```

This endpoint is now implemented on the backend.

On each Unity upload:

- the uploaded `scene_summary` is saved into the backend `scenes/` directory as a reusable debug scene snapshot
- the generated `directing_plan`, `trajectory_plan`, and `validation_report` are saved with a unique output prefix
- the response includes `debug_scene_id`, `debug_scene_file`, and `output_prefix`

### Mode 3: Runtime temporal timeline upload from Unity

`DirectorRuntimeController` temporal mode calls:

- `POST /api/unity/temporal/generate`

Payload shape:

```json
{
  "scene_id": "unity_scene",
  "intent": "Follow the actor, then reveal the window.",
  "cinematic_style": "motorsport_f1",
  "style_notes": "Favor broadcast-like tracking around fast turns.",
  "scene_timeline": {
    "scene_id": "unity_scene",
    "scene_name": "Unity Scene",
    "scene_type": "interior",
    "description": "Runtime timeline from Unity.",
    "bounds": { "width": 6.0, "length": 8.0, "height": 3.0 },
    "time_span": { "start": 0.0, "end": 8.0, "duration": 8.0 },
    "objects_static": [
      {
        "id": "person_01",
        "name": "Actor",
        "category": "character",
        "position": [1.2, 0.0, 0.8],
        "size": [0.5, 1.8, 0.4],
        "forward": [0.0, 0.0, 1.0],
        "importance": 1.0,
        "tags": ["primary_subject"]
      }
    ],
    "object_tracks": [
      {
        "object_id": "person_01",
        "samples": [
          {
            "timestamp": 0.0,
            "position": [1.2, 0.0, 0.8],
            "rotation": [0.0, 0.0, 0.0],
            "velocity": [0.0, 0.0, 0.0],
            "visible": true
          }
        ],
        "motion": {
          "average_speed": 0.7,
          "max_speed": 1.1,
          "direction_trend": [0.1, 0.0, 0.99],
          "acceleration_bucket": "variable",
          "total_displacement": 3.2
        },
        "keyframe_indices": [0]
      }
    ],
    "events": [],
    "camera_candidates": [],
    "relations": []
  }
}
```

Backend response includes:

- `temporal_directing_plan`
- `temporal_trajectory_plan`
- `validation_report`
- `pass_artifacts`
- `scene_timeline` (echoed timeline snapshot for debug)
- `output_prefix`

## Backend response expected by Unity

Unity expects static response shape:

```json
{
  "directing_plan": { "...": "..." },
  "trajectory_plan": { "...": "..." },
  "validation_report": { "...": "..." }
}
```

The important part for playback is `trajectory_plan.trajectories[*].sampled_points`.

For temporal playback, Unity uses:

- `temporal_trajectory_plan.trajectories[*].timed_points`

## Notes and limitations

- `DirectorSceneAnalyzer` currently infers only simple `near` and `on_top_of` relations.
- `DirectorTemporalSceneAnalyzer` currently builds events with lightweight heuristics (`appear`, `disappear`, `speed_change`, `direction_change`).
- Free-space polygons are not generated yet.
- Playback currently uses the returned sampled points directly and keeps the camera looking at `look_at_position`.
- Temporal playback interpolates position/look-at/FOV between `timed_points`.
- The implementation assumes the backend trajectory coordinates use the same handedness and axis convention as the existing Python solver.
- `System.Text.Json` is used for network JSON parsing to support nested numeric arrays in `sampled_points`.

## Suggested backend next step

The next useful backend improvement would be to expose grouped run history metadata, so the frontend can browse saved output bundles by `output_prefix` instead of only listing raw JSON filenames.
