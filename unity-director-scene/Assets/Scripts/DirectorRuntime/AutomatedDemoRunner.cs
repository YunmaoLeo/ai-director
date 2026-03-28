using System.Collections;
using UnityEngine;

#if UNITY_EDITOR
using UnityEditor;
#endif

namespace DirectorRuntime
{
    /// <summary>
    /// Optional automated end-to-end runtime runner for demo verification.
    /// Runs: record -> generate -> playback and prints pass/fail logs.
    /// </summary>
    [DisallowMultipleComponent]
    [RequireComponent(typeof(DirectorController))]
    [RequireComponent(typeof(CinematicPlayer))]
    public class AutomatedDemoRunner : MonoBehaviour
    {
        [Header("Automation")]
        [Tooltip("Run the full demo flow automatically when entering Play Mode.")]
        public bool runOnPlay = false;

        [Tooltip("How long to record actor motion before generating a plan.")]
        public float recordingSeconds = 8f;

        [Tooltip("Maximum seconds to wait for backend plan generation.")]
        public float generateTimeout = 120f;

        [Tooltip("Maximum seconds to wait for cinematic playback completion.")]
        public float playbackTimeout = 150f;

        [Tooltip("Stop Play Mode automatically when the run finishes.")]
        public bool stopPlayModeOnFinish = false;

        private DirectorController _controller;
        private CinematicPlayer _player;
        private bool _isRunning;

        void Awake()
        {
            _controller = GetComponent<DirectorController>();
            _player = GetComponent<CinematicPlayer>();
        }

        IEnumerator Start()
        {
            if (!runOnPlay) yield break;
            yield return RunDemoFlow();
        }

        [ContextMenu("Run Demo Flow")]
        public void RunDemoFlowNow()
        {
            if (!_isRunning)
                StartCoroutine(RunDemoFlow());
        }

        private IEnumerator RunDemoFlow()
        {
            _isRunning = true;
            Debug.Log("[AutomatedDemoRunner] START");

            // Required for MCP-driven unattended tests where Unity Editor is not focused.
            if (!Application.runInBackground)
            {
                Application.runInBackground = true;
                Debug.Log("[AutomatedDemoRunner] Enabled Application.runInBackground for unattended execution.");
            }

            // Defensive reset in case previous debug/test scripts changed timescale.
            if (Time.timeScale < 0.99f)
            {
                Debug.LogWarning($"[AutomatedDemoRunner] Detected timescale={Time.timeScale:F2}, resetting to 1.0.");
                Time.timeScale = 1f;
            }
            yield return null;

            _controller.StartRecording();
            yield return null;
            if (!_controller.IsRecording)
            {
                Fail("Failed to enter recording state.", true);
                yield break;
            }

            Debug.Log($"[AutomatedDemoRunner] Recording for {recordingSeconds:F1}s...");
            yield return new WaitForSecondsRealtime(recordingSeconds);
            _controller.StopRecording();
            yield return null;

            _controller.GeneratePlan();
            yield return null;
            if (!_controller.IsGenerating && !_controller.IsReadyToPlay)
            {
                Fail("Generate plan did not start.", true);
                yield break;
            }

            float elapsed = 0f;
            while (elapsed < generateTimeout && !_controller.IsReadyToPlay)
            {
                if (!_controller.IsGenerating && !_controller.IsReadyToPlay && elapsed > 1f)
                {
                    Fail($"Plan generation ended without ready state. Status: {_controller.StatusMessage}", true);
                    yield break;
                }

                elapsed += Time.unscaledDeltaTime;
                yield return null;
            }

            if (!_controller.IsReadyToPlay)
            {
                Fail("Timeout waiting for plan generation.", true);
                yield break;
            }

            Debug.Log("[AutomatedDemoRunner] Plan ready, starting playback...");
            _controller.PlayCinematic();
            yield return null;
            if (!_player.IsPlaying)
            {
                Fail("Playback did not start.", true);
                yield break;
            }

            elapsed = 0f;
            while (elapsed < playbackTimeout && _player.IsPlaying)
            {
                elapsed += Time.unscaledDeltaTime;
                yield return null;
            }

            if (_player.IsPlaying)
            {
                _controller.StopCinematic();
                Fail("Playback timeout.", true);
                yield break;
            }

            Debug.Log("[AutomatedDemoRunner] PASS: full demo flow completed.");
            _isRunning = false;
            StopPlayModeIfNeeded();
        }

        private void Fail(string message, bool stopPlaybackIfRunning)
        {
            if (stopPlaybackIfRunning && _player != null && _player.IsPlaying)
                _controller.StopCinematic();

            Debug.LogError($"[AutomatedDemoRunner] FAIL: {message}");
            _isRunning = false;
            StopPlayModeIfNeeded();
        }

        private void StopPlayModeIfNeeded()
        {
#if UNITY_EDITOR
            if (stopPlayModeOnFinish && EditorApplication.isPlaying)
                EditorApplication.isPlaying = false;
#endif
        }
    }
}
