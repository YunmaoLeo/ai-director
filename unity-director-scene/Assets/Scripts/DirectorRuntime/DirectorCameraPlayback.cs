using System.Collections;
using UnityEngine;

namespace AIDirector.UnityRuntime
{
    public class DirectorCameraPlayback : MonoBehaviour
    {
        [SerializeField] private Camera targetCamera;
        [SerializeField] private Transform coordinateOrigin;
        [SerializeField] private bool loopPlayback;
        [SerializeField] private bool playOnStart;
        [SerializeField] private float defaultLookSmoothing = 8f;

        private Coroutine playbackCoroutine;
        private TrajectoryPlanData queuedPlan;
        private TemporalTrajectoryPlanData queuedTemporalPlan;
        private Vector3 normalizationOffset;

        private void Start()
        {
            if (playOnStart && queuedPlan != null)
            {
                PlayTrajectoryPlan(queuedPlan, normalizationOffset);
            }

            if (playOnStart && queuedTemporalPlan != null)
            {
                PlayTemporalTrajectoryPlan(queuedTemporalPlan, normalizationOffset);
            }
        }

        public void PlayTrajectoryPlan(TrajectoryPlanData trajectoryPlan, Vector3 analysisNormalizationOffset)
        {
            if (trajectoryPlan == null || trajectoryPlan.trajectories == null || trajectoryPlan.trajectories.Count == 0)
            {
                Debug.LogWarning("Trajectory plan is empty.");
                return;
            }

            normalizationOffset = analysisNormalizationOffset;
            queuedPlan = trajectoryPlan;

            if (playbackCoroutine != null)
            {
                StopCoroutine(playbackCoroutine);
            }

            playbackCoroutine = StartCoroutine(PlaybackRoutine(trajectoryPlan));
        }

        public void PlayTemporalTrajectoryPlan(TemporalTrajectoryPlanData trajectoryPlan, Vector3 analysisNormalizationOffset)
        {
            if (trajectoryPlan == null || trajectoryPlan.trajectories == null || trajectoryPlan.trajectories.Count == 0)
            {
                Debug.LogWarning("Temporal trajectory plan is empty.");
                return;
            }

            normalizationOffset = analysisNormalizationOffset;
            queuedTemporalPlan = trajectoryPlan;

            if (playbackCoroutine != null)
            {
                StopCoroutine(playbackCoroutine);
            }

            playbackCoroutine = StartCoroutine(PlaybackTemporalRoutine(trajectoryPlan));
        }

        public void PlayTemporalDirectorPlan(
            TemporalDirectingPlanData directingPlan,
            TemporalTrajectoryPlanData trajectoryPlan,
            Vector3 analysisNormalizationOffset)
        {
            if (trajectoryPlan == null || trajectoryPlan.trajectories == null || trajectoryPlan.trajectories.Count == 0)
            {
                Debug.LogWarning("Temporal trajectory plan is empty.");
                return;
            }

            normalizationOffset = analysisNormalizationOffset;
            queuedTemporalPlan = trajectoryPlan;

            if (playbackCoroutine != null)
            {
                StopCoroutine(playbackCoroutine);
            }

            var hasCuts = directingPlan != null
                && directingPlan.edit_decision_list != null
                && directingPlan.edit_decision_list.Count > 0;
            playbackCoroutine = hasCuts
                ? StartCoroutine(PlaybackDirectorCutRoutine(directingPlan, trajectoryPlan))
                : StartCoroutine(PlaybackTemporalRoutine(trajectoryPlan));
        }

        public void StopPlayback()
        {
            if (playbackCoroutine != null)
            {
                StopCoroutine(playbackCoroutine);
                playbackCoroutine = null;
            }
        }

        private IEnumerator PlaybackRoutine(TrajectoryPlanData trajectoryPlan)
        {
            if (targetCamera == null)
            {
                Debug.LogError("Target camera is not assigned.");
                yield break;
            }

            do
            {
                foreach (var shot in trajectoryPlan.trajectories)
                {
                    yield return PlayShot(shot);
                }
            }
            while (loopPlayback);

            playbackCoroutine = null;
        }

        private IEnumerator PlaybackTemporalRoutine(TemporalTrajectoryPlanData trajectoryPlan)
        {
            if (targetCamera == null)
            {
                Debug.LogError("Target camera is not assigned.");
                yield break;
            }

            do
            {
                foreach (var shot in trajectoryPlan.trajectories)
                {
                    yield return PlayTemporalShot(shot);
                }
            }
            while (loopPlayback);

            playbackCoroutine = null;
        }

        private IEnumerator PlaybackDirectorCutRoutine(
            TemporalDirectingPlanData directingPlan,
            TemporalTrajectoryPlanData trajectoryPlan)
        {
            if (targetCamera == null)
            {
                Debug.LogError("Target camera is not assigned.");
                yield break;
            }

            do
            {
                var cuts = new System.Collections.Generic.List<CutDecisionItemData>(directingPlan.edit_decision_list);
                cuts.Sort((a, b) => a.timestamp.CompareTo(b.timestamp));

                for (var i = 0; i < cuts.Count; i++)
                {
                    var cut = cuts[i];
                    var nextTimestamp = i < cuts.Count - 1 ? cuts[i + 1].timestamp : float.MaxValue;
                    var shotTrajectory = FindShotTrajectoryById(trajectoryPlan, cut.shot_id);
                    if (shotTrajectory == null)
                    {
                        continue;
                    }

                    var segmentStart = Mathf.Max(cut.timestamp, shotTrajectory.time_start);
                    var segmentEnd = Mathf.Min(nextTimestamp, shotTrajectory.time_end);
                    if (segmentEnd <= segmentStart)
                    {
                        continue;
                    }

                    yield return PlayTemporalShotWindow(shotTrajectory, segmentStart, segmentEnd);
                }
            }
            while (loopPlayback);

            playbackCoroutine = null;
        }

        private IEnumerator PlayShot(ShotTrajectoryData shot)
        {
            if (shot.sampled_points == null || shot.sampled_points.Count == 0)
            {
                yield break;
            }

            var shotDuration = Mathf.Max(0.01f, shot.duration);
            targetCamera.fieldOfView = shot.fov > 1f ? shot.fov : targetCamera.fieldOfView;

            for (var pointIndex = 0; pointIndex < shot.sampled_points.Count - 1; pointIndex++)
            {
                var segmentStart = ToWorldPoint(shot.sampled_points[pointIndex]);
                var segmentEnd = ToWorldPoint(shot.sampled_points[pointIndex + 1]);
                var lookAt = ToWorldPoint(shot.look_at_position);
                var segmentDuration = shotDuration / Mathf.Max(1, shot.sampled_points.Count - 1);
                var elapsed = 0f;

                while (elapsed < segmentDuration)
                {
                    var t = elapsed / segmentDuration;
                    targetCamera.transform.position = Vector3.Lerp(segmentStart, segmentEnd, t);
                    var desiredRotation = Quaternion.LookRotation((lookAt - targetCamera.transform.position).normalized, Vector3.up);
                    targetCamera.transform.rotation = Quaternion.Slerp(targetCamera.transform.rotation, desiredRotation, Time.deltaTime * defaultLookSmoothing);
                    elapsed += Time.deltaTime;
                    yield return null;
                }
            }

            var finalLookAt = ToWorldPoint(shot.look_at_position);
            var finalPosition = ToWorldPoint(shot.sampled_points[shot.sampled_points.Count - 1]);
            targetCamera.transform.position = finalPosition;
            targetCamera.transform.rotation = Quaternion.LookRotation((finalLookAt - finalPosition).normalized, Vector3.up);
        }

        private IEnumerator PlayTemporalShot(TemporalShotTrajectoryData shot)
        {
            if (shot.timed_points == null || shot.timed_points.Count == 0)
            {
                yield break;
            }

            if (shot.timed_points.Count == 1)
            {
                var onlyPoint = shot.timed_points[0];
                var onlyPos = ToWorldPoint(onlyPoint.position);
                var onlyLook = ToWorldPoint(onlyPoint.look_at);
                targetCamera.transform.position = onlyPos;
                targetCamera.transform.rotation = Quaternion.LookRotation((onlyLook - onlyPos).normalized, Vector3.up);
                targetCamera.fieldOfView = onlyPoint.fov > 1f ? onlyPoint.fov : targetCamera.fieldOfView;
                yield break;
            }

            for (var pointIndex = 0; pointIndex < shot.timed_points.Count - 1; pointIndex++)
            {
                var startPoint = shot.timed_points[pointIndex];
                var endPoint = shot.timed_points[pointIndex + 1];
                var segmentStart = ToWorldPoint(startPoint.position);
                var segmentEnd = ToWorldPoint(endPoint.position);
                var lookStart = ToWorldPoint(startPoint.look_at);
                var lookEnd = ToWorldPoint(endPoint.look_at);
                var segmentDuration = Mathf.Max(0.01f, endPoint.timestamp - startPoint.timestamp);
                var elapsed = 0f;

                while (elapsed < segmentDuration)
                {
                    var t = elapsed / segmentDuration;
                    targetCamera.transform.position = Vector3.Lerp(segmentStart, segmentEnd, t);

                    var lookAt = Vector3.Lerp(lookStart, lookEnd, t);
                    var lookDirection = (lookAt - targetCamera.transform.position).normalized;
                    if (lookDirection.sqrMagnitude > 0.0001f)
                    {
                        var desiredRotation = Quaternion.LookRotation(lookDirection, Vector3.up);
                        targetCamera.transform.rotation = Quaternion.Slerp(targetCamera.transform.rotation, desiredRotation, Time.deltaTime * defaultLookSmoothing);
                    }

                    var nextFov = Mathf.Lerp(startPoint.fov, endPoint.fov, t);
                    if (nextFov > 1f)
                    {
                        targetCamera.fieldOfView = nextFov;
                    }

                    elapsed += Time.deltaTime;
                    yield return null;
                }
            }

            var finalPoint = shot.timed_points[shot.timed_points.Count - 1];
            var finalPosition = ToWorldPoint(finalPoint.position);
            var finalLookAt = ToWorldPoint(finalPoint.look_at);
            targetCamera.transform.position = finalPosition;
            if (finalPoint.fov > 1f)
            {
                targetCamera.fieldOfView = finalPoint.fov;
            }

            var finalDirection = (finalLookAt - finalPosition).normalized;
            if (finalDirection.sqrMagnitude > 0.0001f)
            {
                targetCamera.transform.rotation = Quaternion.LookRotation(finalDirection, Vector3.up);
            }
        }

        private IEnumerator PlayTemporalShotWindow(TemporalShotTrajectoryData shot, float startTime, float endTime)
        {
            if (shot.timed_points == null || shot.timed_points.Count == 0)
            {
                yield break;
            }

            var currentTime = startTime;
            while (currentTime < endTime)
            {
                var point = SampleTimedPointAtTime(shot, currentTime);
                var nextTime = Mathf.Min(endTime, currentTime + Time.deltaTime);
                var nextPoint = SampleTimedPointAtTime(shot, nextTime);

                var worldPos = ToWorldPoint(point.position);
                var worldLook = ToWorldPoint(point.look_at);
                targetCamera.transform.position = worldPos;
                var lookDir = (worldLook - worldPos).normalized;
                if (lookDir.sqrMagnitude > 0.0001f)
                {
                    var desiredRotation = Quaternion.LookRotation(lookDir, Vector3.up);
                    targetCamera.transform.rotation = Quaternion.Slerp(
                        targetCamera.transform.rotation,
                        desiredRotation,
                        Time.deltaTime * defaultLookSmoothing);
                }

                var fov = Mathf.Lerp(point.fov, nextPoint.fov, 0.5f);
                if (fov > 1f)
                {
                    targetCamera.fieldOfView = fov;
                }

                currentTime = nextTime;
                yield return null;
            }
        }

        private static TemporalShotTrajectoryData FindShotTrajectoryById(TemporalTrajectoryPlanData plan, string shotId)
        {
            if (plan == null || plan.trajectories == null)
            {
                return null;
            }

            foreach (var shot in plan.trajectories)
            {
                if (shot.shot_id == shotId)
                {
                    return shot;
                }
            }

            return null;
        }

        private static TimedTrajectoryPointData SampleTimedPointAtTime(TemporalShotTrajectoryData shot, float timestamp)
        {
            var points = shot.timed_points;
            if (points == null || points.Count == 0)
            {
                return new TimedTrajectoryPointData
                {
                    timestamp = timestamp,
                    position = new[] { 0f, 0f, 0f },
                    look_at = new[] { 0f, 0f, 0f },
                    fov = 60f
                };
            }

            if (points.Count == 1 || timestamp <= points[0].timestamp)
            {
                return points[0];
            }

            var last = points[points.Count - 1];
            if (timestamp >= last.timestamp)
            {
                return last;
            }

            for (var i = 0; i < points.Count - 1; i++)
            {
                var a = points[i];
                var b = points[i + 1];
                if (timestamp < a.timestamp || timestamp > b.timestamp)
                {
                    continue;
                }

                var span = Mathf.Max(0.0001f, b.timestamp - a.timestamp);
                var t = Mathf.Clamp01((timestamp - a.timestamp) / span);
                return new TimedTrajectoryPointData
                {
                    timestamp = timestamp,
                    position = LerpArray3(a.position, b.position, t),
                    look_at = LerpArray3(a.look_at, b.look_at, t),
                    fov = Mathf.Lerp(a.fov, b.fov, t)
                };
            }

            return last;
        }

        private static float[] LerpArray3(float[] a, float[] b, float t)
        {
            var va = a != null && a.Length >= 3 ? new Vector3(a[0], a[1], a[2]) : Vector3.zero;
            var vb = b != null && b.Length >= 3 ? new Vector3(b[0], b[1], b[2]) : Vector3.zero;
            var v = Vector3.Lerp(va, vb, t);
            return new[] { v.x, v.y, v.z };
        }

        private Vector3 ToWorldPoint(float[] point)
        {
            if (point == null || point.Length < 3)
            {
                return Vector3.zero;
            }

            var localPoint = new Vector3(point[0], point[1], point[2]) + normalizationOffset;
            return coordinateOrigin != null ? coordinateOrigin.TransformPoint(localPoint) : localPoint;
        }
    }
}
