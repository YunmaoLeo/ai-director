using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace DirectorRuntime
{
    /// <summary>
    /// Analyzes recorded actor data to produce rich, scene-agnostic descriptions,
    /// spatial relations, camera candidates, and cinematic-aware raw events.
    /// Designed to be called after recording is complete and tracks are built.
    /// All analysis is deterministic (no LLM dependency).
    /// </summary>
    public static class DirectorTemporalSceneAnalyzer
    {
        const float SpeedChangeMinDelta = 3.5f;
        const float SpeedChangeMinRelative = 0.45f;
        const float SpeedChangeMinSpeed = 1.5f;
        const float SpeedChangeCooldown = 1.0f;
        const float SpeedChangeStopThreshold = 0.25f;
        const float SpeedChangeResumeThreshold = 1.0f;
        const float MinMeaningfulPauseDuration = 0.6f;

        // ── Per-actor intermediate analysis ──

        public struct ActorProfile
        {
            public string actorId;
            public string actorName;
            public string category;
            public string manualDescription;

            // Motion pattern
            public string motionPattern;   // looping, linear, stationary, oscillating, erratic
            public string speedProfile;    // constant, accelerating, decelerating, variable, burst
            public float averageSpeed;
            public float maxSpeed;
            public float totalDisplacement;
            public float pathStraightness; // 0 = very curved, 1 = perfectly straight
            public Vector3 centroid;       // average position
            public Vector3 spatialExtent;  // bounding box of this actor's motion
            public float loopScore;        // how close start/end positions are relative to path length

            // Spatial zone (relative to scene bounds center)
            public string spatialZone;     // central, north, south, east, west, etc.

            // Generated description
            public string generatedDescription;
        }

        // ── Main entry point ──

        /// <summary>
        /// Enriches a SceneTimelineData in-place: fills description, object descriptions,
        /// spatial relations, camera candidates, and regenerates raw_events.
        /// </summary>
        public static void Analyze(SceneTimelineData timeline, ReplayableActor[] actors)
        {
            if (actors == null || actors.Length == 0) return;

            // Build per-actor profiles
            var profiles = new List<ActorProfile>();
            var profileMap = new Dictionary<string, ActorProfile>();
            for (int i = 0; i < actors.Length; i++)
            {
                var p = BuildActorProfile(actors[i]);
                profiles.Add(p);
                profileMap[p.actorId] = p;
            }

            // Scene center
            Vector3 sceneCenter = Vector3.zero;
            foreach (var p in profiles) sceneCenter += p.centroid;
            if (profiles.Count > 0) sceneCenter /= profiles.Count;

            // Assign spatial zones
            for (int i = 0; i < profiles.Count; i++)
            {
                var p = profiles[i];
                p.spatialZone = ClassifySpatialZone(p.centroid, sceneCenter);
                p.generatedDescription = GenerateActorDescription(p);
                profiles[i] = p;
                profileMap[p.actorId] = p;
            }

            // Write per-object descriptions into timeline
            foreach (var so in timeline.objects_static)
            {
                if (profileMap.TryGetValue(so.id, out var prof))
                    so.description = prof.generatedDescription;
            }

            // Generate scene-level description
            timeline.description = GenerateSceneDescription(timeline, profiles, sceneCenter);

            // Generate spatial relations
            timeline.relations = GenerateSpatialRelations(profiles, actors);

            // Generate camera candidates
            timeline.camera_candidates = GenerateCameraCandidates(
                profiles, actors, timeline.time_span, sceneCenter);

            // Re-generate rich raw_events (replace the basic ones)
            var richEvents = GenerateRichEvents(actors, profiles, profileMap, sceneCenter);
            timeline.raw_events = richEvents;
            timeline.events = richEvents; // backward-compat mirror

            Debug.Log($"[SceneAnalyzer] Enrichment complete. " +
                      $"Relations: {timeline.relations.Count}, " +
                      $"CameraCandidates: {timeline.camera_candidates.Count}, " +
                      $"Events: {timeline.raw_events.Count}");
        }

        // ── Actor profiling ──

        static ActorProfile BuildActorProfile(ReplayableActor actor)
        {
            var snaps = actor.recordedSnapshots;
            var p = new ActorProfile
            {
                actorId = actor.actorId,
                actorName = actor.actorName,
                category = actor.category,
                manualDescription = actor.description
            };

            if (snaps.Count < 2)
            {
                p.motionPattern = "stationary";
                p.speedProfile = "constant";
                if (snaps.Count > 0) p.centroid = snaps[0].position;
                return p;
            }

            // Centroid and spatial extent
            Vector3 minP = Vector3.one * float.MaxValue;
            Vector3 maxP = Vector3.one * float.MinValue;
            Vector3 sum = Vector3.zero;
            float totalDist = 0;
            float maxSpd = 0;
            float speedSum = 0;
            var speeds = new List<float>();

            for (int i = 0; i < snaps.Count; i++)
            {
                var pos = snaps[i].position;
                sum += pos;
                minP = Vector3.Min(minP, pos);
                maxP = Vector3.Max(maxP, pos);
                float spd = snaps[i].velocity.magnitude;
                speeds.Add(spd);
                speedSum += spd;
                if (spd > maxSpd) maxSpd = spd;
                if (i > 0) totalDist += Vector3.Distance(snaps[i].position, snaps[i - 1].position);
            }

            p.centroid = sum / snaps.Count;
            p.spatialExtent = maxP - minP;
            p.totalDisplacement = totalDist;
            p.averageSpeed = speedSum / snaps.Count;
            p.maxSpeed = maxSpd;

            // Straightness: net displacement / path length
            float netDisp = Vector3.Distance(snaps[0].position, snaps[snaps.Count - 1].position);
            p.pathStraightness = totalDist > 0.01f ? Mathf.Clamp01(netDisp / totalDist) : 1f;

            // Loop score: how close start and end are
            p.loopScore = totalDist > 0.01f
                ? 1f - Mathf.Clamp01(netDisp / Mathf.Max(p.spatialExtent.magnitude, 1f))
                : 0f;

            // Motion pattern classification
            p.motionPattern = ClassifyMotionPattern(p, snaps);
            p.speedProfile = ClassifySpeedProfile(speeds);

            return p;
        }

        static string ClassifyMotionPattern(ActorProfile p, List<ReplayableActor.Snapshot> snaps)
        {
            if (p.totalDisplacement < 0.5f) return "stationary";
            if (p.loopScore > 0.7f) return "looping";
            if (p.pathStraightness > 0.85f) return "linear";

            // Check for oscillation: does the actor reverse direction repeatedly?
            int reversals = 0;
            for (int i = 2; i < snaps.Count; i++)
            {
                var d1 = (snaps[i - 1].position - snaps[i - 2].position);
                var d2 = (snaps[i].position - snaps[i - 1].position);
                if (d1.sqrMagnitude > 0.01f && d2.sqrMagnitude > 0.01f &&
                    Vector3.Dot(d1.normalized, d2.normalized) < -0.5f)
                    reversals++;
            }
            if (reversals > snaps.Count * 0.1f) return "oscillating";

            // Check for erratic: high direction variance
            float angleSum = 0;
            int angleCount = 0;
            for (int i = 2; i < snaps.Count; i++)
            {
                var d1 = (snaps[i - 1].position - snaps[i - 2].position).normalized;
                var d2 = (snaps[i].position - snaps[i - 1].position).normalized;
                if (d1.sqrMagnitude > 0.01f && d2.sqrMagnitude > 0.01f)
                {
                    angleSum += Vector3.Angle(d1, d2);
                    angleCount++;
                }
            }
            float avgAngle = angleCount > 0 ? angleSum / angleCount : 0;
            if (avgAngle > 25f) return "erratic";

            return "curving";
        }

        static string ClassifySpeedProfile(List<float> speeds)
        {
            if (speeds.Count < 3) return "constant";

            float first = speeds[1]; // skip frame 0 (may be zero)
            float last = speeds[speeds.Count - 1];
            float mean = 0;
            foreach (var s in speeds) mean += s;
            mean /= speeds.Count;

            float variance = 0;
            foreach (var s in speeds) variance += (s - mean) * (s - mean);
            variance /= speeds.Count;
            float cv = mean > 0.1f ? Mathf.Sqrt(variance) / mean : 0; // coefficient of variation

            if (cv < 0.15f) return "constant";

            // Check for single burst pattern
            int highCount = 0;
            float threshold = mean * 1.5f;
            foreach (var s in speeds) if (s > threshold) highCount++;
            if (highCount > 0 && highCount < speeds.Count * 0.3f) return "burst";

            float diff = last - first;
            if (Mathf.Abs(diff) > mean * 0.3f)
                return diff > 0 ? "accelerating" : "decelerating";

            return "variable";
        }

        // ── Spatial zone classification ──

        static string ClassifySpatialZone(Vector3 position, Vector3 sceneCenter)
        {
            var offset = position - sceneCenter;
            float dist = new Vector2(offset.x, offset.z).magnitude;
            if (dist < 3f) return "central";

            // Use 8-direction compass
            float angle = Mathf.Atan2(offset.x, offset.z) * Mathf.Rad2Deg;
            if (angle < 0) angle += 360f;

            if (angle < 22.5f || angle >= 337.5f) return "north";
            if (angle < 67.5f) return "northeast";
            if (angle < 112.5f) return "east";
            if (angle < 157.5f) return "southeast";
            if (angle < 202.5f) return "south";
            if (angle < 247.5f) return "southwest";
            if (angle < 292.5f) return "west";
            return "northwest";
        }

        static string DescribeCardinalDirection(Vector3 direction)
        {
            float angle = Mathf.Atan2(direction.x, direction.z) * Mathf.Rad2Deg;
            if (angle < 0) angle += 360f;
            if (angle < 45f || angle >= 315f) return "northward";
            if (angle < 135f) return "eastward";
            if (angle < 225f) return "southward";
            return "westward";
        }

        static string DescribeSpeed(float speed)
        {
            if (speed < 0.5f) return "nearly still";
            if (speed < 2f) return "slowly";
            if (speed < 5f) return "at moderate speed";
            if (speed < 10f) return "quickly";
            return "at high speed";
        }

        // ── Description generation ──

        static string GenerateActorDescription(ActorProfile p)
        {
            // If user provided a manual description, use it as base and append motion info
            if (!string.IsNullOrEmpty(p.manualDescription))
            {
                return $"{p.manualDescription} " +
                       $"Motion: {p.motionPattern} path, {p.speedProfile} speed " +
                       $"(avg {p.averageSpeed:F1} u/s, max {p.maxSpeed:F1} u/s), " +
                       $"covering {p.totalDisplacement:F0} units.";
            }

            var sb = new StringBuilder();
            sb.Append($"{p.actorName} is a {p.category}");

            switch (p.motionPattern)
            {
                case "stationary":
                    sb.Append($" positioned in the {p.spatialZone} area, remaining stationary.");
                    return sb.ToString();
                case "looping":
                    sb.Append($" traveling in a {p.speedProfile}-speed loop");
                    break;
                case "linear":
                    var dir = DescribeCardinalDirection(
                        p.spatialExtent.x > p.spatialExtent.z ? Vector3.right : Vector3.forward);
                    sb.Append($" moving {dir} in a roughly straight path");
                    break;
                case "oscillating":
                    sb.Append($" oscillating back and forth");
                    break;
                case "erratic":
                    sb.Append($" moving erratically with frequent direction changes");
                    break;
                default: // curving
                    sb.Append($" following a curved path");
                    break;
            }

            sb.Append($" through the {p.spatialZone} region");
            sb.Append($" {DescribeSpeed(p.averageSpeed)}");
            sb.Append($" (avg {p.averageSpeed:F1}, peak {p.maxSpeed:F1} u/s)");
            sb.Append($", covering {p.totalDisplacement:F0} units of distance.");

            if (p.speedProfile == "burst")
                sb.Append(" Exhibits intermittent bursts of speed.");
            else if (p.speedProfile == "accelerating")
                sb.Append(" Gradually gaining speed over time.");
            else if (p.speedProfile == "decelerating")
                sb.Append(" Gradually slowing down over time.");

            return sb.ToString();
        }

        static string GenerateSceneDescription(
            SceneTimelineData timeline, List<ActorProfile> profiles, Vector3 sceneCenter)
        {
            var sb = new StringBuilder();

            // Scene overview
            sb.Append($"A {timeline.scene_type} scene spanning {timeline.time_span.duration:F1} seconds");
            sb.Append($" across a {timeline.bounds.width:F0}x{timeline.bounds.length:F0} unit area");
            sb.Append($" featuring {profiles.Count} dynamic object{(profiles.Count != 1 ? "s" : "")}");

            // Summarize categories
            var cats = new Dictionary<string, int>();
            foreach (var p in profiles)
            {
                if (!cats.ContainsKey(p.category)) cats[p.category] = 0;
                cats[p.category]++;
            }
            var catParts = new List<string>();
            foreach (var kv in cats)
                catParts.Add(kv.Value > 1 ? $"{kv.Value} {kv.Key}s" : $"1 {kv.Key}");
            sb.Append($" ({string.Join(", ", catParts)}).");

            // Overall dynamics
            float avgAllSpeed = 0;
            int movingCount = 0;
            foreach (var p in profiles)
            {
                if (p.motionPattern != "stationary")
                {
                    avgAllSpeed += p.averageSpeed;
                    movingCount++;
                }
            }
            if (movingCount > 0)
            {
                avgAllSpeed /= movingCount;
                string paceDesc = avgAllSpeed < 2f ? "slow-paced" :
                    avgAllSpeed < 6f ? "moderate-paced" : "fast-paced";
                sb.Append($" The action is {paceDesc} overall.");
            }

            // Motion patterns summary
            var patterns = new Dictionary<string, List<string>>();
            foreach (var p in profiles)
            {
                if (!patterns.ContainsKey(p.motionPattern))
                    patterns[p.motionPattern] = new List<string>();
                patterns[p.motionPattern].Add(p.actorName);
            }
            foreach (var kv in patterns)
            {
                if (kv.Key == "stationary") continue;
                string names = string.Join(" and ", kv.Value);
                sb.Append($" {names}: {kv.Key} motion.");
            }

            return sb.ToString();
        }

        // ── Spatial relations ──

        static List<SpatialRelation> GenerateSpatialRelations(
            List<ActorProfile> profiles, ReplayableActor[] actors)
        {
            var rels = new List<SpatialRelation>();
            for (int a = 0; a < profiles.Count; a++)
            {
                for (int b = a + 1; b < profiles.Count; b++)
                {
                    var pa = profiles[a];
                    var pb = profiles[b];

                    // Distance relation based on average positions
                    float dist = Vector3.Distance(pa.centroid, pb.centroid);
                    float combinedExtent = (pa.spatialExtent.magnitude + pb.spatialExtent.magnitude) * 0.5f;

                    if (dist < combinedExtent * 0.3f)
                        rels.Add(new SpatialRelation { type = "co-located", source = pa.actorId, target = pb.actorId });
                    else if (dist < combinedExtent * 0.6f)
                        rels.Add(new SpatialRelation { type = "nearby", source = pa.actorId, target = pb.actorId });

                    // Path relationship from snapshot analysis
                    string pathRel = AnalyzePathRelationship(actors[a], actors[b]);
                    if (pathRel != null)
                        rels.Add(new SpatialRelation { type = pathRel, source = pa.actorId, target = pb.actorId });

                    // Speed comparison
                    if (pa.averageSpeed > 0.5f && pb.averageSpeed > 0.5f)
                    {
                        float speedRatio = pa.averageSpeed / Mathf.Max(pb.averageSpeed, 0.01f);
                        if (speedRatio > 1.5f)
                            rels.Add(new SpatialRelation { type = "faster_than", source = pa.actorId, target = pb.actorId });
                        else if (speedRatio < 0.67f)
                            rels.Add(new SpatialRelation { type = "slower_than", source = pa.actorId, target = pb.actorId });
                    }
                }
            }
            return rels;
        }

        static string AnalyzePathRelationship(ReplayableActor a, ReplayableActor b)
        {
            var snapsA = a.recordedSnapshots;
            var snapsB = b.recordedSnapshots;
            int count = Mathf.Min(snapsA.Count, snapsB.Count);
            if (count < 5) return null;

            int parallelFrames = 0;
            int convergingFrames = 0;
            int divergingFrames = 0;
            float prevDist = Vector3.Distance(snapsA[0].position, snapsB[0].position);

            for (int i = 1; i < count; i++)
            {
                float dist = Vector3.Distance(snapsA[i].position, snapsB[i].position);
                var dirA = snapsA[i].velocity.normalized;
                var dirB = snapsB[i].velocity.normalized;

                if (dirA.sqrMagnitude > 0.01f && dirB.sqrMagnitude > 0.01f)
                {
                    float dot = Vector3.Dot(dirA, dirB);
                    if (dot > 0.7f) parallelFrames++;
                }

                float distDelta = dist - prevDist;
                if (distDelta < -0.1f) convergingFrames++;
                else if (distDelta > 0.1f) divergingFrames++;
                prevDist = dist;
            }

            float total = count - 1f;
            if (parallelFrames / total > 0.5f) return "parallel_motion";
            if (convergingFrames / total > 0.4f) return "converging";
            if (divergingFrames / total > 0.4f) return "diverging";
            return null;
        }

        // ── Camera candidates ──

        static List<CameraCandidate> GenerateCameraCandidates(
            List<ActorProfile> profiles, ReplayableActor[] actors,
            TimeSpan timeSpan, Vector3 sceneCenter)
        {
            var candidates = new List<CameraCandidate>();
            int idx = 0;
            float tStart = timeSpan.start;
            float tEnd = timeSpan.end;

            // 1. Overview position: elevated, looking at scene center
            candidates.Add(new CameraCandidate
            {
                region_id = $"cam_region_{idx++}",
                time_start = tStart,
                time_end = tEnd,
                center = new float[] { sceneCenter.x, sceneCenter.y + 15f, sceneCenter.z - 20f },
                radius = 10f,
                clearance_score = 0.9f
            });

            // 2. Per-actor tracking zones
            foreach (var p in profiles)
            {
                if (p.motionPattern == "stationary") continue;

                // Side tracking position (offset perpendicular to main motion direction)
                Vector3 perpOffset = Vector3.Cross(
                    (p.spatialExtent.x > p.spatialExtent.z ? Vector3.right : Vector3.forward),
                    Vector3.up).normalized * 8f;

                candidates.Add(new CameraCandidate
                {
                    region_id = $"cam_region_{idx++}",
                    time_start = tStart,
                    time_end = tEnd,
                    center = new float[] {
                        p.centroid.x + perpOffset.x,
                        p.centroid.y + 3f,
                        p.centroid.z + perpOffset.z },
                    radius = 6f,
                    clearance_score = 0.7f
                });
            }

            // 3. Interaction hotspots: find time windows where actors are closest
            for (int a = 0; a < actors.Length; a++)
            {
                for (int b = a + 1; b < actors.Length; b++)
                {
                    var hot = FindClosestApproach(actors[a], actors[b]);
                    if (hot.HasValue)
                    {
                        var h = hot.Value;
                        candidates.Add(new CameraCandidate
                        {
                            region_id = $"cam_region_{idx++}",
                            time_start = Mathf.Max(h.time - 1f, tStart),
                            time_end = Mathf.Min(h.time + 1f, tEnd),
                            center = new float[] {
                                h.midpoint.x, h.midpoint.y + 5f, h.midpoint.z - 8f },
                            radius = 5f,
                            clearance_score = 0.85f
                        });
                    }
                }
            }

            return candidates;
        }

        struct ApproachPoint { public float time; public Vector3 midpoint; public float distance; }

        static ApproachPoint? FindClosestApproach(ReplayableActor a, ReplayableActor b)
        {
            var sa = a.recordedSnapshots;
            var sb = b.recordedSnapshots;
            int count = Mathf.Min(sa.Count, sb.Count);
            if (count < 2) return null;

            float minDist = float.MaxValue;
            int minIdx = 0;
            for (int i = 0; i < count; i++)
            {
                float d = Vector3.Distance(sa[i].position, sb[i].position);
                if (d < minDist) { minDist = d; minIdx = i; }
            }

            return new ApproachPoint
            {
                time = sa[minIdx].time,
                midpoint = (sa[minIdx].position + sb[minIdx].position) * 0.5f,
                distance = minDist
            };
        }

        // ── Rich event generation ──

        static List<SceneEvent> GenerateRichEvents(
            ReplayableActor[] actors, List<ActorProfile> profiles,
            Dictionary<string, ActorProfile> profileMap, Vector3 sceneCenter)
        {
            var events = new List<SceneEvent>();
            int idx = 0;

            foreach (var actor in actors)
            {
                var snaps = actor.recordedSnapshots;
                if (snaps.Count == 0) continue;
                var prof = profileMap[actor.actorId];

                // Appear
                string zone = ClassifySpatialZone(snaps[0].position, sceneCenter);
                events.Add(new SceneEvent
                {
                    event_id = $"evt_{idx++}",
                    event_type = "appear",
                    timestamp = snaps[0].time,
                    object_ids = new List<string> { actor.actorId },
                    description = $"{actor.actorName} ({actor.category}) enters the scene " +
                                  $"in the {zone} area, moving {DescribeSpeed(snaps.Count > 1 ? snaps[1].velocity.magnitude : 0)}."
                });

                // Speed changes with context
                float prevSpeed = 0;
                float lastSpeedEventTime = float.NegativeInfinity;
                for (int i = 1; i < snaps.Count; i++)
                {
                    float spd = snaps[i].velocity.magnitude;
                    float delta = spd - prevSpeed;
                    float baseline = Mathf.Max(prevSpeed, spd, prof.averageSpeed, 0.01f);
                    float relativeDelta = Mathf.Abs(delta) / baseline;
                    bool hasSignificantDelta = Mathf.Abs(delta) >= SpeedChangeMinDelta;
                    bool hasSignificantRelativeChange = relativeDelta >= SpeedChangeMinRelative;
                    bool aboveMeaningfulSpeed = Mathf.Max(prevSpeed, spd) >= SpeedChangeMinSpeed;
                    bool outsideCooldown = (snaps[i].time - lastSpeedEventTime) >= SpeedChangeCooldown;

                    if (hasSignificantDelta && hasSignificantRelativeChange && aboveMeaningfulSpeed && outsideCooldown)
                    {
                        string spdZone = ClassifySpatialZone(snaps[i].position, sceneCenter);
                        string verb = delta > 0 ? "accelerates" : "decelerates";
                        string intensity = Mathf.Abs(delta) > 6.5f || relativeDelta > 0.85f
                            ? "sharply"
                            : "noticeably";
                        events.Add(new SceneEvent
                        {
                            event_id = $"evt_{idx++}",
                            event_type = "speed_change",
                            timestamp = snaps[i].time,
                            object_ids = new List<string> { actor.actorId },
                            description = $"{actor.actorName} {intensity} {verb} " +
                                          $"from {prevSpeed:F1} to {spd:F1} u/s " +
                                          $"in the {spdZone} area."
                        });
                        lastSpeedEventTime = snaps[i].time;
                    }
                    prevSpeed = spd;
                }

                // Direction changes with context
                for (int i = 2; i < snaps.Count; i++)
                {
                    var d1 = (snaps[i - 1].position - snaps[i - 2].position).normalized;
                    var d2 = (snaps[i].position - snaps[i - 1].position).normalized;
                    if (d1.sqrMagnitude > 0.01f && d2.sqrMagnitude > 0.01f)
                    {
                        float angle = Vector3.Angle(d1, d2);
                        if (angle > 30f)
                        {
                            string turnType = angle > 90f ? "sharp turn" :
                                              angle > 60f ? "significant turn" : "gradual curve";
                            string newDir = DescribeCardinalDirection(d2);
                            events.Add(new SceneEvent
                            {
                                event_id = $"evt_{idx++}",
                                event_type = "direction_change",
                                timestamp = snaps[i].time,
                                object_ids = new List<string> { actor.actorId },
                                description = $"{actor.actorName} makes a {turnType} ({angle:F0} deg), " +
                                              $"now heading {newDir}."
                            });
                        }
                    }
                }

                // Momentary stop (speed drops near zero then resumes)
                bool wasStopped = false;
                float stopStart = 0;
                for (int i = 1; i < snaps.Count; i++)
                {
                    bool stopped = snaps[i].velocity.magnitude < SpeedChangeStopThreshold;
                    if (stopped && !wasStopped)
                    {
                        stopStart = snaps[i].time;
                    }
                    else if (!stopped && wasStopped && snaps[i].velocity.magnitude > SpeedChangeResumeThreshold)
                    {
                        float dur = snaps[i].time - stopStart;
                        if (dur >= MinMeaningfulPauseDuration && (stopStart - lastSpeedEventTime) >= SpeedChangeCooldown)
                        {
                            events.Add(new SceneEvent
                            {
                                event_id = $"evt_{idx++}",
                                event_type = "speed_change",
                                timestamp = stopStart,
                                duration = dur,
                                object_ids = new List<string> { actor.actorId },
                                description = $"{actor.actorName} pauses for {dur:F1}s before resuming movement."
                            });
                            lastSpeedEventTime = stopStart;
                        }
                    }
                    wasStopped = stopped;
                }
            }

            // ── Pairwise interaction events ──
            for (int a = 0; a < actors.Length; a++)
            {
                for (int b = a + 1; b < actors.Length; b++)
                {
                    var snapsA = actors[a].recordedSnapshots;
                    var snapsB = actors[b].recordedSnapshots;
                    int count = Mathf.Min(snapsA.Count, snapsB.Count);

                    bool wasClose = false;
                    float closeStart = 0;
                    float closeMinDist = float.MaxValue;
                    Vector3 closeMidpoint = Vector3.zero;

                    for (int i = 0; i < count; i++)
                    {
                        float dist = Vector3.Distance(snapsA[i].position, snapsB[i].position);
                        bool isClose = dist < 5f;

                        if (isClose)
                        {
                            if (!wasClose)
                            {
                                closeStart = snapsA[i].time;
                                closeMinDist = dist;
                                closeMidpoint = (snapsA[i].position + snapsB[i].position) * 0.5f;
                            }
                            if (dist < closeMinDist)
                            {
                                closeMinDist = dist;
                                closeMidpoint = (snapsA[i].position + snapsB[i].position) * 0.5f;
                            }
                        }
                        else if (wasClose)
                        {
                            // Emit interaction event with duration
                            float dur = snapsA[Mathf.Min(i, snapsA.Count - 1)].time - closeStart;
                            string zone = ClassifySpatialZone(closeMidpoint, sceneCenter);

                            // Determine interaction quality
                            var dirA = snapsA[Mathf.Max(0, i - 1)].velocity.normalized;
                            var dirB = snapsB[Mathf.Max(0, i - 1)].velocity.normalized;
                            float dot = Vector3.Dot(dirA, dirB);
                            string interType = dot > 0.5f ? "side-by-side passage" :
                                               dot < -0.5f ? "head-on approach" :
                                               "crossing paths";

                            events.Add(new SceneEvent
                            {
                                event_id = $"evt_{idx++}",
                                event_type = "interaction",
                                timestamp = closeStart,
                                duration = dur,
                                object_ids = new List<string> { actors[a].actorId, actors[b].actorId },
                                description = $"{actors[a].actorName} and {actors[b].actorName}: " +
                                              $"{interType} in the {zone} area " +
                                              $"(closest: {closeMinDist:F1} units, duration: {dur:F1}s)."
                            });
                            closeMinDist = float.MaxValue;
                        }
                        wasClose = isClose;
                    }

                    // Handle still-close at end of recording
                    if (wasClose)
                    {
                        float dur = snapsA[Mathf.Min(count - 1, snapsA.Count - 1)].time - closeStart;
                        string zone = ClassifySpatialZone(closeMidpoint, sceneCenter);
                        events.Add(new SceneEvent
                        {
                            event_id = $"evt_{idx++}",
                            event_type = "interaction",
                            timestamp = closeStart,
                            duration = dur,
                            object_ids = new List<string> { actors[a].actorId, actors[b].actorId },
                            description = $"{actors[a].actorName} and {actors[b].actorName} " +
                                          $"remain in close proximity in the {zone} area " +
                                          $"(closest: {closeMinDist:F1} units, duration: {dur:F1}s)."
                        });
                    }

                    // Overtake detection
                    DetectOvertakes(actors[a], actors[b], sceneCenter, ref idx, events);
                }
            }

            events.Sort((x, y) => x.timestamp.CompareTo(y.timestamp));
            return events;
        }

        static void DetectOvertakes(
            ReplayableActor a, ReplayableActor b,
            Vector3 sceneCenter, ref int idx, List<SceneEvent> events)
        {
            var sa = a.recordedSnapshots;
            var sb = b.recordedSnapshots;
            int count = Mathf.Min(sa.Count, sb.Count);
            if (count < 10) return;

            // Project positions onto their shared general motion direction
            // Use the average velocity direction of both combined
            Vector3 avgDir = Vector3.zero;
            for (int i = 1; i < count; i++)
            {
                avgDir += sa[i].velocity.normalized + sb[i].velocity.normalized;
            }
            avgDir.Normalize();
            if (avgDir.sqrMagnitude < 0.01f) return;

            // Track who is "ahead" along this direction
            bool aWasAhead = Vector3.Dot(sa[0].position, avgDir) >
                             Vector3.Dot(sb[0].position, avgDir);

            for (int i = 1; i < count; i++)
            {
                bool aIsAhead = Vector3.Dot(sa[i].position, avgDir) >
                                Vector3.Dot(sb[i].position, avgDir);
                if (aIsAhead != aWasAhead)
                {
                    // Lead changed
                    float dist = Vector3.Distance(sa[i].position, sb[i].position);
                    if (dist < 10f) // only if they're reasonably close
                    {
                        string overtaker = aIsAhead ? a.actorName : b.actorName;
                        string overtakee = aIsAhead ? b.actorName : a.actorName;
                        string zone = ClassifySpatialZone(
                            (sa[i].position + sb[i].position) * 0.5f, sceneCenter);

                        events.Add(new SceneEvent
                        {
                            event_id = $"evt_{idx++}",
                            event_type = "interaction",
                            timestamp = sa[i].time,
                            object_ids = new List<string> { a.actorId, b.actorId },
                            description = $"{overtaker} overtakes {overtakee} in the {zone} area."
                        });
                    }
                    aWasAhead = aIsAhead;
                }
            }
        }
    }
}
