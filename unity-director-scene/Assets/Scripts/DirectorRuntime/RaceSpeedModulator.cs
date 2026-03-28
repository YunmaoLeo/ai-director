using UnityEngine;

namespace DirectorRuntime
{
    /// <summary>
    /// Adds non-linear speed behavior on top of WaypointFollower so vehicles
    /// produce stronger pacing contrast and overtake opportunities.
    /// </summary>
    [RequireComponent(typeof(WaypointFollower))]
    public class RaceSpeedModulator : MonoBehaviour
    {
        public enum DriverStyle
        {
            Aggressor,
            Chaser
        }

        [Header("Style")]
        public DriverStyle style = DriverStyle.Aggressor;

        [Tooltip("If <= 0, capture follower speed at Start as baseline.")]
        public float baselineSpeed = -1f;

        [Tooltip("Global style intensity multiplier.")]
        [Range(0.5f, 2.0f)]
        public float styleIntensity = 1.0f;

        [Header("Pulse")]
        [Range(0f, 0.5f)] public float pulseAmplitude = 0.12f;
        [Range(0.2f, 4f)] public float pulseFrequency = 1.2f;
        [Range(0f, 6.28f)] public float pulsePhase = 0f;

        [Header("Limits")]
        public float minSpeedMultiplier = 0.55f;
        public float maxSpeedMultiplier = 1.85f;
        public float smoothing = 6f;

        private WaypointFollower _follower;

        void Start()
        {
            _follower = GetComponent<WaypointFollower>();
            if (_follower != null && baselineSpeed <= 0f)
                baselineSpeed = Mathf.Max(0.1f, _follower.speed);
        }

        void Update()
        {
            if (_follower == null || _follower.path == null || baselineSpeed <= 0f)
                return;

            float pathLen = Mathf.Max(0.001f, _follower.path.TotalLength);
            float normalized = Mathf.Repeat(_follower.Distance, pathLen) / pathLen;

            float styleFactor = style == DriverStyle.Aggressor
                ? AggressorProfile(normalized)
                : ChaserProfile(normalized);

            // Speed reacts to gradient: uphill slows, downhill accelerates.
            float slopeY = _follower.path.SampleForward(_follower.Distance).y;
            float slopeFactor = 1f - Mathf.Clamp(slopeY, -0.5f, 0.5f) * 0.35f;

            float pulse = 1f + Mathf.Sin(Time.time * pulseFrequency + pulsePhase) * pulseAmplitude;
            float multiplier = styleFactor * slopeFactor * pulse * styleIntensity;
            multiplier = Mathf.Clamp(multiplier, minSpeedMultiplier, maxSpeedMultiplier);

            float targetSpeed = baselineSpeed * multiplier;
            _follower.speed = Mathf.Lerp(_follower.speed, targetSpeed, Time.deltaTime * smoothing);
        }

        private static float AggressorProfile(float t)
        {
            float m = 1f;
            m *= Bump(t, 0.07f, 0.18f, 1.35f); // hard launch
            m *= Bump(t, 0.40f, 0.58f, 1.28f); // attack window
            m *= Bump(t, 0.74f, 0.88f, 0.72f); // heavy brake zone
            m *= Bump(t, 0.90f, 0.98f, 1.22f); // exit burst
            return m;
        }

        private static float ChaserProfile(float t)
        {
            float m = 1f;
            m *= Bump(t, 0.06f, 0.16f, 0.82f); // measured setup
            m *= Bump(t, 0.34f, 0.52f, 1.18f); // close gap
            m *= Bump(t, 0.52f, 0.68f, 1.45f); // overtake push
            m *= Bump(t, 0.82f, 0.93f, 0.86f); // stabilize
            m *= Bump(t, 0.93f, 0.99f, 1.32f); // final dive
            return m;
        }

        private static float Bump(float t, float start, float end, float factor)
        {
            if (start >= end)
                return 1f;

            if (t <= start || t >= end)
                return 1f;

            float x = Mathf.InverseLerp(start, end, t);
            float shape = Mathf.SmoothStep(0f, 1f, x);
            float bell = 1f - Mathf.Abs(shape * 2f - 1f);
            return Mathf.Lerp(1f, factor, bell);
        }
    }
}
