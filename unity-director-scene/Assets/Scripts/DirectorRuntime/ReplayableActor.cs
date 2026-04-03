using System.Collections.Generic;
using UnityEngine;

namespace DirectorRuntime
{
    /// <summary>
    /// Marks a GameObject as a recordable/replayable actor for the director system.
    /// Stores recorded snapshots and can replay them deterministically.
    /// </summary>
    public class ReplayableActor : MonoBehaviour
    {
        [Header("Identity")]
        [Tooltip("Stable ID used across timeline, events, and backend contract.")]
        public string actorId;
        [Tooltip("Human-readable display name.")]
        public string actorName;
        [Tooltip("Scene-agnostic category (e.g. vehicle, character, prop).")]
        public string category = "object";
        [Tooltip("Free-text description of this actor for LLM context. Auto-generated if blank.")]
        [TextArea(1, 3)]
        public string description = "";
        [Tooltip("Importance weight for directing (0-1).")]
        [Range(0f, 1f)]
        public float importance = 0.5f;
        public List<string> tags = new List<string>();

        // Recorded snapshot buffer
        public struct Snapshot
        {
            public float time;
            public Vector3 position;
            public Quaternion rotation;
            public Vector3 velocity;
            public bool visible;
        }

        [HideInInspector] public List<Snapshot> recordedSnapshots = new List<Snapshot>();

        private Vector3 _prevPosition;
        private float _prevSnapshotTime;
        private bool _isReplaying;
        private int _replayIndex;
        private Vector3 _currentReplayVelocity;

        public bool IsReplaying => _isReplaying;
        public Vector3 CurrentReplayVelocity => _currentReplayVelocity;

        void Awake()
        {
            if (string.IsNullOrEmpty(actorId))
                actorId = gameObject.name + "_" + gameObject.GetInstanceID().ToString("X");
            if (string.IsNullOrEmpty(actorName))
                actorName = gameObject.name;
        }

        // ── Recording ──

        public void BeginRecording()
        {
            recordedSnapshots.Clear();
            _prevPosition = transform.position;
            _prevSnapshotTime = -1f;
        }

        public void CaptureSnapshot(float time)
        {
            var pos = transform.position;
            float dt = _prevSnapshotTime >= 0f ? (time - _prevSnapshotTime) : 0f;
            var vel = dt > 0.001f ? (pos - _prevPosition) / dt : Vector3.zero;
            recordedSnapshots.Add(new Snapshot
            {
                time = time,
                position = pos,
                rotation = transform.rotation,
                velocity = vel,
                visible = gameObject.activeInHierarchy
            });
            _prevPosition = pos;
            _prevSnapshotTime = time;
        }

        // ── Replay ──

        public void BeginReplay()
        {
            _isReplaying = true;
            _replayIndex = 0;
            _currentReplayVelocity = Vector3.zero;
        }

        public void EndReplay()
        {
            _isReplaying = false;
            _currentReplayVelocity = Vector3.zero;
        }

        /// <summary>
        /// Sets transform to the interpolated recorded state at the given time.
        /// Uses cached _replayIndex for O(1) amortized lookup during sequential playback.
        /// </summary>
        public void SetReplayTime(float time)
        {
            if (recordedSnapshots.Count == 0) return;

            if (time <= recordedSnapshots[0].time)
            {
                ApplySnapshot(recordedSnapshots[0]);
                _replayIndex = 0;
                return;
            }
            if (time >= recordedSnapshots[recordedSnapshots.Count - 1].time)
            {
                ApplySnapshot(recordedSnapshots[recordedSnapshots.Count - 1]);
                _replayIndex = Mathf.Max(0, recordedSnapshots.Count - 2);
                return;
            }

            // Start search from cached index for sequential access
            int start = Mathf.Clamp(_replayIndex, 0, recordedSnapshots.Count - 2);

            // If cached position is ahead of time, reset to beginning
            if (recordedSnapshots[start].time > time)
                start = 0;

            for (int i = start; i < recordedSnapshots.Count - 1; i++)
            {
                var a = recordedSnapshots[i];
                var b = recordedSnapshots[i + 1];
                if (time >= a.time && time <= b.time)
                {
                    float t = (time - a.time) / Mathf.Max(b.time - a.time, 0.0001f);
                    transform.position = Vector3.Lerp(a.position, b.position, t);
                    transform.rotation = Quaternion.Slerp(a.rotation, b.rotation, t);
                    _currentReplayVelocity = Vector3.Lerp(a.velocity, b.velocity, t);
                    _replayIndex = i;
                    return;
                }
            }
        }

        private void ApplySnapshot(Snapshot s)
        {
            transform.position = s.position;
            transform.rotation = s.rotation;
            _currentReplayVelocity = s.velocity;
        }

        /// <summary>
        /// Returns the bounding size of this actor based on its renderer or collider.
        /// </summary>
        public Vector3 GetSize()
        {
            var r = GetComponentInChildren<Renderer>();
            if (r != null) return r.bounds.size;
            var c = GetComponentInChildren<Collider>();
            if (c != null) return c.bounds.size;
            return Vector3.one;
        }
    }
}
