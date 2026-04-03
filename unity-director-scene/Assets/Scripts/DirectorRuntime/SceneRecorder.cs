using System.Collections.Generic;
using UnityEngine;

namespace DirectorRuntime
{
    /// <summary>
    /// Records all ReplayableActors in the scene and produces a valid SceneTimelineData
    /// payload for the backend temporal planning API.
    /// </summary>
    public class SceneRecorder : MonoBehaviour
    {
        [System.Serializable]
        public class CachedTimelineInfo
        {
            public string filePath;
            public string fileName;
            public string displayName;
            public string relativeAge;
            public long lastWriteTicks;
        }

        [Header("Recording Settings")]
        [Tooltip("Samples per second during recording.")]
        public float sampleRate = 10f;

        [Tooltip("Scene-agnostic type label (e.g. 'dynamic_scene', 'race', 'dialog').")]
        public string sceneType = "dynamic_scene";

        [Tooltip("Human-readable scene name.")]
        public string sceneName = "Recorded Scene";

        [Tooltip("Optional description.")]
        public string sceneDescription = "";

        public bool IsRecording { get; private set; }
        public float RecordingStartTime { get; private set; }
        public float RecordingDuration { get; private set; }

        private float _nextSampleTime;
        private float _recordTime;
        private ReplayableActor[] _actors;

        [Header("Timeline Cache")]
        [Tooltip("File path for saving/loading cached timelines. Relative to project root.")]
        public string timelineCacheDir = "TimelineCache";

        [Header("Environment Capture")]
        [Tooltip("Expand timeline bounds with non-actor environment geometry (ground, track, walls, etc.).")]
        public bool includeEnvironmentInBounds = true;

        [Tooltip("Emit environment objects into objects_static for better debug visualization/context.")]
        public bool includeEnvironmentObjects = true;

        [Tooltip("Capture each visible static renderer as its own environment object instead of truncating to a small subset.")]
        public bool captureAllEnvironmentObjects = true;

        [Tooltip("Upper bound for auto-captured environment objects when full capture is disabled.")]
        public int maxEnvironmentObjects = 256;

        /// <summary>Last built timeline, kept for debug inspection.</summary>
        [HideInInspector] public SceneTimelineData lastTimeline;
        [HideInInspector] public string lastTimelineJson;

        public bool StartRecording()
        {
            _actors = FindObjectsByType<ReplayableActor>(FindObjectsSortMode.None);
            if (_actors.Length == 0)
            {
                Debug.LogWarning("[SceneRecorder] No ReplayableActor found in scene.");
                return false;
            }

            foreach (var a in _actors) a.BeginRecording();

            _recordTime = 0f;
            _nextSampleTime = 0f;
            RecordingStartTime = Time.time;
            IsRecording = true;
            Debug.Log($"[SceneRecorder] Recording started. Actors: {_actors.Length}, SampleRate: {sampleRate}Hz");
            return true;
        }

        public void StopRecording()
        {
            if (!IsRecording) return;
            IsRecording = false;
            RecordingDuration = _recordTime;
            Debug.Log($"[SceneRecorder] Recording stopped. Duration: {RecordingDuration:F2}s, " +
                      $"Samples/actor: {(_actors.Length > 0 ? _actors[0].recordedSnapshots.Count : 0)}");
        }

        void Update()
        {
            if (!IsRecording) return;

            _recordTime += Time.deltaTime;
            if (_recordTime >= _nextSampleTime)
            {
                foreach (var a in _actors)
                    a.CaptureSnapshot(_recordTime);
                _nextSampleTime += 1f / sampleRate;
            }
        }

        /// <summary>
        /// Builds a SceneTimelineData from the last recording.
        /// Also populates raw_events with basic motion-derived events.
        /// </summary>
        public SceneTimelineData BuildTimeline(string sceneId = null)
        {
            if (_actors == null || _actors.Length == 0)
            {
                Debug.LogError("[SceneRecorder] No recording data available.");
                return null;
            }

            var timeline = new SceneTimelineData
            {
                scene_id = sceneId ?? System.Guid.NewGuid().ToString("N").Substring(0, 12),
                scene_name = sceneName,
                scene_type = sceneType,
                description = sceneDescription,
                time_span = new TimeSpan { start = 0, end = RecordingDuration, duration = RecordingDuration }
            };

            // Compute scene bounds from all recorded positions
            Vector3 minP = Vector3.one * float.MaxValue;
            Vector3 maxP = Vector3.one * float.MinValue;

            foreach (var actor in _actors)
            {
                // Static object entry
                var so = new SceneObject
                {
                    id = actor.actorId,
                    name = actor.actorName,
                    category = actor.category,
                    importance = actor.importance,
                    tags = new List<string>(actor.tags),
                    position = new float[] { actor.transform.position.x, actor.transform.position.y, actor.transform.position.z }
                };

                var actorForward = actor.transform.forward;
                so.forward = new float[] { actorForward.x, actorForward.y, actorForward.z };

                if (actor.recordedSnapshots.Count > 0)
                {
                    var first = actor.recordedSnapshots[0];
                    so.position = new float[] { first.position.x, first.position.y, first.position.z };
                }
                var sz = actor.GetSize();
                so.size = new float[] { sz.x, sz.y, sz.z };
                timeline.objects_static.Add(so);

                // Object track
                var track = new ObjectTrack { object_id = actor.actorId };
                float totalDisp = 0;
                float maxSpd = 0;
                Vector3 prevPos = Vector3.zero;
                Vector3 dirAccum = Vector3.zero;

                for (int i = 0; i < actor.recordedSnapshots.Count; i++)
                {
                    var snap = actor.recordedSnapshots[i];
                    var sample = new ObjectTrackSample
                    {
                        timestamp = snap.time,
                        position = new float[] { snap.position.x, snap.position.y, snap.position.z },
                        rotation = new float[] { snap.rotation.eulerAngles.x, snap.rotation.eulerAngles.y, snap.rotation.eulerAngles.z },
                        velocity = new float[] { snap.velocity.x, snap.velocity.y, snap.velocity.z },
                        visible = snap.visible
                    };
                    track.samples.Add(sample);

                    // Bounds
                    minP = Vector3.Min(minP, snap.position);
                    maxP = Vector3.Max(maxP, snap.position);

                    // Motion stats
                    float spd = snap.velocity.magnitude;
                    if (spd > maxSpd) maxSpd = spd;
                    if (i > 0)
                    {
                        totalDisp += Vector3.Distance(snap.position, prevPos);
                        dirAccum += (snap.position - prevPos).normalized;
                    }
                    prevPos = snap.position;
                }

                float avgSpd = actor.recordedSnapshots.Count > 1
                    ? totalDisp / Mathf.Max(RecordingDuration, 0.01f) : 0;
                var dirTrend = dirAccum.normalized;
                track.motion = new MotionDescriptor
                {
                    average_speed = avgSpd,
                    max_speed = maxSpd,
                    direction_trend = new float[] { dirTrend.x, dirTrend.y, dirTrend.z },
                    acceleration_bucket = ClassifyAcceleration(actor.recordedSnapshots),
                    total_displacement = totalDisp
                };

                // Mark first and last as keyframes, plus speed-change moments
                if (track.samples.Count > 0)
                {
                    track.keyframe_indices.Add(0);
                    if (track.samples.Count > 1)
                        track.keyframe_indices.Add(track.samples.Count - 1);
                }

                timeline.object_tracks.Add(track);
            }

            if (includeEnvironmentInBounds || includeEnvironmentObjects)
            {
                AddEnvironmentData(timeline, ref minP, ref maxP);
            }

            // Bounds
            var span = maxP - minP;
            timeline.bounds = new Bounds
            {
                width = Mathf.Max(span.x, 1f),
                length = Mathf.Max(span.z, 1f),
                height = Mathf.Max(span.y, 1f)
            };

            // Leave semantic_events empty; backend will enrich
            timeline.semantic_events = new List<SemanticSceneEvent>();

            // Run the scene analyzer: generates descriptions, relations,
            // camera candidates, and rich raw_events
            DirectorTemporalSceneAnalyzer.Analyze(timeline, _actors);

            lastTimeline = timeline;
            lastTimelineJson = JsonUtility.ToJson(timeline, true);
            Debug.Log($"[SceneRecorder] Timeline built. Objects: {timeline.objects_static.Count}, " +
                      $"Tracks: {timeline.object_tracks.Count}, RawEvents: {timeline.raw_events.Count}");
            return timeline;
        }

        private void AddEnvironmentData(SceneTimelineData timeline, ref Vector3 minP, ref Vector3 maxP)
        {
            var seenObjects = new HashSet<int>();
            int emitted = 0;

            var renderers = FindObjectsByType<Renderer>(FindObjectsSortMode.None);
            for (int i = 0; i < renderers.Length; i++)
            {
                var renderer = renderers[i];
                if (renderer == null || !renderer.enabled) continue;
                if (renderer.GetComponentInParent<ReplayableActor>() != null) continue;
                if (!renderer.gameObject.activeInHierarchy) continue;
                if (!IsEnvironmentLike(renderer.gameObject)) continue;

                var b = renderer.bounds;
                if (b.size.sqrMagnitude <= 0.0001f) continue;

                if (includeEnvironmentInBounds)
                {
                    minP = Vector3.Min(minP, b.min);
                    maxP = Vector3.Max(maxP, b.max);
                }

                if (!includeEnvironmentObjects) continue;
                if (!captureAllEnvironmentObjects && emitted >= maxEnvironmentObjects) continue;

                var anchor = GetEnvironmentAnchor(renderer);
                int key = anchor.GetInstanceID();
                if (!seenObjects.Add(key)) continue;

                var so = BuildEnvironmentObject(anchor, b, key);
                timeline.objects_static.Add(so);
                emitted++;
            }
        }

        private static SceneObject BuildEnvironmentObject(GameObject go, UnityEngine.Bounds b, int key)
        {
            var lower = (go != null ? go.name : "environment").ToLowerInvariant();
            bool isGround = lower.Contains("ground") || lower.Contains("floor") || lower.Contains("track") || lower.Contains("road");
            Vector3 forward = go != null ? go.transform.forward : Vector3.forward;

            return new SceneObject
            {
                id = $"env_{key}",
                name = go != null ? go.name : "Environment",
                category = isGround ? "ground" : "architectural",
                position = new[] { b.center.x, b.center.y, b.center.z },
                size = new[] { Mathf.Max(b.size.x, 0.1f), Mathf.Max(b.size.y, 0.1f), Mathf.Max(b.size.z, 0.1f) },
                forward = new[] { forward.x, forward.y, forward.z },
                importance = 0.15f,
                tags = new List<string> { "environment", isGround ? "ground_plane" : "structure" }
            };
        }

        private static bool IsEnvironmentLike(GameObject go)
        {
            if (go == null) return false;
            if (go.CompareTag("EditorOnly")) return false;
            if (go.name.StartsWith("__", System.StringComparison.Ordinal)) return false;
            if (IsStaticHierarchy(go)) return true;

            string n = go.name.ToLowerInvariant();
            return n.Contains("ground")
                || n.Contains("floor")
                || n.Contains("track")
                || n.Contains("road")
                || n.Contains("terrain")
                || n.Contains("wall")
                || n.Contains("building")
                || n.Contains("house")
                || n.Contains("roof")
                || n.Contains("facade")
                || n.Contains("window")
                || n.Contains("door")
                || n.Contains("sidewalk")
                || n.Contains("curb")
                || n.Contains("crosswalk")
                || n.Contains("fence")
                || n.Contains("sign")
                || n.Contains("bench")
                || n.Contains("lamp")
                || n.Contains("tree")
                || n.Contains("stairs")
                || n.Contains("room")
                || n.Contains("arena")
                || n.Contains("stage")
                || n.Contains("platform");
        }

        private static GameObject GetEnvironmentAnchor(Renderer renderer)
        {
            if (renderer == null) return null;

            Transform current = renderer.transform;
            Transform lastStatic = current;
            while (current.parent != null && current.parent != current.root)
            {
                if (!IsStaticHierarchy(current.parent.gameObject)) break;
                lastStatic = current.parent;
                current = current.parent;
            }

            return lastStatic != null ? lastStatic.gameObject : renderer.gameObject;
        }

        private static bool IsStaticHierarchy(GameObject go)
        {
            Transform current = go != null ? go.transform : null;
            while (current != null)
            {
                if (current.gameObject.isStatic) return true;
                current = current.parent;
            }

            return false;
        }

        private static string ClassifyAcceleration(List<ReplayableActor.Snapshot> snaps)
        {
            if (snaps.Count < 3) return "constant";
            float firstSpeed = snaps[1].velocity.magnitude;
            float lastSpeed = snaps[snaps.Count - 1].velocity.magnitude;
            float diff = lastSpeed - firstSpeed;
            if (Mathf.Abs(diff) < 1f) return "constant";
            return diff > 0 ? "accelerating" : "decelerating";
        }

        // ── Timeline Cache (Save / Load) ──

        private string GetCacheRoot()
        {
            // Place cache folder next to Assets/ (project root), not inside Assets/
            string projectRoot = System.IO.Path.GetDirectoryName(Application.dataPath);
            string dir = System.IO.Path.Combine(projectRoot, timelineCacheDir);
            if (!System.IO.Directory.Exists(dir))
                System.IO.Directory.CreateDirectory(dir);
            return dir;
        }

        /// <summary>
        /// Saves the last built timeline JSON to disk.
        /// Returns the full file path, or null on failure.
        /// </summary>
        public string SaveTimeline(string label = null)
        {
            if (string.IsNullOrEmpty(lastTimelineJson))
            {
                Debug.LogWarning("[SceneRecorder] No timeline to save.");
                return null;
            }

            string fileName = string.IsNullOrEmpty(label)
                ? $"timeline_{lastTimeline.scene_id}.json"
                : $"timeline_{label}.json";
            string path = System.IO.Path.Combine(GetCacheRoot(), fileName);
            System.IO.File.WriteAllText(path, lastTimelineJson);
            Debug.Log($"[SceneRecorder] Timeline saved to {path}");
            return path;
        }

        /// <summary>
        /// Loads a cached timeline JSON from disk into lastTimeline / lastTimelineJson.
        /// Accepts a full path or just a filename (resolved relative to cache dir).
        /// Returns true on success.
        /// </summary>
        public bool LoadTimeline(string pathOrName)
        {
            string path = pathOrName;
            if (!System.IO.File.Exists(path))
            {
                // Try resolving relative to cache dir
                path = System.IO.Path.Combine(GetCacheRoot(), pathOrName);
            }
            if (!System.IO.File.Exists(path))
            {
                Debug.LogError($"[SceneRecorder] Cache file not found: {pathOrName}");
                return false;
            }

            string json = System.IO.File.ReadAllText(path);
            var loaded = JsonUtility.FromJson<SceneTimelineData>(json);
            if (loaded == null)
            {
                Debug.LogError($"[SceneRecorder] Failed to parse timeline from {path}");
                return false;
            }

            lastTimeline = loaded;
            lastTimelineJson = json;
            RecordingDuration = loaded.time_span != null ? loaded.time_span.duration : 0;
            int hydratedActors = HydrateReplayBuffersFromTimeline(loaded);
            Debug.Log($"[SceneRecorder] Timeline loaded from {path}. " +
                      $"SceneId: {loaded.scene_id}, Duration: {RecordingDuration:F2}s, " +
                      $"Objects: {loaded.objects_static.Count}, Tracks: {loaded.object_tracks.Count}, " +
                      $"HydratedActors: {hydratedActors}");
            return true;
        }

        public int AdoptTimeline(SceneTimelineData timeline, string timelineJson = null)
        {
            if (timeline == null)
                return 0;

            lastTimeline = timeline;
            lastTimelineJson = string.IsNullOrEmpty(timelineJson)
                ? JsonUtility.ToJson(timeline, true)
                : timelineJson;
            RecordingDuration = timeline.time_span != null ? timeline.time_span.duration : 0f;
            return HydrateReplayBuffersFromTimeline(timeline);
        }

        /// <summary>
        /// Applies a pose sampled from the loaded timeline to matching scene actors.
        /// Returns true if at least one actor was updated.
        /// </summary>
        public bool ApplyTimelinePose(float timestamp, out int appliedActors, out int missingActors)
        {
            appliedActors = 0;
            missingActors = 0;

            if (lastTimeline == null || lastTimeline.object_tracks == null || lastTimeline.object_tracks.Count == 0)
                return false;

            var actors = FindObjectsByType<ReplayableActor>(FindObjectsSortMode.None);
            var actorMap = new Dictionary<string, ReplayableActor>();
            foreach (var actor in actors)
            {
                if (!string.IsNullOrEmpty(actor.actorId))
                    actorMap[actor.actorId] = actor;
            }

            foreach (var track in lastTimeline.object_tracks)
            {
                if (track == null || string.IsNullOrEmpty(track.object_id) || track.samples == null || track.samples.Count == 0)
                    continue;

                if (!actorMap.TryGetValue(track.object_id, out var target))
                {
                    missingActors++;
                    continue;
                }

                var sample = SampleTrackAt(track.samples, timestamp);
                if (sample.position != null && sample.position.Length >= 3)
                {
                    target.transform.position = new Vector3(
                        sample.position[0],
                        sample.position[1],
                        sample.position[2]);
                }

                if (sample.rotation != null && sample.rotation.Length >= 3)
                {
                    target.transform.rotation = Quaternion.Euler(
                        sample.rotation[0],
                        sample.rotation[1],
                        sample.rotation[2]);
                }

                appliedActors++;
            }

            return appliedActors > 0;
        }

        private static ObjectTrackSample SampleTrackAt(List<ObjectTrackSample> samples, float timestamp)
        {
            if (samples.Count == 1 || timestamp <= samples[0].timestamp)
                return samples[0];

            var last = samples[samples.Count - 1];
            if (timestamp >= last.timestamp)
                return last;

            for (int i = 0; i < samples.Count - 1; i++)
            {
                var a = samples[i];
                var b = samples[i + 1];
                if (timestamp < a.timestamp || timestamp > b.timestamp)
                    continue;

                float dt = Mathf.Max(b.timestamp - a.timestamp, 0.0001f);
                float t = Mathf.Clamp01((timestamp - a.timestamp) / dt);

                var pa = (a.position != null && a.position.Length >= 3)
                    ? new Vector3(a.position[0], a.position[1], a.position[2])
                    : Vector3.zero;
                var pb = (b.position != null && b.position.Length >= 3)
                    ? new Vector3(b.position[0], b.position[1], b.position[2])
                    : pa;

                var ra = (a.rotation != null && a.rotation.Length >= 3)
                    ? Quaternion.Euler(a.rotation[0], a.rotation[1], a.rotation[2])
                    : Quaternion.identity;
                var rb = (b.rotation != null && b.rotation.Length >= 3)
                    ? Quaternion.Euler(b.rotation[0], b.rotation[1], b.rotation[2])
                    : ra;

                var p = Vector3.Lerp(pa, pb, t);
                var r = Quaternion.Slerp(ra, rb, t).eulerAngles;

                return new ObjectTrackSample
                {
                    timestamp = timestamp,
                    position = new[] { p.x, p.y, p.z },
                    rotation = new[] { r.x, r.y, r.z },
                    velocity = new[] { 0f, 0f, 0f },
                    visible = true
                };
            }

            return last;
        }

        private int HydrateReplayBuffersFromTimeline(SceneTimelineData timeline)
        {
            if (timeline == null || timeline.object_tracks == null)
                return 0;

            var actors = FindObjectsByType<ReplayableActor>(FindObjectsSortMode.None);
            var actorMap = new Dictionary<string, ReplayableActor>();
            foreach (var actor in actors)
            {
                if (!string.IsNullOrEmpty(actor.actorId))
                    actorMap[actor.actorId] = actor;
            }

            int hydrated = 0;
            foreach (var track in timeline.object_tracks)
            {
                if (track == null || string.IsNullOrEmpty(track.object_id) || track.samples == null || track.samples.Count == 0)
                    continue;
                if (!actorMap.TryGetValue(track.object_id, out var actor))
                    continue;

                actor.recordedSnapshots.Clear();
                for (int i = 0; i < track.samples.Count; i++)
                {
                    var sample = track.samples[i];
                    actor.recordedSnapshots.Add(new ReplayableActor.Snapshot
                    {
                        time = sample.timestamp,
                        position = ToVector3(sample.position, actor.transform.position),
                        rotation = Quaternion.Euler(ToVector3(sample.rotation, actor.transform.eulerAngles)),
                        velocity = ToVector3(sample.velocity, Vector3.zero),
                        visible = sample.visible
                    });
                }

                hydrated++;
            }

            return hydrated;
        }

        private static Vector3 ToVector3(float[] values, Vector3 fallback)
        {
            if (values == null || values.Length < 3)
                return fallback;

            return new Vector3(values[0], values[1], values[2]);
        }

        /// <summary>
        /// Returns cached timelines sorted by newest first with UI-friendly labels.
        /// </summary>
        public CachedTimelineInfo[] ListCachedTimelines()
        {
            string dir = GetCacheRoot();
            if (!System.IO.Directory.Exists(dir)) return new CachedTimelineInfo[0];

            var files = System.IO.Directory.GetFiles(dir, "timeline_*.json");
            var entries = new CachedTimelineInfo[files.Length];

            for (int i = 0; i < files.Length; i++)
            {
                string filePath = files[i];
                string fileName = System.IO.Path.GetFileName(filePath);
                var lastWrite = System.IO.File.GetLastWriteTime(filePath);

                entries[i] = new CachedTimelineInfo
                {
                    filePath = filePath,
                    fileName = fileName,
                    displayName = lastWrite.ToString("yyyy-MM-dd HH:mm:ss"),
                    relativeAge = FormatRelativeAge(lastWrite),
                    lastWriteTicks = lastWrite.Ticks
                };
            }

            System.Array.Sort(entries, (a, b) => b.lastWriteTicks.CompareTo(a.lastWriteTicks));
            return entries;
        }

        private static string FormatRelativeAge(System.DateTime timestamp)
        {
            var delta = System.DateTime.Now - timestamp;
            if (delta.TotalSeconds < 60)
                return "just now";
            if (delta.TotalMinutes < 60)
                return $"{Mathf.Max(1, Mathf.FloorToInt((float)delta.TotalMinutes))} min ago";
            if (delta.TotalHours < 24)
                return $"{Mathf.Max(1, Mathf.FloorToInt((float)delta.TotalHours))} hr ago";
            return $"{Mathf.Max(1, Mathf.FloorToInt((float)delta.TotalDays))} day ago";
        }
    }
}
