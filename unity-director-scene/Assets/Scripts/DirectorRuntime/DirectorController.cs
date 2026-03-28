using UnityEngine;

namespace DirectorRuntime
{
    /// <summary>
    /// Main orchestrator for the dynamic scene cinematic director workflow.
    /// Provides runtime UI (OnGUI) for: Start Recording, Stop Recording,
    /// Generate Plan, Play Cinematic.
    /// Wires together SceneRecorder, DirectorApiClient, and CinematicPlayer.
    /// </summary>
    [RequireComponent(typeof(SceneRecorder))]
    [RequireComponent(typeof(DirectorApiClient))]
    [RequireComponent(typeof(CinematicPlayer))]
    public class DirectorController : MonoBehaviour
    {
        [Header("Planning")]
        [Tooltip("User intent / directing prompt sent to backend.")]
        [TextArea(2, 4)]
        public string intent = "Cinematic coverage of the action with dramatic camera angles and smooth transitions.";

        [Header("Cache")]
        [Tooltip("Auto-save timeline to disk after each recording.")]
        public bool autoSaveTimeline = true;

        [Tooltip("Label for saved cache file (blank = use scene_id).")]
        public string cacheLabel = "";

        [Header("Debug")]
        [Tooltip("Save debug JSON artifacts after each request.")]
        public bool saveDebugFiles = true;

        [Header("UI")]
        [Tooltip("GUI scale factor. 0 = auto-detect from screen DPI.")]
        [Range(0f, 4f)]
        public float uiScale = 0f;

        [Header("Demo Quality")]
        [Tooltip("Automatically style scene colors/materials for a cleaner demo look.")]
        public bool autoPolishVisuals = true;

        [Tooltip("Create lightweight decorative props when the scene is too sparse.")]
        public bool createBackdropIfMissing = true;

        [Header("Recording")]
        [Tooltip("Reset waypoint followers to path start before each take.")]
        public bool resetActorsBeforeRecording = true;

        private SceneRecorder _recorder;
        private DirectorApiClient _apiClient;
        private CinematicPlayer _player;

        private enum State { Idle, Recording, Generating, ReadyToPlay, Playing }
        private State _state = State.Idle;
        private string _statusMessage = "Ready.";
        private TemporalGenerateResponseData _lastResponse;

        public string StatusMessage => _statusMessage;
        public bool HasPlan => _lastResponse != null;
        public bool IsRecording => _state == State.Recording;
        public bool IsGenerating => _state == State.Generating;
        public bool IsReadyToPlay => _state == State.ReadyToPlay;
        public bool IsPlaying => _state == State.Playing;

        // Cache browser state
        private string[] _cachedFiles;
        private bool _showCachePicker;

        void Awake()
        {
            _recorder = GetComponent<SceneRecorder>();
            _apiClient = GetComponent<DirectorApiClient>();
            _player = GetComponent<CinematicPlayer>();
            EnsureVisualPolish();
        }

        // ── Workflow actions ──

        public void StartRecording()
        {
            if (_state != State.Idle && _state != State.ReadyToPlay)
            {
                _statusMessage = "Cannot record in current state.";
                return;
            }
            if (resetActorsBeforeRecording)
                ResetActorsToStart();

            // Re-enable live actor movement
            SetActorMovement(true);
            if (!_recorder.StartRecording())
            {
                _state = State.Idle;
                _statusMessage = "No ReplayableActor found. Add at least one actor and retry.";
                return;
            }
            _state = State.Recording;
            _statusMessage = "Recording...";
        }

        public void StopRecording()
        {
            if (_state != State.Recording)
            {
                _statusMessage = "Not recording.";
                return;
            }
            _recorder.StopRecording();
            var timeline = _recorder.BuildTimeline();
            if (timeline == null)
            {
                _statusMessage = "Failed to build timeline.";
                _state = State.Idle;
                return;
            }

            // Auto-save to cache
            string savedPath = null;
            if (autoSaveTimeline)
            {
                string label = string.IsNullOrEmpty(cacheLabel) ? null : cacheLabel;
                savedPath = _recorder.SaveTimeline(label);
            }

            _state = State.Idle;
            _statusMessage = $"Recording stopped. Duration: {_recorder.RecordingDuration:F1}s. Ready to generate.";
            if (savedPath != null)
                _statusMessage += $"\nCached: {System.IO.Path.GetFileName(savedPath)}";
        }

        public void GeneratePlan()
        {
            if (_recorder.lastTimeline == null)
            {
                _statusMessage = "No recording available. Record first.";
                return;
            }
            if (_apiClient.IsBusy)
            {
                _statusMessage = "Request already in progress.";
                return;
            }

            _state = State.Generating;
            _statusMessage = "Sending to backend...";

            _apiClient.SendTemporalGenerate(
                _recorder.lastTimeline,
                intent,
                OnPlanSuccess,
                OnPlanError
            );
        }

        public void PlayCinematic()
        {
            if (_state != State.ReadyToPlay || _lastResponse == null)
            {
                _statusMessage = "No plan available. Generate first.";
                return;
            }

            var actors = FindObjectsByType<ReplayableActor>(FindObjectsSortMode.None);

            // Stop live movement during playback
            SetActorMovement(false);

            _player.Play(
                _lastResponse.temporal_trajectory_plan,
                _lastResponse.temporal_directing_plan,
                actors
            );
            _state = State.Playing;
            _statusMessage = "Playing cinematic...";
        }

        public void StopCinematic()
        {
            _player.Stop();
            SetActorMovement(true);
            _state = State.ReadyToPlay;
            _statusMessage = "Playback stopped. Ready to replay or re-record.";
        }

        // ── Callbacks ──

        private void OnPlanSuccess(TemporalGenerateResponseData response)
        {
            _lastResponse = response;
            int trajCount = response.temporal_trajectory_plan?.trajectories?.Count ?? 0;
            int shotCount = response.temporal_directing_plan?.shots?.Count ?? 0;
            _state = State.ReadyToPlay;
            _statusMessage = $"Plan received! Policy: {response.director_policy}, " +
                             $"Shots: {shotCount}, Trajectories: {trajCount}. Ready to play.";
            Debug.Log($"[DirectorController] {_statusMessage}");

            if (saveDebugFiles)
                _apiClient.SaveDebugArtifacts();
        }

        private void OnPlanError(string error)
        {
            _state = State.Idle;
            _statusMessage = $"Error: {error}";
            Debug.LogError($"[DirectorController] Plan generation failed: {error}");

            if (saveDebugFiles)
                _apiClient.SaveDebugArtifacts();
        }

        private void SetActorMovement(bool enabled)
        {
            var followers = FindObjectsByType<WaypointFollower>(FindObjectsSortMode.None);
            foreach (var f in followers) f.SetActive(enabled);
        }

        private void ResetActorsToStart()
        {
            var followers = FindObjectsByType<WaypointFollower>(FindObjectsSortMode.None);
            foreach (var f in followers)
                f.ResetToStart();
        }

        private void EnsureVisualPolish()
        {
            if (!autoPolishVisuals) return;
            var polish = GetComponent<DemoVisualPolish>();
            if (polish == null)
                polish = gameObject.AddComponent<DemoVisualPolish>();
            polish.createBackdropIfMissing = createBackdropIfMissing;
            polish.Apply();
        }

        void Update()
        {
            // Auto-detect playback end
            if (_state == State.Playing && !_player.IsPlaying)
            {
                SetActorMovement(true);
                _state = State.ReadyToPlay;
                _statusMessage = "Cinematic finished. Ready to replay.";
            }
        }

        // ── Runtime UI ──

        void OnGUI()
        {
            float s = uiScale > 0f ? uiScale : (Screen.dpi > 0 ? Screen.dpi / 96f : 2f);
            s = Mathf.Clamp(s, 1f, 4f);
            var prevMatrix = GUI.matrix;
            GUI.matrix = Matrix4x4.TRS(Vector3.zero, Quaternion.identity, new Vector3(s, s, 1f));

            EnsureStyles();
            float w = 260, h = 36, pad = 6;
            float x = 10, y = 10;

            // Title
            GUI.Label(new Rect(x, y, w, 24), "<b>AI Director</b>", _headerStyle);
            y += 28;

            // Status
            GUI.Label(new Rect(x, y, 400, 20), _statusMessage, _statusStyle);
            y += 24;

            // Intent editor (core user input for directing)
            GUI.Label(new Rect(x, y, w, 20), "<b>Intent</b>", _headerSmallStyle ?? GUI.skin.label);
            y += 20;
            intent = GUI.TextArea(
                new Rect(x, y, 400, 64),
                string.IsNullOrEmpty(intent) ? "" : intent,
                _textAreaStyle ?? GUI.skin.textArea);
            y += 64 + pad;

            if (string.IsNullOrWhiteSpace(intent))
            {
                GUI.Label(
                    new Rect(x, y, 420, 20),
                    "Enter intent before generating (e.g. cinematic race coverage with dramatic cuts).");
                y += 20;
            }

            // Recording controls
            GUI.enabled = (_state == State.Idle || _state == State.ReadyToPlay);
            if (GUI.Button(new Rect(x, y, w, h), "Start Recording"))
                StartRecording();
            y += h + pad;

            GUI.enabled = (_state == State.Recording);
            if (GUI.Button(new Rect(x, y, w, h), "Stop Recording"))
                StopRecording();
            y += h + pad;

            // Generate
            GUI.enabled = (_state == State.Idle || _state == State.ReadyToPlay) &&
                          _recorder.lastTimeline != null &&
                          !string.IsNullOrWhiteSpace(intent) &&
                          !_apiClient.IsBusy;
            if (GUI.Button(new Rect(x, y, w, h), "Generate Plan"))
                GeneratePlan();
            y += h + pad;

            // Playback
            GUI.enabled = (_state == State.ReadyToPlay);
            if (GUI.Button(new Rect(x, y, w, h), "Play Cinematic"))
                PlayCinematic();
            y += h + pad;

            GUI.enabled = (_state == State.Playing);
            if (GUI.Button(new Rect(x, y, w, h), "Stop Playback"))
                StopCinematic();
            y += h + pad;

            GUI.enabled = true;

            // ── Cache controls ──
            y += 8;
            GUI.Label(new Rect(x, y, w, 20), "<b>Timeline Cache</b>", _headerSmallStyle ?? GUI.skin.label);
            y += 22;

            GUI.enabled = (_recorder.lastTimeline != null);
            if (GUI.Button(new Rect(x, y, w, h), "Save Timeline"))
            {
                string label = string.IsNullOrEmpty(cacheLabel) ? null : cacheLabel;
                string path = _recorder.SaveTimeline(label);
                if (path != null)
                    _statusMessage = $"Saved: {System.IO.Path.GetFileName(path)}";
            }
            y += h + pad;

            GUI.enabled = (_state == State.Idle || _state == State.ReadyToPlay);
            if (GUI.Button(new Rect(x, y, w, h), _showCachePicker ? "Hide Cache List" : "Load Cached Timeline"))
            {
                _showCachePicker = !_showCachePicker;
                if (_showCachePicker)
                    _cachedFiles = _recorder.ListCachedTimelines();
            }
            y += h + pad;

            if (_showCachePicker && _cachedFiles != null)
            {
                if (_cachedFiles.Length == 0)
                {
                    GUI.Label(new Rect(x + 10, y, w, 20), "(no cached timelines)");
                    y += 22;
                }
                else
                {
                    for (int i = 0; i < _cachedFiles.Length; i++)
                    {
                        if (GUI.Button(new Rect(x + 10, y, w - 10, 28), _cachedFiles[i]))
                        {
                            if (_recorder.LoadTimeline(_cachedFiles[i]))
                            {
                                _lastResponse = null; // Loaded timeline invalidates any previous plan
                                _state = State.Idle;

                                if (_recorder.ApplyTimelinePose(0f, out int applied, out int missing))
                                {
                                    _statusMessage =
                                        $"Loaded: {_cachedFiles[i]}. Applied start pose to {applied} actor(s)" +
                                        (missing > 0 ? $", missing {missing}." : ".") +
                                        " Ready to generate.";
                                }
                                else
                                {
                                    _statusMessage = $"Loaded: {_cachedFiles[i]}. Timeline is ready to generate.";
                                }
                                _showCachePicker = false;
                            }
                            else
                            {
                                _statusMessage = $"Failed to load {_cachedFiles[i]}.";
                            }
                        }
                        y += 30;
                    }
                }
            }

            GUI.enabled = true;

            // Playback status
            if (_state == State.Playing || _player.IsPlaying)
            {
                y += 4;
                GUI.Label(new Rect(x, y, 400, 20), _player.GetDebugStatus());
                y += 20;
            }

            // Recording timer
            if (_state == State.Recording)
            {
                y += 4;
                float elapsed = Time.time - _recorder.RecordingStartTime;
                GUI.Label(new Rect(x, y, 200, 20), $"REC {elapsed:F1}s",
                    new GUIStyle(GUI.skin.label) { normal = { textColor = Color.red } });
            }

            // Debug info
            if (_state == State.Generating)
            {
                y += 4;
                GUI.Label(new Rect(x, y, 300, 20), "Waiting for backend response...");
            }

            GUI.matrix = prevMatrix;
        }

        // Lazy style caches
        private GUIStyle _headerStyle;
        private GUIStyle _headerSmallStyle;
        private GUIStyle _statusStyle;
        private GUIStyle _textAreaStyle;

        void OnEnable()
        {
            _headerStyle = null;
            _statusStyle = null;
            _headerSmallStyle = null;
            _textAreaStyle = null;
        }

        private void EnsureStyles()
        {
            if (_headerStyle == null)
            {
                _headerStyle = new GUIStyle(GUI.skin.label) { richText = true, fontSize = 16 };
                _headerSmallStyle = new GUIStyle(GUI.skin.label) { richText = true, fontSize = 12 };
                _statusStyle = new GUIStyle(GUI.skin.label) { wordWrap = true, fontSize = 11 };
                _textAreaStyle = new GUIStyle(GUI.skin.textArea) { wordWrap = true, fontSize = 11 };
            }
        }

    }
}
