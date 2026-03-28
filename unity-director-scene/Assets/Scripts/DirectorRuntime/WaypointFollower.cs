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
        [Tooltip("The path to follow.")]
        public WaypointPath path;

        [Tooltip("Movement speed in units/second.")]
        public float speed = 5f;

        [Tooltip("If true, orient transform forward along path tangent.")]
        public bool alignToPath = true;

        [Tooltip("Rotation smoothing speed.")]
        public float rotationSmooth = 10f;

        private float _distance;
        private bool _active = true;

        /// <summary>Current distance along path.</summary>
        public float Distance => _distance;

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

            _distance += speed * Time.deltaTime;
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
    }
}
