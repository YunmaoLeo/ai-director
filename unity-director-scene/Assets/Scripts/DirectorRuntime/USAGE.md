# Director Runtime - Usage Guide

## Quick Start

### 1. Setup the Demo Scene
1. Open Unity and load `Assets/Scenes/SampleScene.unity`.
2. Menu: **AI Director > Setup Demo Scene**.
   - This rebuilds a polished slot-car style demo (track surface, lane markers, barriers, start gate, two stylized cars), plus a DirectorController object with all required components.

### 2. Run the Workflow
1. **Enter Play Mode** (Ctrl+P / Cmd+P).
2. The two cars stay still until you click **Start Recording**.
3. Use the on-screen responsive control panel. The timeline cache now shows save timestamps and keeps the newest takes at the top.

| Button | Action |
|---|---|
| **Start Recording** | Begins capturing timestamped transforms of all ReplayableActors. |
| **Stop Recording** | Ends capture, builds the `SceneTimelineData` payload with raw_events. |
| **Generate Plan** | Sends the timeline + intent to the backend `POST /api/unity/temporal/generate`. |
| **Play Cinematic** | Replays the recorded segment while driving the camera from the returned trajectory plan. |
| **Stop Playback** | Interrupts cinematic playback and returns to live mode. |

### 3. Backend Prerequisites
- The director backend must be running at the URL configured on the `DirectorApiClient` component (default: `http://localhost:8000`).
- The backend endpoint `POST /api/unity/temporal/generate` must be available.
- An LLM provider must be configured on the backend (see backend docs).

## Component Reference

### DirectorController
Main orchestrator. Attach to a single GameObject along with SceneRecorder, DirectorApiClient, and CinematicPlayer.
- **Intent**: The directing prompt sent to the backend (editable in Inspector).
- **Save Debug Files**: When enabled, saves last request/response JSON to `Application.persistentDataPath`.
- **Reset Actors Before Recording**: Resets all waypoint followers to deterministic start positions for each take.
- **Timeline Cache Panel**: Displays cached takes by save date/time, sorted newest-first, with one-click loading.

### AutomatedDemoRunner
Optional runtime verifier for unattended testing.
- Runs end-to-end flow automatically: `StartRecording -> StopRecording -> GeneratePlan -> PlayCinematic`.
- Emits explicit PASS/FAIL logs in Unity Console.
- Keep `runOnPlay` off for manual demos; enable it for regression checks or MCP-driven tests.

### SceneRecorder
Captures all `ReplayableActor` objects in the scene.
- **Sample Rate**: Samples per second (default 10 Hz).
- **Scene Type / Name / Description**: Metadata included in the timeline payload.

### DirectorApiClient
HTTP bridge to the backend.
- **Backend URL**: Base URL (no trailing slash).
- **LLM Provider / Model**: Optional overrides.
- **Director Hint**: Planning policy hint (default "auto").

### CinematicPlayer
Drives camera playback from the trajectory plan.
- **Target Camera**: Camera to control (defaults to Camera.main).
- **Playback Speed**: Time scale multiplier.
- **Transition Blend Time**: Smooth blend duration for non-cut transitions.
- Uses transition/path easing for less linear camera motion (`soft_cut`, `dissolve`, `whip_pan`, `ease_in_out`, etc.).

### ReplayableActor
Attach to any GameObject that should be recorded/replayed.
- **Actor ID**: Stable ID used in the timeline contract. Must be unique.
- **Category**: Scene-agnostic label (vehicle, character, prop, etc.).
- **Importance**: Weight for directing decisions (0-1).

### WaypointPath
Defines a path as an ordered list of local-space waypoints.
- **Waypoints**: Edit in Inspector or auto-populated from child transforms.
- **Loop**: Whether the path loops.
- Yellow gizmo lines are drawn in the Scene view.

### WaypointFollower
Moves a GameObject along a WaypointPath at constant speed.
- **Speed**: Units per second.
- **Align To Path**: Orient forward along path tangent.

## Data Flow

```
[Scene: ReplayableActors moving]
        |
    Start Recording
        |
    Stop Recording -> SceneTimelineData (objects_static, object_tracks, raw_events)
        |
    Generate Plan  -> POST /api/unity/temporal/generate
        |              {scene_id, intent, scene_timeline}
        |
    Response       <- {temporal_directing_plan, temporal_trajectory_plan, ...}
        |
    Play Cinematic -> Actors replay recorded motion
                      Camera follows trajectory timed_points
                      Shot switching per edit_decision_list
```

## Debug Artifacts
- `lastTimeline` / `lastTimelineJson` on SceneRecorder (Inspector).
- `lastRequestJson` / `lastResponseJson` on DirectorApiClient (Inspector).
- When `saveDebugFiles` is enabled, JSON files are saved to `Application.persistentDataPath`:
  - `last_temporal_request.json`
  - `last_temporal_response.json`

## Extending to Non-Racing Scenes
The system is scene-agnostic:
1. Add `ReplayableActor` to any moving objects (characters, drones, props).
2. Set meaningful `actorId`, `category`, and `importance`.
3. Movement can come from any source (animation, physics, AI navigation, scripted paths).
4. `WaypointFollower` is optional - only needed for the demo's deterministic paths.
5. The SceneRecorder captures whatever transforms exist at sample time.
6. Raw events are auto-generated from motion analysis (speed changes, direction changes, proximity interactions).
