using UnityEngine;

namespace DirectorRuntime
{
    /// <summary>
    /// Moves a GameObject along a WaypointPath at a configurable speed.
    /// Deterministic when using fixed speed (no randomness).
    /// </summary>
    [RequireComponent(typeof(ReplayableActor))]
    public class WaypointFollower : MonoBehaviour
    {
        public enum SpeedPattern
        {
            Constant,
            Aggressor,
            Chaser
        }

        [Tooltip("The path to follow.")]
        public WaypointPath path;

        [Tooltip("Movement speed in units/second.")]
        public float speed = 5f;

        [Tooltip("If true, orient transform forward along path tangent.")]
        public bool alignToPath = true;

        [Tooltip("Rotation smoothing speed.")]
        public float rotationSmooth = 10f;

        [Header("Dynamic Speed")]
        [Tooltip("Enable non-linear speed variation along the spline.")]
        public bool dynamicSpeed = true;

        [Tooltip("Driving style profile used to modulate speed.")]
        public SpeedPattern speedPattern = SpeedPattern.Constant;

        [Tooltip("How strongly the style profile affects speed.")]
        [Range(0f, 2f)]
        public float patternIntensity = 1.35f;

        [Tooltip("Uphill/downhill response. Positive values slow uphill and speed downhill.")]
        [Range(0f, 1f)]
        public float slopeInfluence = 0.42f;

        [Tooltip("Extra rhythmic pulse to avoid perfectly uniform movement.")]
        [Range(0f, 0.6f)]
        public float pulseAmplitude = 0.18f;

        [Tooltip("Pulse frequency in Hz.")]
        [Range(0.1f, 6f)]
        public float pulseFrequency = 1.8f;

        [Tooltip("Per-car pulse phase to desynchronize vehicles.")]
        [Range(0f, 6.28318f)]
        public float pulsePhase = 0f;

        [Tooltip("Clamp for final speed multiplier.")]
        public float minSpeedMultiplier = 0.35f;
        public float maxSpeedMultiplier = 2.4f;

        private float _distance;
        private bool _active;
        private float _currentSpeedMultiplier = 1f;
        private float _currentEffectiveSpeed;

        /// <summary>Current distance along path.</summary>
        public float Distance => _distance;
        public float CurrentSpeedMultiplier => _currentSpeedMultiplier;
        public float CurrentEffectiveSpeed => _currentEffectiveSpeed;

        void OnEnable()
        {
            // Always start idle on Play so actors wait for an explicit recording start.
            _active = false;
            _currentSpeedMultiplier = 0f;
            _currentEffectiveSpeed = 0f;
        }

        public void SetActive(bool active) => _active = active;

        /// <summary>Reset to start of path.</summary>
        public void ResetToStart()
        {
            _distance = 0;
            if (path != null)
            {
                transform.position = path.SamplePosition(0);
                if (alignToPath)
                    transform.forward = path.SampleForward(0);
            }
        }

        void Update()
        {
            if (!_active || path == null) return;

            _currentSpeedMultiplier = EvaluateSpeedMultiplier();
            _currentEffectiveSpeed = speed * _currentSpeedMultiplier;
            _distance += _currentEffectiveSpeed * Time.deltaTime;
            transform.position = path.SamplePosition(_distance);

            if (alignToPath)
            {
                var fwd = path.SampleForward(_distance);
                if (fwd.sqrMagnitude > 0.001f)
                {
                    var target = Quaternion.LookRotation(fwd);
                    transform.rotation = Quaternion.Slerp(transform.rotation, target,
                        Time.deltaTime * rotationSmooth);
                }
            }
        }

        private float EvaluateSpeedMultiplier()
        {
            if (!dynamicSpeed || speedPattern == SpeedPattern.Constant)
                return 1f;

            float pathLen = Mathf.Max(0.001f, path.TotalLength);
            float normalized = Mathf.Repeat(_distance, pathLen) / pathLen;

            float profile = speedPattern == SpeedPattern.Aggressor
                ? EvaluateAggressor(normalized)
                : EvaluateChaser(normalized);

            // Blend profile toward 1.0 using intensity.
            profile = Mathf.Lerp(1f, profile, Mathf.Clamp01(patternIntensity));

            // Ups/downs influence pacing.
            float slopeY = path.SampleForward(_distance).y;
            float slopeFactor = 1f - Mathf.Clamp(slopeY, -0.7f, 0.7f) * slopeInfluence;

            float pulse = 1f + Mathf.Sin(Time.time * pulseFrequency + pulsePhase) * pulseAmplitude;
            float combined = profile * slopeFactor * pulse;
            return Mathf.Clamp(combined, minSpeedMultiplier, maxSpeedMultiplier);
        }

        private static float EvaluateAggressor(float t)
        {
            float m = 1f;
            m *= Bump(t, 0.02f, 0.18f, 1.70f);
            m *= Bump(t, 0.18f, 0.32f, 0.72f);
            m *= Bump(t, 0.33f, 0.55f, 1.58f);
            m *= Bump(t, 0.56f, 0.74f, 0.66f);
            m *= Bump(t, 0.75f, 0.92f, 1.86f);
            return m;
        }

        private static float EvaluateChaser(float t)
        {
            float m = 1f;
            m *= Bump(t, 0.02f, 0.16f, 0.74f);
            m *= Bump(t, 0.18f, 0.40f, 1.42f);
            m *= Bump(t, 0.41f, 0.58f, 0.78f);
            m *= Bump(t, 0.59f, 0.84f, 1.94f);
            m *= Bump(t, 0.85f, 0.98f, 0.72f);
            return m;
        }

        private static float Bump(float t, float start, float end, float factor)
        {
            if (start >= end || t <= start || t >= end)
                return 1f;

            float x = Mathf.InverseLerp(start, end, t);
            float smooth = Mathf.SmoothStep(0f, 1f, x);
            float bell = 1f - Mathf.Abs(smooth * 2f - 1f);
            return Mathf.Lerp(1f, factor, bell);
        }
    }
}
