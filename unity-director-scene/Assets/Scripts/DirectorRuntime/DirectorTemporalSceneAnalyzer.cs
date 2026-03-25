using System;
using System.Collections;
using System.Collections.Generic;
using UnityEngine;

namespace AIDirector.UnityRuntime
{
    public class DirectorTemporalSceneAnalyzer : MonoBehaviour
    {
        [Header("Dependencies")]
        [SerializeField] private DirectorSceneAnalyzer sceneAnalyzer;

        [Header("Capture")]
        [SerializeField] private float captureDurationSeconds = 8f;
        [SerializeField] private float sampleRateHz = 5f;
        [SerializeField] private bool detectEvents = true;
        [SerializeField] private bool includeDefaultCameraCandidate = true;

        [Header("Heuristics")]
        [SerializeField] private float speedChangeThreshold = 0.35f;
        [SerializeField] private float directionChangeDotThreshold = 0.55f;
        [SerializeField] private float keyframeDisplacementThreshold = 0.45f;

        public IEnumerator CaptureSceneTimeline(
            Action<SceneTimelineData> onSuccess,
            Action<string> onError)
        {
            if (sceneAnalyzer == null)
            {
                onError?.Invoke("DirectorTemporalSceneAnalyzer requires DirectorSceneAnalyzer.");
                yield break;
            }

            var duration = Mathf.Max(0.5f, captureDurationSeconds);
            var hz = Mathf.Max(1f, sampleRateHz);
            var interval = 1f / hz;
            var expectedSamples = Mathf.Max(2, Mathf.CeilToInt(duration * hz) + 1);

            var initialSummary = sceneAnalyzer.CaptureSceneSummary();
            var timeline = new SceneTimelineData
            {
                scene_id = initialSummary.scene_id,
                scene_name = initialSummary.scene_name,
                scene_type = initialSummary.scene_type,
                description = initialSummary.description,
                bounds = initialSummary.bounds,
                time_span = new TimeSpanData
                {
                    start = 0f,
                    end = duration,
                    duration = duration
                },
                objects_static = new List<SceneObjectData>(initialSummary.objects),
                relations = new List<SpatialRelationData>(initialSummary.relations),
                free_space = initialSummary.free_space
            };

            var staticById = new Dictionary<string, SceneObjectData>();
            foreach (var obj in timeline.objects_static)
            {
                if (!staticById.ContainsKey(obj.id))
                {
                    staticById.Add(obj.id, obj);
                }
            }

            var tracksById = new Dictionary<string, ObjectTrackData>();
            var previousPositionById = new Dictionary<string, Vector3>();
            var previousVelocityById = new Dictionary<string, Vector3>();
            var previousVisibleById = new Dictionary<string, bool>();
            var eventCounter = 0;

            for (var sampleIndex = 0; sampleIndex < expectedSamples; sampleIndex++)
            {
                if (sampleIndex > 0)
                {
                    yield return new WaitForSeconds(interval);
                }

                var now = Mathf.Min(duration, sampleIndex * interval);
                var frameSummary = sceneAnalyzer.CaptureSceneSummary();
                var frameObjectsById = new Dictionary<string, SceneObjectData>();
                foreach (var obj in frameSummary.objects)
                {
                    frameObjectsById[obj.id] = obj;
                    if (!staticById.ContainsKey(obj.id))
                    {
                        staticById[obj.id] = obj;
                        timeline.objects_static.Add(obj);
                    }
                }

                foreach (var staticObj in timeline.objects_static)
                {
                    var objectId = staticObj.id;
                    var visible = frameObjectsById.TryGetValue(objectId, out var frameObj);
                    var currentPosition = visible ? ToVector3(frameObj.position) : GetOrDefault(previousPositionById, objectId, ToVector3(staticObj.position));
                    var currentRotation = visible ? ForwardToEuler(frameObj.forward) : Vector3.zero;
                    var previousPosition = GetOrDefault(previousPositionById, objectId, currentPosition);
                    var velocity = sampleIndex > 0 ? (currentPosition - previousPosition) / Mathf.Max(interval, 0.0001f) : Vector3.zero;

                    if (!tracksById.TryGetValue(objectId, out var track))
                    {
                        track = new ObjectTrackData { object_id = objectId };
                        tracksById[objectId] = track;
                    }

                    track.samples.Add(new ObjectTrackSampleData
                    {
                        timestamp = now,
                        position = ToFloatArray(currentPosition),
                        rotation = ToFloatArray(currentRotation),
                        velocity = ToFloatArray(velocity),
                        visible = visible
                    });

                    if (detectEvents && sampleIndex > 0)
                    {
                        var wasVisible = GetOrDefault(previousVisibleById, objectId, true);
                        if (!wasVisible && visible)
                        {
                            timeline.events.Add(CreateEvent(ref eventCounter, "appear", now, 0f, objectId, $"{objectId} became visible."));
                        }
                        else if (wasVisible && !visible)
                        {
                            timeline.events.Add(CreateEvent(ref eventCounter, "disappear", now, 0f, objectId, $"{objectId} became hidden."));
                        }

                        var prevVelocity = GetOrDefault(previousVelocityById, objectId, Vector3.zero);
                        var speedDelta = Mathf.Abs(velocity.magnitude - prevVelocity.magnitude);
                        if (visible && speedDelta >= speedChangeThreshold)
                        {
                            timeline.events.Add(CreateEvent(ref eventCounter, "speed_change", now, 0f, objectId, $"{objectId} speed changed."));
                        }

                        if (visible && velocity.sqrMagnitude > 0.001f && prevVelocity.sqrMagnitude > 0.001f)
                        {
                            var directionDot = Vector3.Dot(velocity.normalized, prevVelocity.normalized);
                            if (directionDot < directionChangeDotThreshold)
                            {
                                timeline.events.Add(CreateEvent(ref eventCounter, "direction_change", now, 0f, objectId, $"{objectId} direction changed."));
                            }
                        }
                    }

                    previousPositionById[objectId] = currentPosition;
                    previousVelocityById[objectId] = velocity;
                    previousVisibleById[objectId] = visible;
                }
            }

            foreach (var pair in tracksById)
            {
                var track = pair.Value;
                track.motion = BuildMotionDescriptor(track);
                track.keyframe_indices = BuildKeyframes(track, keyframeDisplacementThreshold);
                timeline.object_tracks.Add(track);
            }

            if (includeDefaultCameraCandidate)
            {
                timeline.camera_candidates.Add(new CameraCandidateData
                {
                    region_id = "room_center",
                    time_start = 0f,
                    time_end = duration,
                    center = new[]
                    {
                        timeline.bounds.width * 0.5f,
                        Mathf.Max(1.2f, timeline.bounds.height * 0.5f),
                        timeline.bounds.length * 0.5f
                    },
                    radius = Mathf.Max(1f, Mathf.Min(timeline.bounds.width, timeline.bounds.length) * 0.25f),
                    clearance_score = 0.6f
                });
            }

            onSuccess?.Invoke(timeline);
        }

        private static MotionDescriptorData BuildMotionDescriptor(ObjectTrackData track)
        {
            if (track.samples == null || track.samples.Count == 0)
            {
                return new MotionDescriptorData
                {
                    direction_trend = new[] { 0f, 0f, 0f }
                };
            }

            var speedSum = 0f;
            var maxSpeed = 0f;
            var visibleSamples = 0;
            var firstVisible = -1;
            var lastVisible = -1;
            var directionAccumulator = Vector3.zero;
            Vector3? prevVelocity = null;
            var accelPeaks = 0;

            for (var i = 0; i < track.samples.Count; i++)
            {
                var sample = track.samples[i];
                if (!sample.visible)
                {
                    continue;
                }

                var velocity = ToVector3(sample.velocity);
                var speed = velocity.magnitude;
                speedSum += speed;
                maxSpeed = Mathf.Max(maxSpeed, speed);
                if (speed > 0.0001f)
                {
                    directionAccumulator += velocity.normalized;
                }

                if (firstVisible < 0)
                {
                    firstVisible = i;
                }
                lastVisible = i;
                visibleSamples++;

                if (prevVelocity.HasValue)
                {
                    var accel = (velocity - prevVelocity.Value).magnitude;
                    if (accel > 1.2f)
                    {
                        accelPeaks++;
                    }
                }
                prevVelocity = velocity;
            }

            var averageSpeed = visibleSamples > 0 ? speedSum / visibleSamples : 0f;
            var directionTrend = directionAccumulator.sqrMagnitude > 0.0001f ? directionAccumulator.normalized : Vector3.zero;
            var displacement = 0f;

            if (firstVisible >= 0 && lastVisible >= 0 && firstVisible != lastVisible)
            {
                var start = ToVector3(track.samples[firstVisible].position);
                var end = ToVector3(track.samples[lastVisible].position);
                displacement = Vector3.Distance(start, end);
            }

            var accelerationBucket = "constant";
            if (accelPeaks >= 3)
            {
                accelerationBucket = "variable";
            }
            else if (maxSpeed < 0.1f)
            {
                accelerationBucket = "static";
            }

            return new MotionDescriptorData
            {
                average_speed = averageSpeed,
                max_speed = maxSpeed,
                direction_trend = ToFloatArray(directionTrend),
                acceleration_bucket = accelerationBucket,
                total_displacement = displacement
            };
        }

        private static List<int> BuildKeyframes(ObjectTrackData track, float displacementThreshold)
        {
            var result = new List<int>();
            if (track.samples == null || track.samples.Count == 0)
            {
                return result;
            }

            result.Add(0);
            var lastKeyPosition = ToVector3(track.samples[0].position);
            for (var i = 1; i < track.samples.Count - 1; i++)
            {
                var current = track.samples[i];
                if (!current.visible)
                {
                    continue;
                }

                var currentPos = ToVector3(current.position);
                if (Vector3.Distance(lastKeyPosition, currentPos) >= displacementThreshold)
                {
                    result.Add(i);
                    lastKeyPosition = currentPos;
                }
            }

            if (!result.Contains(track.samples.Count - 1))
            {
                result.Add(track.samples.Count - 1);
            }

            return result;
        }

        private static SceneEventData CreateEvent(
            ref int eventCounter,
            string eventType,
            float timestamp,
            float duration,
            string objectId,
            string description)
        {
            var evt = new SceneEventData
            {
                event_id = $"evt_{eventCounter:D4}",
                event_type = eventType,
                timestamp = timestamp,
                duration = duration,
                description = description
            };
            evt.object_ids.Add(objectId);
            eventCounter++;
            return evt;
        }

        private static Vector3 ForwardToEuler(float[] forward)
        {
            var direction = ToVector3(forward);
            if (direction.sqrMagnitude < 0.0001f)
            {
                return Vector3.zero;
            }

            return Quaternion.LookRotation(direction.normalized, Vector3.up).eulerAngles;
        }

        private static float[] ToFloatArray(Vector3 value)
        {
            return new[] { value.x, value.y, value.z };
        }

        private static T GetOrDefault<T>(Dictionary<string, T> source, string key, T fallback)
        {
            if (source != null && key != null && source.TryGetValue(key, out var value))
            {
                return value;
            }

            return fallback;
        }

        private static Vector3 ToVector3(float[] values)
        {
            if (values == null || values.Length < 3)
            {
                return Vector3.zero;
            }

            return new Vector3(values[0], values[1], values[2]);
        }
    }
}
