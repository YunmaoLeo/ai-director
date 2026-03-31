# End-to-End Verification Checklist

## Pre-flight
- [ ] Unity project opens without compilation errors.
- [ ] Backend is running at configured URL (default `http://localhost:8000`).
- [ ] Backend `POST /api/unity/temporal/generate` is reachable (test with `curl -X POST http://localhost:8000/api/unity/temporal/generate -H "Content-Type: application/json" -d '{}'` - should return a validation error, not a connection error).

## Scene Setup
- [ ] Run **AI Director > Setup Demo Scene** from menu bar.
- [ ] Scene contains: DemoWorld, PathA, PathB, CarA (stylized red), CarB (stylized blue), DirectorController, Main Camera, Directional Light.
- [ ] Yellow gizmo lines visible in Scene view for both paths.
- [ ] DirectorController has components: SceneRecorder, DirectorApiClient, CinematicPlayer, DirectorController.

## Recording
- [ ] Enter Play Mode. Both cars remain still before recording starts.
- [ ] Click **Start Recording**. Status shows "Recording..." and red timer counts up.
- [ ] After clicking **Start Recording**, both cars begin moving along their waypoint loops.
- [ ] Wait 5-10 seconds to capture meaningful motion data.
- [ ] Click **Stop Recording**. Status shows duration and "Ready to generate."
- [ ] Console logs show: recording started, recording stopped, timeline built with object/track/event counts.

## Plan Generation
- [ ] Click **Generate Plan**. Status shows "Sending to backend...".
- [ ] Console log confirms request sent with scene_id and intent.
- [ ] After backend responds, status shows policy, shot count, trajectory count.
- [ ] `lastResponseJson` on DirectorApiClient is populated (check Inspector in pause).
- [ ] If `saveDebugFiles` is on, JSON files exist in `Application.persistentDataPath`.

## Cinematic Playback
- [ ] Click **Play Cinematic**. Status shows playback progress.
- [ ] Cars replay their recorded positions (not live movement).
- [ ] Camera moves according to returned trajectory (position, look-at, FOV change).
- [ ] Shot transitions are visible in the console log (shot switch messages).
- [ ] Playback ends automatically when timeline completes. Status shows "Cinematic finished."

## Optional Automated Run
- [ ] Add/enable `AutomatedDemoRunner` on `DirectorController` (`runOnPlay = true`).
- [ ] Enter Play Mode and wait for log: `[AutomatedDemoRunner] PASS: full demo flow completed.`

## Contract Compliance
- [ ] `lastRequestJson` contains valid `scene_timeline` with: scene_id, scene_name, scene_type, bounds, time_span, objects_static, object_tracks, raw_events, events (mirror), semantic_events (empty).
- [ ] `raw_events` include appear, speed_change, direction_change, and/or interaction events.
- [ ] Object IDs are consistent across objects_static, object_tracks, and events.
- [ ] Response contains `temporal_directing_plan` with shots and beats.
- [ ] Response contains `temporal_trajectory_plan` with trajectories containing timed_points.

## Error Handling
- [ ] If backend is offline, clicking Generate Plan shows an error message in the UI status (not a crash).
- [ ] If no recording exists, Generate Plan shows "No recording available."
- [ ] If no plan exists, Play Cinematic shows "No plan available."
