using Unity.Cinemachine;
using UnityEngine;
using UnityEngine.Rendering;
using UnityEngine.Rendering.Universal;
using CubePeople;

namespace DirectorRuntime
{
    /// <summary>
    /// Replays recorded actor motion and drives a Cinemachine-backed camera state
    /// according to the backend TemporalTrajectoryPlan.
    /// Supports multi-shot switching, lens changes, and URP depth-of-field playback.
    /// </summary>
    public class CinematicPlayer : MonoBehaviour
    {
        [Header("References")]
        [Tooltip("Camera to drive. If null, Camera.main is used.")]
        public Camera targetCamera;

        [Tooltip("Optional global volume. If null, the first active Volume in the scene is used.")]
        public Volume globalVolume;

        [Header("Playback Settings")]
        [Tooltip("Speed multiplier for playback (1 = realtime).")]
        public float playbackSpeed = 1f;

        [Tooltip("Smooth camera transitions between shots (seconds).")]
        public float transitionBlendTime = 0.3f;

        [Tooltip("Drive the render camera through Cinemachine instead of direct transform writes.")]
        public bool useCinemachine = true;

        [Tooltip("Apply URP Depth Of Field during cinematic playback.")]
        public bool enableDepthOfField = true;

        [Tooltip("Default physical sensor size for cinematic lens calculations.")]
        public Vector2 defaultSensorSize = new Vector2(36f, 24f);

        public bool IsPlaying { get; private set; }
        public float PlaybackTime { get; private set; }
        public int CurrentShotIndex { get; private set; }
        public string CurrentShotId { get; private set; }

        private const string RuntimeCameraName = "AI Director Cinemachine Camera";

        private TemporalTrajectoryPlanData _plan;
        private TemporalDirectingPlanData _directingPlan;
        private ReplayableActor[] _actors;
        private float _startTime;
        private float _endTime;

        private CinemachineBrain _brain;
        private CinemachineCamera _cinemachineCamera;
        private CinemachineBasicMultiChannelPerlin _noise;
        private NoiseSettings _noiseProfile;
        private VolumeProfile _runtimeVolumeProfile;
        private DepthOfField _depthOfField;
        private FollowTarget _suspendedFollowTarget;
        private bool _suspendedFollowTargetWasEnabled;

        private CameraFrameState _currentState;
        private CameraFrameState _blendFromState;
        private bool _hasCurrentState;

        private float _blendTimer;
        private bool _isBlending;
        private string _activeTransitionIn = "cut";

        private struct CameraFrameState
        {
            public Vector3 position;
            public Quaternion rotation;
            public float fov;
            public float dutch;
            public float focusDistance;
            public float aperture;
            public float focalLength;
            public Vector2 lensShift;
        }

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

            if (!EnsureRuntimeBindings())
                return;

            SuspendGameplayCameraDrivers();

            _startTime = _plan.time_span != null ? _plan.time_span.start : _plan.trajectories[0].time_start;
            _endTime = _plan.time_span != null ? _plan.time_span.end :
                _plan.trajectories[_plan.trajectories.Count - 1].time_end;

            PlaybackTime = _startTime;
            CurrentShotIndex = 0;
            CurrentShotId = _plan.trajectories[0].shot_id;
            _isBlending = false;
            _activeTransitionIn = "cut";
            _currentState = CaptureCurrentState();
            _blendFromState = _currentState;
            _hasCurrentState = true;

            if (_actors != null)
                foreach (var actor in _actors)
                    actor.BeginReplay();

            IsPlaying = true;
            Debug.Log($"[CinematicPlayer] Playback started. Duration: {_endTime - _startTime:F2}s, " +
                      $"Shots: {_plan.trajectories.Count}, Cinemachine={(useCinemachine ? "on" : "off")}, " +
                      $"DepthOfField={(enableDepthOfField ? "on" : "off")}");
        }

        public void Stop()
        {
            if (!IsPlaying)
                return;

            IsPlaying = false;
            if (_actors != null)
            {
                foreach (var actor in _actors)
                    actor.EndReplay();
            }

            ApplyRigMetadata(null);
            ResumeGameplayCameraDrivers();
            Debug.Log("[CinematicPlayer] Playback stopped.");
        }

        private void Update()
        {
            if (!IsPlaying)
                return;

            PlaybackTime += Time.deltaTime * playbackSpeed;

            if (PlaybackTime > _endTime)
            {
                Stop();
                Debug.Log("[CinematicPlayer] Playback finished.");
                return;
            }

            if (_actors != null)
            {
                foreach (var actor in _actors)
                    actor.SetReplayTime(PlaybackTime);
            }

            var traj = FindActiveTrajectory(PlaybackTime);
            if (traj == null)
                return;

            ApplyRigMetadata(traj);

            if (traj.shot_id != CurrentShotId)
            {
                Debug.Log($"[CinematicPlayer] Shot switch: {CurrentShotId} -> {traj.shot_id} " +
                          $"(transition: {traj.transition_in}) at t={PlaybackTime:F2}");

                if (!IsHardCut(traj.transition_in))
                {
                    _blendFromState = _hasCurrentState ? _currentState : CaptureCurrentState();
                    _blendTimer = 0f;
                    _isBlending = true;
                    _activeTransitionIn = string.IsNullOrEmpty(traj.transition_in) ? "cut" : traj.transition_in;
                }
                else
                {
                    _isBlending = false;
                    _activeTransitionIn = string.IsNullOrEmpty(traj.transition_in) ? "cut" : traj.transition_in;
                }

                CurrentShotId = traj.shot_id;
                CurrentShotIndex = _plan.trajectories.IndexOf(traj);
            }

            ApplyTrajectory(traj, PlaybackTime);
        }

        private bool EnsureRuntimeBindings()
        {
            if (targetCamera == null)
                targetCamera = Camera.main;
            if (targetCamera == null)
            {
                Debug.LogError("[CinematicPlayer] No camera available.");
                return false;
            }

            targetCamera.usePhysicalProperties = true;

            if (useCinemachine)
            {
                _brain = targetCamera.GetComponent<CinemachineBrain>();
                if (_brain == null)
                    _brain = targetCamera.gameObject.AddComponent<CinemachineBrain>();

                _brain.DefaultBlend = new CinemachineBlendDefinition(
                    CinemachineBlendDefinition.Styles.EaseInOut,
                    Mathf.Max(0.05f, transitionBlendTime));

                if (_cinemachineCamera == null)
                {
                    _cinemachineCamera = GetComponentInChildren<CinemachineCamera>(true);
                    if (_cinemachineCamera == null)
                    {
                        var rigGo = new GameObject(RuntimeCameraName);
                        rigGo.transform.SetParent(transform, false);
                        _cinemachineCamera = rigGo.AddComponent<CinemachineCamera>();
                    }
                }

                _cinemachineCamera.Priority = 100;
                _cinemachineCamera.enabled = true;
                _cinemachineCamera.gameObject.hideFlags = HideFlags.None;
                _cinemachineCamera.Target = default;

                if (_noise == null)
                {
                    _noise = _cinemachineCamera.GetComponent<CinemachineBasicMultiChannelPerlin>();
                    if (_noise == null)
                        _noise = _cinemachineCamera.gameObject.AddComponent<CinemachineBasicMultiChannelPerlin>();
                }

                if (_noiseProfile == null)
                    _noiseProfile = CreateRuntimeNoiseProfile();
                _noise.NoiseProfile = _noiseProfile;
                _noise.enabled = false;
            }

            ResolveDepthOfField();
            return true;
        }

        private void SuspendGameplayCameraDrivers()
        {
            if (targetCamera == null)
                return;

            _suspendedFollowTarget = targetCamera.GetComponent<FollowTarget>();
            if (_suspendedFollowTarget == null)
                return;

            _suspendedFollowTargetWasEnabled = _suspendedFollowTarget.enabled;
            if (_suspendedFollowTargetWasEnabled)
                _suspendedFollowTarget.enabled = false;
        }

        private void ResumeGameplayCameraDrivers()
        {
            if (_suspendedFollowTarget == null)
                return;

            _suspendedFollowTarget.enabled = _suspendedFollowTargetWasEnabled;
            _suspendedFollowTarget = null;
            _suspendedFollowTargetWasEnabled = false;
        }

        private void ResolveDepthOfField()
        {
            if (!enableDepthOfField)
            {
                _depthOfField = null;
                return;
            }

            if (globalVolume == null)
            {
                var volumes = FindObjectsOfType<Volume>(true);
                foreach (var volume in volumes)
                {
                    if (!volume.isGlobal)
                        continue;
                    globalVolume = volume;
                    break;
                }
            }

            if (globalVolume == null)
            {
                Debug.LogWarning("[CinematicPlayer] No global URP Volume found. Depth Of Field playback will be skipped.");
                return;
            }

            if (_runtimeVolumeProfile == null)
            {
                if (globalVolume.profile != null)
                {
                    _runtimeVolumeProfile = globalVolume.profile;
                }
                else if (globalVolume.sharedProfile != null)
                {
                    _runtimeVolumeProfile = Instantiate(globalVolume.sharedProfile);
                    _runtimeVolumeProfile.name = $"{globalVolume.sharedProfile.name} (Runtime Copy)";
                    globalVolume.profile = _runtimeVolumeProfile;
                }
                else
                {
                    _runtimeVolumeProfile = ScriptableObject.CreateInstance<VolumeProfile>();
                    _runtimeVolumeProfile.name = "AI Director Runtime Volume";
                    globalVolume.profile = _runtimeVolumeProfile;
                }
            }

            if (!_runtimeVolumeProfile.TryGet(out _depthOfField))
                _depthOfField = _runtimeVolumeProfile.Add<DepthOfField>(true);

            _depthOfField.active = true;
            _depthOfField.mode.overrideState = true;
            _depthOfField.mode.value = DepthOfFieldMode.Bokeh;
            _depthOfField.focusDistance.overrideState = true;
            _depthOfField.aperture.overrideState = true;
            _depthOfField.focalLength.overrideState = true;
        }

        private TemporalShotTrajectory FindActiveTrajectory(float time)
        {
            for (int i = _plan.trajectories.Count - 1; i >= 0; i--)
            {
                var trajectory = _plan.trajectories[i];
                if (time >= trajectory.time_start && time <= trajectory.time_end)
                    return trajectory;
            }

            TemporalShotTrajectory nearest = null;
            float bestDistance = float.MaxValue;
            foreach (var trajectory in _plan.trajectories)
            {
                float mid = (trajectory.time_start + trajectory.time_end) * 0.5f;
                float distance = Mathf.Abs(time - mid);
                if (distance < bestDistance)
                {
                    bestDistance = distance;
                    nearest = trajectory;
                }
            }

            return nearest;
        }

        private void ApplyTrajectory(TemporalShotTrajectory traj, float time)
        {
            if (traj.timed_points == null || traj.timed_points.Count == 0)
                return;

            var targetState = SampleTrajectory(traj, time);

            if (_isBlending)
            {
                _blendTimer += Time.deltaTime;
                float rawBlend = Mathf.Clamp01(_blendTimer / Mathf.Max(transitionBlendTime, 0.01f));
                float blend = EvaluateTransitionBlend(_activeTransitionIn, rawBlend);
                targetState = LerpState(_blendFromState, targetState, blend);
                if (blend >= 1f)
                    _isBlending = false;
            }

            ApplyCameraState(targetState);
            _currentState = targetState;
            _hasCurrentState = true;
        }

        private CameraFrameState SampleTrajectory(TemporalShotTrajectory traj, float time)
        {
            if (traj.timed_points.Count == 1)
                return BuildState(traj.timed_points[0]);

            var points = traj.timed_points;
            if (time <= points[0].timestamp)
                return BuildState(points[0]);
            if (time >= points[points.Count - 1].timestamp)
                return BuildState(points[points.Count - 1]);

            for (int i = 0; i < points.Count - 1; i++)
            {
                if (time < points[i].timestamp || time > points[i + 1].timestamp)
                    continue;

                float t = (time - points[i].timestamp) /
                          Mathf.Max(points[i + 1].timestamp - points[i].timestamp, 0.0001f);
                float blendT = EvaluatePathBlend(traj.path_type, t);
                return LerpState(BuildState(points[i]), BuildState(points[i + 1]), blendT);
            }

            return BuildState(points[points.Count - 1]);
        }

        private CameraFrameState BuildState(TimedTrajectoryPoint point)
        {
            Vector3 position = point.Position;
            Vector3 lookAt = point.LookAt;
            Vector3 direction = lookAt - position;
            Quaternion rotation = direction.sqrMagnitude > 0.0001f
                ? Quaternion.LookRotation(direction.normalized)
                : (_hasCurrentState ? _currentState.rotation : targetCamera.transform.rotation);

            return new CameraFrameState
            {
                position = position,
                rotation = rotation,
                fov = point.fov,
                dutch = point.dutch,
                focusDistance = point.focus_distance,
                aperture = point.aperture,
                focalLength = point.focal_length,
                lensShift = point.LensShift,
            };
        }

        private void ApplyCameraState(CameraFrameState state)
        {
            if (useCinemachine && _cinemachineCamera != null)
            {
                _cinemachineCamera.transform.SetPositionAndRotation(state.position, state.rotation);

                var lens = _cinemachineCamera.Lens;
                lens.ModeOverride = LensSettings.OverrideModes.Physical;
                lens.FieldOfView = Mathf.Clamp(state.fov, 20f, 110f);
                lens.Dutch = state.dutch;
                lens.PhysicalProperties.SensorSize = defaultSensorSize;
                lens.PhysicalProperties.FocusDistance = Mathf.Max(0.1f, state.focusDistance);
                lens.PhysicalProperties.Aperture = Mathf.Clamp(state.aperture, 1f, 16f);
                lens.PhysicalProperties.LensShift = state.lensShift;
                _cinemachineCamera.Lens = lens;
            }
            else
            {
                targetCamera.transform.SetPositionAndRotation(state.position, state.rotation);
                targetCamera.fieldOfView = Mathf.Clamp(state.fov, 20f, 110f);
                targetCamera.usePhysicalProperties = true;
                targetCamera.focusDistance = Mathf.Max(0.1f, state.focusDistance);
                targetCamera.aperture = Mathf.Clamp(state.aperture, 1f, 16f);
                targetCamera.lensShift = state.lensShift;
            }

            if (_depthOfField != null && enableDepthOfField)
            {
                _depthOfField.active = true;
                _depthOfField.mode.value = DepthOfFieldMode.Bokeh;
                _depthOfField.focusDistance.value = Mathf.Max(0.1f, state.focusDistance);
                _depthOfField.aperture.value = Mathf.Clamp(state.aperture, 1f, 32f);
                _depthOfField.focalLength.value = Mathf.Clamp(state.focalLength, 1f, 300f);
            }
        }

        private void ApplyRigMetadata(TemporalShotTrajectory traj)
        {
            if (_noise == null)
                return;

            if (traj == null)
            {
                _noise.enabled = false;
                return;
            }

            string rigStyle = string.IsNullOrEmpty(traj.rig_style) ? "default" : traj.rig_style.ToLowerInvariant();
            if (rigStyle == "handheld")
            {
                _noise.enabled = true;
                _noise.NoiseProfile = _noiseProfile;
                _noise.AmplitudeGain = Mathf.Max(0.1f, traj.noise_amplitude);
                _noise.FrequencyGain = Mathf.Max(0.2f, traj.noise_frequency);
            }
            else if (rigStyle == "steadicam")
            {
                _noise.enabled = true;
                _noise.NoiseProfile = _noiseProfile;
                _noise.AmplitudeGain = 0.12f;
                _noise.FrequencyGain = 0.65f;
            }
            else
            {
                _noise.enabled = false;
            }
        }

        private CameraFrameState CaptureCurrentState()
        {
            if (targetCamera == null)
                return default;

            return new CameraFrameState
            {
                position = targetCamera.transform.position,
                rotation = targetCamera.transform.rotation,
                fov = targetCamera.fieldOfView,
                dutch = 0f,
                focusDistance = Mathf.Max(0.1f, targetCamera.focusDistance),
                aperture = Mathf.Clamp(targetCamera.aperture, 1f, 16f),
                focalLength = Mathf.Max(1f, targetCamera.focalLength),
                lensShift = targetCamera.lensShift,
            };
        }

        private static CameraFrameState LerpState(CameraFrameState a, CameraFrameState b, float t)
        {
            return new CameraFrameState
            {
                position = Vector3.Lerp(a.position, b.position, t),
                rotation = Quaternion.Slerp(a.rotation, b.rotation, t),
                fov = Mathf.Lerp(a.fov, b.fov, t),
                dutch = Mathf.Lerp(a.dutch, b.dutch, t),
                focusDistance = Mathf.Lerp(a.focusDistance, b.focusDistance, t),
                aperture = Mathf.Lerp(a.aperture, b.aperture, t),
                focalLength = Mathf.Lerp(a.focalLength, b.focalLength, t),
                lensShift = Vector2.Lerp(a.lensShift, b.lensShift, t),
            };
        }

        private static bool IsHardCut(string transitionType)
        {
            if (string.IsNullOrEmpty(transitionType))
                return true;

            switch (transitionType.ToLowerInvariant())
            {
                case "cut":
                case "hard_cut":
                case "flash_cut":
                    return true;
                default:
                    return false;
            }
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
                case "smooth":
                case "match_cut":
                    return Mathf.SmoothStep(0f, 1f, t);
                case "whip_pan":
                case "whip":
                    return Mathf.Clamp01(t * t * (3f - 2f * t));
                case "ramp_in":
                    return t * t;
                default:
                    return t;
            }
        }

        private static NoiseSettings CreateRuntimeNoiseProfile()
        {
            var profile = ScriptableObject.CreateInstance<NoiseSettings>();
            profile.name = "AI Director Runtime Noise";

            profile.PositionNoise = new[]
            {
                MakeNoiseLayer(0.35f, 0.18f, 0.18f, 0.15f),
                MakeNoiseLayer(1.1f, 0.05f, 0.08f, 0.04f),
                MakeNoiseLayer(2.4f, 0.02f, 0.03f, 0.015f),
            };
            profile.OrientationNoise = new[]
            {
                MakeNoiseLayer(0.5f, 0.5f, 0.8f, 0.35f),
                MakeNoiseLayer(1.6f, 0.18f, 0.3f, 0.12f),
            };
            return profile;
        }

        private static NoiseSettings.TransformNoiseParams MakeNoiseLayer(
            float frequency,
            float ampX,
            float ampY,
            float ampZ)
        {
            return new NoiseSettings.TransformNoiseParams
            {
                X = new NoiseSettings.NoiseParams { Frequency = frequency, Amplitude = ampX, Constant = false },
                Y = new NoiseSettings.NoiseParams { Frequency = frequency * 1.13f, Amplitude = ampY, Constant = false },
                Z = new NoiseSettings.NoiseParams { Frequency = frequency * 0.91f, Amplitude = ampZ, Constant = false },
            };
        }

        /// <summary>
        /// Returns a summary string of the current playback state for debug UI.
        /// </summary>
        public string GetDebugStatus()
        {
            if (!IsPlaying)
                return "Idle";

            return $"Shot {CurrentShotIndex + 1}/{_plan?.trajectories?.Count ?? 0} " +
                   $"[{CurrentShotId}] t={PlaybackTime:F2}/{_endTime:F2}" +
                   (_isBlending ? " (blending)" : "");
        }
    }
}
