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
        private Vector3 normalizationOffset;

        private void Start()
        {
            if (playOnStart && queuedPlan != null)
            {
                PlayTrajectoryPlan(queuedPlan, normalizationOffset);
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
