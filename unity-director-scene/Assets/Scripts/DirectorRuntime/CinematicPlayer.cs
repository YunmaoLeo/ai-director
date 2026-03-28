using System.Collections.Generic;
using UnityEngine;

namespace DirectorRuntime
{
    /// <summary>
    /// Replays recorded actor motion and drives camera position/rotation/FOV
    /// according to the backend TemporalTrajectoryPlan.
    /// Supports multi-shot switching with transition awareness.
    /// </summary>
    public class CinematicPlayer : MonoBehaviour
    {
        [Header("References")]
        [Tooltip("Camera to drive. If null, Camera.main is used.")]
        public Camera targetCamera;

        [Header("Playback Settings")]
        [Tooltip("Speed multiplier for playback (1 = realtime).")]
        public float playbackSpeed = 1f;

        [Tooltip("Smooth camera transitions between shots (seconds).")]
        public float transitionBlendTime = 0.3f;

        public bool IsPlaying { get; private set; }
        public float PlaybackTime { get; private set; }
        public int CurrentShotIndex { get; private set; }
        public string CurrentShotId { get; private set; }

        private TemporalTrajectoryPlanData _plan;
        private TemporalDirectingPlanData _directingPlan;
        private ReplayableActor[] _actors;
        private float _startTime;
        private float _endTime;

        // Transition blending state
        private Vector3 _blendFromPos;
        private Quaternion _blendFromRot;
        private float _blendFromFov;
        private float _blendTimer;
        private bool _isBlending;
        private string _activeTransitionIn = "cut";

        /// <summary>
        /// Begins cinematic playback with the given trajectory plan.
        /// Actors will be driven to their recorded positions in sync.
        /// </summary>
        public void Play(
            TemporalTrajectoryPlanData trajectoryPlan,
            TemporalDirectingPlanData directingPlan,
            ReplayableActor[] actors)
        {
            if (trajectoryPlan == null || trajectoryPlan.trajectories == null ||
                trajectoryPlan.trajectories.Count == 0)
            {
                Debug.LogError("[CinematicPlayer] No trajectories in plan.");
                return;
            }

            _plan = trajectoryPlan;
            _directingPlan = directingPlan;
            _actors = actors;

            if (targetCamera == null)
                targetCamera = Camera.main;
            if (targetCamera == null)
            {
                Debug.LogError("[CinematicPlayer] No camera available.");
                return;
            }

            // Determine time range from plan
            _startTime = _plan.time_span != null ? _plan.time_span.start : _plan.trajectories[0].time_start;
            _endTime = _plan.time_span != null ? _plan.time_span.end :
                _plan.trajectories[_plan.trajectories.Count - 1].time_end;

            PlaybackTime = _startTime;
            CurrentShotIndex = 0;
            CurrentShotId = _plan.trajectories[0].shot_id;
            _isBlending = false;
            _activeTransitionIn = "cut";

            foreach (var a in _actors) a.BeginReplay();

            IsPlaying = true;
            Debug.Log($"[CinematicPlayer] Playback started. Duration: {_endTime - _startTime:F2}s, " +
                      $"Shots: {_plan.trajectories.Count}");
        }

        public void Stop()
        {
            if (!IsPlaying) return;
            IsPlaying = false;
            if (_actors != null)
                foreach (var a in _actors) a.EndReplay();
            Debug.Log("[CinematicPlayer] Playback stopped.");
        }

        void Update()
        {
            if (!IsPlaying) return;

            PlaybackTime += Time.deltaTime * playbackSpeed;

            if (PlaybackTime > _endTime)
            {
                Stop();
                Debug.Log("[CinematicPlayer] Playback finished.");
                return;
            }

            // Drive actors to recorded positions
            if (_actors != null)
                foreach (var a in _actors)
                    a.SetReplayTime(PlaybackTime);

            // Find active trajectory
            var traj = FindActiveTrajectory(PlaybackTime);
            if (traj == null) return;

            // Detect shot change
            if (traj.shot_id != CurrentShotId)
            {
                Debug.Log($"[CinematicPlayer] Shot switch: {CurrentShotId} -> {traj.shot_id} " +
                          $"(transition: {traj.transition_in}) at t={PlaybackTime:F2}");

                // Start blend if not a hard cut
                if (traj.transition_in != "cut" && traj.transition_in != "hard_cut" &&
                    traj.transition_in != "flash_cut")
                {
                    _blendFromPos = targetCamera.transform.position;
                    _blendFromRot = targetCamera.transform.rotation;
                    _blendFromFov = targetCamera.fieldOfView;
                    _blendTimer = 0;
                    _isBlending = true;
                    _activeTransitionIn = traj.transition_in ?? "cut";
                }
                else
                {
                    _isBlending = false;
                    _activeTransitionIn = traj.transition_in ?? "cut";
                }

                CurrentShotId = traj.shot_id;
                CurrentShotIndex = _plan.trajectories.IndexOf(traj);
            }

            // Interpolate camera from trajectory timed_points
            ApplyTrajectory(traj, PlaybackTime);
        }

        private TemporalShotTrajectory FindActiveTrajectory(float time)
        {
            // Find the trajectory whose time range contains the current time
            for (int i = _plan.trajectories.Count - 1; i >= 0; i--)
            {
                var t = _plan.trajectories[i];
                if (time >= t.time_start && time <= t.time_end)
                    return t;
            }
            // Fallback: find nearest
            TemporalShotTrajectory nearest = null;
            float bestDist = float.MaxValue;
            foreach (var t in _plan.trajectories)
            {
                float mid = (t.time_start + t.time_end) * 0.5f;
                float d = Mathf.Abs(time - mid);
                if (d < bestDist) { bestDist = d; nearest = t; }
            }
            return nearest;
        }

        private void ApplyTrajectory(TemporalShotTrajectory traj, float time)
        {
            if (traj.timed_points == null || traj.timed_points.Count == 0) return;

            Vector3 pos;
            Vector3 lookAt;
            float fov;

            if (traj.timed_points.Count == 1)
            {
                var pt = traj.timed_points[0];
                pos = pt.Position;
                lookAt = pt.LookAt;
                fov = pt.fov;
            }
            else
            {
                // Find bracketing points
                var points = traj.timed_points;

                if (time <= points[0].timestamp)
                {
                    pos = points[0].Position;
                    lookAt = points[0].LookAt;
                    fov = points[0].fov;
                }
                else if (time >= points[points.Count - 1].timestamp)
                {
                    var last = points[points.Count - 1];
                    pos = last.Position;
                    lookAt = last.LookAt;
                    fov = last.fov;
                }
                else
                {
                    // Interpolate
                    pos = Vector3.zero;
                    lookAt = Vector3.zero;
                    fov = 60f;
                    for (int i = 0; i < points.Count - 1; i++)
                    {
                        if (time >= points[i].timestamp && time <= points[i + 1].timestamp)
                        {
                            float t = (time - points[i].timestamp) /
                                      Mathf.Max(points[i + 1].timestamp - points[i].timestamp, 0.0001f);
                            float pathT = EvaluatePathBlend(traj.path_type, t);
                            pos = Vector3.Lerp(points[i].Position, points[i + 1].Position, pathT);
                            lookAt = Vector3.Lerp(points[i].LookAt, points[i + 1].LookAt, pathT);
                            fov = Mathf.Lerp(points[i].fov, points[i + 1].fov, pathT);
                            break;
                        }
                    }
                }
            }

            // Apply blend if transitioning
            if (_isBlending)
            {
                _blendTimer += Time.deltaTime;
                float rawBlend = Mathf.Clamp01(_blendTimer / Mathf.Max(transitionBlendTime, 0.01f));
                float blend = EvaluateTransitionBlend(_activeTransitionIn, rawBlend);
                pos = Vector3.Lerp(_blendFromPos, pos, blend);
                fov = Mathf.Lerp(_blendFromFov, fov, blend);
                var targetRot = Quaternion.LookRotation((lookAt - pos).normalized);

                if (_activeTransitionIn == "whip_pan")
                {
                    // Fast directional accent early in transition, then settle.
                    float whip = Mathf.Sin((1f - blend) * Mathf.PI) * 12f;
                    targetRot *= Quaternion.Euler(0f, whip, 0f);
                }

                targetCamera.transform.rotation = Quaternion.Slerp(_blendFromRot, targetRot, blend);
                targetCamera.transform.position = pos;
                targetCamera.fieldOfView = fov;

                if (blend >= 1f) _isBlending = false;
                return;
            }

            targetCamera.transform.position = pos;
            var dir = (lookAt - pos).normalized;
            if (dir.sqrMagnitude > 0.001f)
                targetCamera.transform.rotation = Quaternion.LookRotation(dir);
            targetCamera.fieldOfView = fov;
        }

        private static float EvaluatePathBlend(string pathType, float t)
        {
            if (string.IsNullOrEmpty(pathType))
                return t;

            switch (pathType.ToLowerInvariant())
            {
                case "ease_in":
                    return t * t;
                case "ease_out":
                    return 1f - (1f - t) * (1f - t);
                case "ease_in_out":
                case "spline":
                case "arc":
                    return Mathf.SmoothStep(0f, 1f, t);
                default:
                    return t;
            }
        }

        private static float EvaluateTransitionBlend(string transitionType, float t)
        {
            if (string.IsNullOrEmpty(transitionType))
                return t;

            switch (transitionType.ToLowerInvariant())
            {
                case "soft_cut":
                case "dissolve":
                case "match_move":
                    return Mathf.SmoothStep(0f, 1f, t);
                case "whip_pan":
                    return Mathf.Clamp01(t * t * (3f - 2f * t));
                case "ramp_in":
                    return t * t;
                default:
                    return t;
            }
        }

        /// <summary>
        /// Returns a summary string of the current playback state for debug UI.
        /// </summary>
        public string GetDebugStatus()
        {
            if (!IsPlaying) return "Idle";
            return $"Shot {CurrentShotIndex + 1}/{_plan?.trajectories?.Count ?? 0} " +
                   $"[{CurrentShotId}] t={PlaybackTime:F2}/{_endTime:F2}" +
                   (_isBlending ? " (blending)" : "");
        }
    }
}
