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
        private bool _isReplaying;
        private int _replayIndex;

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
        }

        public void CaptureSnapshot(float time)
        {
            var pos = transform.position;
            var vel = (pos - _prevPosition) / Mathf.Max(Time.deltaTime, 0.001f);
            recordedSnapshots.Add(new Snapshot
            {
                time = time,
                position = pos,
                rotation = transform.rotation,
                velocity = vel,
                visible = gameObject.activeInHierarchy
            });
            _prevPosition = pos;
        }

        // ── Replay ──

        public void BeginReplay()
        {
            _isReplaying = true;
            _replayIndex = 0;
        }

        public void EndReplay()
        {
            _isReplaying = false;
        }

        /// <summary>
        /// Sets transform to the interpolated recorded state at the given time.
        /// </summary>
        public void SetReplayTime(float time)
        {
            if (recordedSnapshots.Count == 0) return;

            // Clamp
            if (time <= recordedSnapshots[0].time)
            {
                ApplySnapshot(recordedSnapshots[0]);
                return;
            }
            if (time >= recordedSnapshots[recordedSnapshots.Count - 1].time)
            {
                ApplySnapshot(recordedSnapshots[recordedSnapshots.Count - 1]);
                return;
            }

            // Find bracketing snapshots
            for (int i = 0; i < recordedSnapshots.Count - 1; i++)
            {
                var a = recordedSnapshots[i];
                var b = recordedSnapshots[i + 1];
                if (time >= a.time && time <= b.time)
                {
                    float t = (time - a.time) / Mathf.Max(b.time - a.time, 0.0001f);
                    transform.position = Vector3.Lerp(a.position, b.position, t);
                    transform.rotation = Quaternion.Slerp(a.rotation, b.rotation, t);
                    return;
                }
            }
        }

        private void ApplySnapshot(Snapshot s)
        {
            transform.position = s.position;
            transform.rotation = s.rotation;
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
