using System.Collections.Generic;
using UnityEngine;

namespace DirectorRuntime
{
    /// <summary>
    /// Smooth waypoint-based path using Catmull-Rom spline interpolation.
    /// Provides deterministic position sampling by distance along the path.
    /// Optionally renders the path at runtime via LineRenderer.
    /// </summary>
    public class WaypointPath : MonoBehaviour
    {
        [Tooltip("Ordered control points in local space. If empty, child transforms are used.")]
        public List<Vector3> waypoints = new List<Vector3>();

        [Tooltip("If true, path loops back to start.")]
        public bool loop = true;

        [Header("Spline Quality")]
        [Tooltip("Subdivisions per segment for the baked spline curve.")]
        [Range(4, 32)]
        public int subdivisionsPerSegment = 12;

        [Header("Runtime Visualization")]
        [Tooltip("Show path with a LineRenderer at runtime.")]
        public bool showAtRuntime = true;

        [Tooltip("Path line color.")]
        public Color pathColor = new Color(1f, 0.85f, 0.2f, 0.8f);

        [Tooltip("Path line width.")]
        public float lineWidth = 0.15f;

        // Baked spline data
        private List<Vector3> _bakedPoints; // local space
        private float[] _segLengths;
        private float _totalLength;
        private bool _built;
        private LineRenderer _lr;

        void Awake() => Build();
        void OnEnable() => Build();
        void OnValidate() => Build();

        public void Build()
        {
            if (waypoints.Count == 0)
            {
                for (int i = 0; i < transform.childCount; i++)
                    waypoints.Add(transform.GetChild(i).localPosition);
            }
            if (waypoints.Count < 2) return;

            BakeSpline();
            _built = true;

            if (showAtRuntime)
                SetupLineRenderer();
        }

        public float TotalLength => _built ? _totalLength : 0;

        // ── Catmull-Rom baking ──

        private void BakeSpline()
        {
            _bakedPoints = new List<Vector3>();
            int wpCount = waypoints.Count;
            int segCount = loop ? wpCount : wpCount - 1;

            for (int seg = 0; seg < segCount; seg++)
            {
                // Four control points for Catmull-Rom
                Vector3 p0 = waypoints[Mod(seg - 1, wpCount)];
                Vector3 p1 = waypoints[seg];
                Vector3 p2 = waypoints[Mod(seg + 1, wpCount)];
                Vector3 p3 = waypoints[Mod(seg + 2, wpCount)];

                for (int sub = 0; sub < subdivisionsPerSegment; sub++)
                {
                    float t = sub / (float)subdivisionsPerSegment;
                    _bakedPoints.Add(CatmullRom(p0, p1, p2, p3, t));
                }
            }

            // Close the loop or add final point
            if (loop)
                _bakedPoints.Add(_bakedPoints[0]);
            else
                _bakedPoints.Add(waypoints[wpCount - 1]);

            // Compute segment lengths
            _segLengths = new float[_bakedPoints.Count - 1];
            _totalLength = 0;
            for (int i = 0; i < _segLengths.Length; i++)
            {
                float len = Vector3.Distance(_bakedPoints[i], _bakedPoints[i + 1]);
                _segLengths[i] = len;
                _totalLength += len;
            }
        }

        private static Vector3 CatmullRom(Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, float t)
        {
            float t2 = t * t;
            float t3 = t2 * t;
            return 0.5f * (
                (2f * p1) +
                (-p0 + p2) * t +
                (2f * p0 - 5f * p1 + 4f * p2 - p3) * t2 +
                (-p0 + 3f * p1 - 3f * p2 + p3) * t3
            );
        }

        private static int Mod(int x, int m)
        {
            return ((x % m) + m) % m;
        }

        // ── Sampling ──

        /// <summary>
        /// Returns world-space position at a given distance along the baked spline.
        /// </summary>
        public Vector3 SamplePosition(float distance)
        {
            if (!_built || _bakedPoints.Count < 2) return transform.position;

            if (loop)
                distance = ((distance % _totalLength) + _totalLength) % _totalLength;
            else
                distance = Mathf.Clamp(distance, 0, _totalLength);

            float acc = 0;
            for (int i = 0; i < _segLengths.Length; i++)
            {
                if (acc + _segLengths[i] >= distance)
                {
                    float t = (distance - acc) / Mathf.Max(_segLengths[i], 0.0001f);
                    var local = Vector3.Lerp(_bakedPoints[i], _bakedPoints[i + 1], t);
                    return transform.TransformPoint(local);
                }
                acc += _segLengths[i];
            }
            return transform.TransformPoint(_bakedPoints[_bakedPoints.Count - 1]);
        }

        /// <summary>
        /// Returns world-space forward direction at the given distance.
        /// </summary>
        public Vector3 SampleForward(float distance)
        {
            float delta = 0.05f;
            var a = SamplePosition(distance);
            var b = SamplePosition(distance + delta);
            var dir = (b - a).normalized;
            return dir.sqrMagnitude > 0.001f ? dir : transform.forward;
        }

        // ── Runtime LineRenderer ──

        private void SetupLineRenderer()
        {
            _lr = GetComponent<LineRenderer>();
            if (_lr == null)
                _lr = gameObject.AddComponent<LineRenderer>();

            _lr.useWorldSpace = true;
            _lr.startWidth = lineWidth;
            _lr.endWidth = lineWidth;
            _lr.loop = loop;
            _lr.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            _lr.receiveShadows = false;

            // Use Unlit material for clean line
            var mat = new Material(Shader.Find("Universal Render Pipeline/Unlit"));
            mat.color = pathColor;
            _lr.material = mat;
            _lr.startColor = pathColor;
            _lr.endColor = pathColor;

            // Set positions
            int count = loop ? _bakedPoints.Count - 1 : _bakedPoints.Count;
            _lr.positionCount = count;
            for (int i = 0; i < count; i++)
                _lr.SetPosition(i, transform.TransformPoint(_bakedPoints[i]));
        }

        // ── Gizmos ──

        void OnDrawGizmos()
        {
            if (waypoints.Count < 2) return;

            // Draw smooth preview in editor even before play
            if (_bakedPoints != null && _bakedPoints.Count > 1)
            {
                Gizmos.color = new Color(1f, 0.85f, 0.2f, 0.6f);
                for (int i = 0; i < _bakedPoints.Count - 1; i++)
                {
                    var a = transform.TransformPoint(_bakedPoints[i]);
                    var b = transform.TransformPoint(_bakedPoints[i + 1]);
                    Gizmos.DrawLine(a, b);
                }
            }
            else
            {
                // Fallback: straight-line preview
                Gizmos.color = Color.yellow;
                int count = loop ? waypoints.Count : waypoints.Count - 1;
                for (int i = 0; i < count; i++)
                {
                    var a = transform.TransformPoint(waypoints[i]);
                    var b = transform.TransformPoint(waypoints[(i + 1) % waypoints.Count]);
                    Gizmos.DrawLine(a, b);
                }
            }

            // Draw control point spheres
            Gizmos.color = new Color(1f, 0.5f, 0f, 0.9f);
            foreach (var wp in waypoints)
                Gizmos.DrawSphere(transform.TransformPoint(wp), 0.3f);
        }

        void OnDrawGizmosSelected()
        {
            if (waypoints.Count < 2) return;
            // When selected, show control point indices
            Gizmos.color = Color.white;
            for (int i = 0; i < waypoints.Count; i++)
                Gizmos.DrawWireSphere(transform.TransformPoint(waypoints[i]), 0.5f);
        }
    }
}
