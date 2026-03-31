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

        public enum PlanningMode
        {
            FreeformLLM,
            CameraDSL
        }

        [Tooltip("Freeform LLM maximizes creative freedom. Camera DSL uses a stronger camera language for more stable and more diverse outputs.")]
        public PlanningMode planningMode = PlanningMode.FreeformLLM;

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
        private SceneRecorder.CachedTimelineInfo[] _cachedFiles;
        private DirectorApiClient.CachedPlanInfo[] _cachedPlans;
        private Vector2 _mainScroll;
        private Vector2 _cacheScroll;
        private bool _uiPanelVisible = true;
        private float _uiPanelVisibility = 1f;
        private float _uiPanelVelocity;
        private bool _showCachePanel = true;
        private CacheTab _activeCacheTab = CacheTab.ShootingPlans;

        private enum CacheTab
        {
            ShootingPlans,
            Timelines
        }

        void Awake()
        {
            if (!Application.runInBackground)
                Application.runInBackground = true;

            _recorder = GetComponent<SceneRecorder>();
            _apiClient = GetComponent<DirectorApiClient>();
            _player = GetComponent<CinematicPlayer>();
            _apiClient.planningMode = GetPlanningModeApiValue();
            RefreshCachedFiles();
            RefreshCachedPlans();
            SetActorMovement(false);
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
                SetActorMovement(false);
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
            RefreshCachedFiles();

            _state = State.Idle;
            _statusMessage = $"Recording stopped. Duration: {_recorder.RecordingDuration:F1}s. Ready to generate.";
            if (savedPath != null)
                _statusMessage += $"\nCached: {System.IO.Path.GetFileName(savedPath)}";

            // Vehicles should only run while recording.
            SetActorMovement(false);
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
            _apiClient.planningMode = GetPlanningModeApiValue();
            _statusMessage = $"Sending to backend ({GetPlanningModeLabel()})...";

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
            SetActorMovement(false);
            _state = State.ReadyToPlay;
            _statusMessage = "Playback stopped. Ready to replay or re-record.";
        }

        // ── Callbacks ──

        private void OnPlanSuccess(TemporalGenerateResponseData response)
        {
            _lastResponse = response;
            int trajCount = response.temporal_trajectory_plan?.trajectories?.Count ?? 0;
            int shotCount = response.temporal_directing_plan?.shots?.Count ?? 0;
            _apiClient.SaveGeneratedPlan(response.scene_id);
            RefreshCachedPlans();
            _state = State.ReadyToPlay;
            _statusMessage = $"Plan received! Policy: {response.director_policy}, " +
                             $"Shots: {shotCount}, Trajectories: {trajCount}, Mode: {GetPlanningModeLabel()}. Ready to play.";
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

        private void RefreshCachedFiles()
        {
            _cachedFiles = _recorder != null
                ? _recorder.ListCachedTimelines()
                : new SceneRecorder.CachedTimelineInfo[0];
        }

        private void RefreshCachedPlans()
        {
            _cachedPlans = _apiClient != null
                ? _apiClient.ListCachedPlans()
                : new DirectorApiClient.CachedPlanInfo[0];
        }

        void Update()
        {
            // Auto-detect playback end
            if (_state == State.Playing && !_player.IsPlaying)
            {
                SetActorMovement(false);
                _state = State.ReadyToPlay;
                _statusMessage = "Cinematic finished. Ready to replay.";
            }

            float targetVisibility = _uiPanelVisible ? 1f : 0f;
            _uiPanelVisibility = Mathf.SmoothDamp(
                _uiPanelVisibility,
                targetVisibility,
                ref _uiPanelVelocity,
                0.16f,
                Mathf.Infinity,
                Mathf.Max(Time.unscaledDeltaTime, 0.0001f));
        }

        // ── Runtime UI ──

        void OnGUI()
        {
            float s = uiScale > 0f
                ? uiScale
                : Mathf.Clamp(
                    Mathf.Min(Screen.width / 1280f, Screen.height / 800f),
                    1.0f,
                    1.35f);
            var prevMatrix = GUI.matrix;
            GUI.matrix = Matrix4x4.TRS(Vector3.zero, Quaternion.identity, new Vector3(s, s, 1f));

            EnsureStyles();
            float viewportWidth = Screen.width / s;
            float viewportHeight = Screen.height / s;
            float outerMargin = Mathf.Clamp(viewportWidth * 0.02f, 16f, 28f);
            float gap = 16f;
            float top = outerMargin;
            float availableWidth = viewportWidth - outerMargin * 2f;
            float availableHeight = viewportHeight - outerMargin * 2f;
            bool canUseTwoColumns = availableWidth >= 980f;
            bool useTwoColumns = canUseTwoColumns && _showCachePanel;
            float animatedVisibility = Mathf.SmoothStep(0f, 1f, Mathf.Clamp01(_uiPanelVisibility));

            if (_cachedFiles == null)
                RefreshCachedFiles();
            if (_cachedPlans == null)
                RefreshCachedPlans();

            DrawPanelToggleButton(new Rect(outerMargin, top, _uiPanelVisible ? 128f : 156f, 48f));
            top += 58f;
            availableHeight -= 58f;

            if (animatedVisibility <= 0.01f)
            {
                GUI.matrix = prevMatrix;
                return;
            }

            float slideOffset = -(1f - animatedVisibility) * 120f;
            Color previousColor = GUI.color;
            GUI.color = new Color(1f, 1f, 1f, animatedVisibility);

            if (useTwoColumns)
            {
                float totalWidth = Mathf.Min(availableWidth, 1080f);
                float leftWidth = Mathf.Clamp(totalWidth * 0.60f, 520f, 660f);
                float rightWidth = totalWidth - leftWidth - gap;
                float panelHeight = Mathf.Min(availableHeight, 860f);
                DrawMainPanel(new Rect(outerMargin + slideOffset, top, leftWidth, panelHeight));
                DrawCachePanel(new Rect(outerMargin + leftWidth + gap + slideOffset, top, rightWidth, panelHeight));
            }
            else
            {
                float mainWidth = Mathf.Min(availableWidth, 720f);
                float mainHeight = _showCachePanel
                    ? Mathf.Min(availableHeight * 0.68f, 620f)
                    : Mathf.Min(availableHeight, 820f);
                DrawMainPanel(new Rect(outerMargin + slideOffset, top, mainWidth, mainHeight));

                if (_showCachePanel)
                {
                    float cacheHeight = Mathf.Min(availableHeight - mainHeight - gap, 360f);
                    if (cacheHeight > 120f)
                        DrawCachePanel(new Rect(outerMargin + slideOffset, top + mainHeight + gap, mainWidth, cacheHeight));
                }
            }

            GUI.color = previousColor;
            GUI.matrix = prevMatrix;
        }

        // Lazy style caches
        private Texture2D _panelTexture;
        private Texture2D _panelAccentTexture;
        private Texture2D _buttonTexture;
        private Texture2D _buttonPrimaryTexture;
        private Texture2D _buttonDangerTexture;
        private Texture2D _buttonDisabledTexture;
        private Texture2D _toggleButtonTexture;
        private Texture2D _statusTexture;
        private Texture2D _cacheItemTexture;
        private Texture2D _scrollbarTrackTexture;
        private Texture2D _scrollbarThumbTexture;
        private GUIStyle _panelStyle;
        private GUIStyle _panelAccentStyle;
        private GUIStyle _headerStyle;
        private GUIStyle _headerSmallStyle;
        private GUIStyle _subtleStyle;
        private GUIStyle _statusStyle;
        private GUIStyle _textAreaStyle;
        private GUIStyle _buttonStyle;
        private GUIStyle _primaryButtonStyle;
        private GUIStyle _dangerButtonStyle;
        private GUIStyle _disabledButtonStyle;
        private GUIStyle _statusCardStyle;
        private GUIStyle _cacheItemStyle;
        private GUIStyle _cacheTitleStyle;
        private GUIStyle _cacheMetaStyle;
        private GUIStyle _tagStyle;
        private GUIStyle _textFieldStyle;
        private GUIStyle _dividerStyle;
        private GUIStyle _toggleButtonStyle;
        private GUIStyle _verticalScrollbarStyle;
        private GUIStyle _verticalScrollbarThumbStyle;
        private GUIStyle _verticalScrollbarButtonStyle;
        private GUIStyle _tabButtonStyle;
        private GUIStyle _activeTabButtonStyle;

        void OnEnable()
        {
            _panelTexture = null;
            _panelAccentTexture = null;
            _buttonTexture = null;
            _buttonPrimaryTexture = null;
            _buttonDangerTexture = null;
            _buttonDisabledTexture = null;
            _toggleButtonTexture = null;
            _statusTexture = null;
            _cacheItemTexture = null;
            _scrollbarTrackTexture = null;
            _scrollbarThumbTexture = null;
            _panelStyle = null;
            _panelAccentStyle = null;
            _headerStyle = null;
            _statusStyle = null;
            _headerSmallStyle = null;
            _subtleStyle = null;
            _textAreaStyle = null;
            _buttonStyle = null;
            _primaryButtonStyle = null;
            _dangerButtonStyle = null;
            _disabledButtonStyle = null;
            _statusCardStyle = null;
            _cacheItemStyle = null;
            _cacheTitleStyle = null;
            _cacheMetaStyle = null;
            _tagStyle = null;
            _textFieldStyle = null;
            _dividerStyle = null;
            _toggleButtonStyle = null;
            _verticalScrollbarStyle = null;
            _verticalScrollbarThumbStyle = null;
            _verticalScrollbarButtonStyle = null;
            _tabButtonStyle = null;
            _activeTabButtonStyle = null;
        }

        private void EnsureStyles()
        {
            if (_headerStyle == null)
            {
                _panelTexture = CreateSolidTexture(new Color(0.08f, 0.10f, 0.13f, 0.94f));
                _panelAccentTexture = CreateSolidTexture(new Color(0.11f, 0.14f, 0.18f, 0.98f));
                _buttonTexture = CreateSolidTexture(new Color(0.17f, 0.20f, 0.24f, 1f));
                _buttonPrimaryTexture = CreateSolidTexture(new Color(0.10f, 0.48f, 0.48f, 1f));
                _buttonDangerTexture = CreateSolidTexture(new Color(0.58f, 0.20f, 0.22f, 1f));
                _buttonDisabledTexture = CreateSolidTexture(new Color(0.16f, 0.17f, 0.19f, 0.75f));
                _toggleButtonTexture = CreateSolidTexture(new Color(0.10f, 0.12f, 0.15f, 0.84f));
                _statusTexture = CreateSolidTexture(new Color(0.12f, 0.16f, 0.21f, 0.95f));
                _cacheItemTexture = CreateSolidTexture(new Color(0.13f, 0.15f, 0.18f, 0.95f));
                _scrollbarTrackTexture = CreateSolidTexture(new Color(1f, 1f, 1f, 0.035f));
                _scrollbarThumbTexture = CreateSolidTexture(new Color(0.88f, 0.91f, 0.95f, 0.18f));

                _panelStyle = new GUIStyle(GUI.skin.box)
                {
                    normal = { background = _panelTexture },
                    border = new RectOffset(16, 16, 16, 16),
                    padding = new RectOffset(18, 18, 18, 18)
                };
                _panelAccentStyle = new GUIStyle(_panelStyle)
                {
                    normal = { background = _panelAccentTexture }
                };

                _headerStyle = new GUIStyle(GUI.skin.label)
                {
                    richText = true,
                    fontSize = 36,
                    fontStyle = FontStyle.Bold,
                    normal = { textColor = new Color(0.96f, 0.98f, 1f, 1f) }
                };
                _headerSmallStyle = new GUIStyle(GUI.skin.label)
                {
                    richText = true,
                    fontSize = 20,
                    fontStyle = FontStyle.Bold,
                    normal = { textColor = new Color(0.92f, 0.95f, 0.98f, 1f) }
                };
                _subtleStyle = new GUIStyle(GUI.skin.label)
                {
                    wordWrap = true,
                    fontSize = 16,
                    normal = { textColor = new Color(0.68f, 0.74f, 0.80f, 1f) }
                };
                _statusStyle = new GUIStyle(GUI.skin.label)
                {
                    wordWrap = true,
                    fontSize = 18,
                    normal = { textColor = new Color(0.92f, 0.96f, 1f, 1f) }
                };
                _textAreaStyle = new GUIStyle(GUI.skin.textArea)
                {
                    wordWrap = true,
                    fontSize = 18,
                    padding = new RectOffset(12, 12, 12, 12),
                    normal = { background = _statusTexture, textColor = Color.white },
                    focused = { background = _statusTexture, textColor = Color.white }
                };
                _textFieldStyle = new GUIStyle(GUI.skin.textField)
                {
                    fontSize = 16,
                    padding = new RectOffset(10, 10, 8, 8),
                    normal = { background = _statusTexture, textColor = Color.white },
                    focused = { background = _statusTexture, textColor = Color.white }
                };
                _buttonStyle = BuildButtonStyle(_buttonTexture, new Color(0.95f, 0.97f, 0.99f, 1f));
                _primaryButtonStyle = BuildButtonStyle(_buttonPrimaryTexture, Color.white);
                _dangerButtonStyle = BuildButtonStyle(_buttonDangerTexture, Color.white);
                _disabledButtonStyle = BuildButtonStyle(_buttonDisabledTexture, new Color(0.62f, 0.66f, 0.70f, 1f));
                _toggleButtonStyle = BuildButtonStyle(_toggleButtonTexture, new Color(0.92f, 0.96f, 1f, 1f));
                _toggleButtonStyle.fontSize = 15;
                _toggleButtonStyle.fixedHeight = 48;
                _tabButtonStyle = BuildButtonStyle(CreateSolidTexture(new Color(0.14f, 0.16f, 0.20f, 0.9f)), new Color(0.78f, 0.84f, 0.90f, 1f));
                _tabButtonStyle.fontSize = 14;
                _tabButtonStyle.fixedHeight = 42;
                _activeTabButtonStyle = BuildButtonStyle(CreateSolidTexture(new Color(0.10f, 0.48f, 0.48f, 0.96f)), Color.white);
                _activeTabButtonStyle.fontSize = 14;
                _activeTabButtonStyle.fixedHeight = 42;
                _statusCardStyle = new GUIStyle(GUI.skin.box)
                {
                    normal = { background = _statusTexture },
                    border = new RectOffset(14, 14, 14, 14),
                    padding = new RectOffset(14, 14, 12, 12)
                };
                _cacheItemStyle = new GUIStyle(GUI.skin.button)
                {
                    normal = { background = _cacheItemTexture, textColor = Color.white },
                    active = { background = _statusTexture, textColor = Color.white },
                    hover = { background = _statusTexture, textColor = Color.white },
                    alignment = TextAnchor.UpperLeft,
                    padding = new RectOffset(14, 14, 12, 12),
                    margin = new RectOffset(0, 0, 0, 10),
                    fixedHeight = 72
                };
                _cacheTitleStyle = new GUIStyle(GUI.skin.label)
                {
                    fontSize = 18,
                    fontStyle = FontStyle.Bold,
                    normal = { textColor = Color.white }
                };
                _cacheMetaStyle = new GUIStyle(GUI.skin.label)
                {
                    fontSize = 15,
                    wordWrap = true,
                    normal = { textColor = new Color(0.71f, 0.78f, 0.84f, 1f) }
                };
                _tagStyle = new GUIStyle(GUI.skin.label)
                {
                    alignment = TextAnchor.MiddleCenter,
                    fontSize = 14,
                    fontStyle = FontStyle.Bold,
                    normal = { textColor = new Color(0.72f, 0.92f, 0.89f, 1f) }
                };
                _dividerStyle = new GUIStyle(GUI.skin.box)
                {
                    normal = { background = CreateSolidTexture(new Color(1f, 1f, 1f, 0.08f)) },
                    margin = new RectOffset(0, 0, 10, 10),
                    fixedHeight = 1
                };
                _verticalScrollbarStyle = new GUIStyle(GUI.skin.verticalScrollbar)
                {
                    normal = { background = _scrollbarTrackTexture },
                    fixedWidth = 8,
                    margin = new RectOffset(8, 0, 2, 2)
                };
                _verticalScrollbarThumbStyle = new GUIStyle(GUI.skin.verticalScrollbarThumb)
                {
                    normal = { background = _scrollbarThumbTexture },
                    hover = { background = _scrollbarThumbTexture },
                    active = { background = _scrollbarThumbTexture },
                    fixedWidth = 8
                };
                _verticalScrollbarButtonStyle = new GUIStyle(GUI.skin.verticalScrollbarUpButton)
                {
                    normal = { background = CreateSolidTexture(new Color(1f, 1f, 1f, 0.01f)) },
                    fixedWidth = 8,
                    fixedHeight = 6
                };

                GUI.skin.verticalScrollbar = _verticalScrollbarStyle;
                GUI.skin.verticalScrollbarThumb = _verticalScrollbarThumbStyle;
                GUI.skin.verticalScrollbarUpButton = _verticalScrollbarButtonStyle;
                GUI.skin.verticalScrollbarDownButton = _verticalScrollbarButtonStyle;
            }
        }

        private GUIStyle BuildButtonStyle(Texture2D background, Color textColor)
        {
            return new GUIStyle(GUI.skin.button)
            {
                normal = { background = background, textColor = textColor },
                hover = { background = background, textColor = textColor },
                active = { background = background, textColor = textColor },
                fontStyle = FontStyle.Bold,
                fontSize = 17,
                alignment = TextAnchor.MiddleCenter,
                padding = new RectOffset(14, 14, 12, 12),
                margin = new RectOffset(0, 0, 0, 8),
                fixedHeight = 56
            };
        }

        private Texture2D CreateSolidTexture(Color color)
        {
            var tex = new Texture2D(1, 1, TextureFormat.RGBA32, false)
            {
                hideFlags = HideFlags.HideAndDontSave
            };
            tex.SetPixel(0, 0, color);
            tex.Apply();
            return tex;
        }

        private void DrawPanelToggleButton(Rect rect)
        {
            string label = _uiPanelVisible ? "Hide UI" : "Open UI";
            if (GUI.Button(rect, label, _toggleButtonStyle))
                _uiPanelVisible = !_uiPanelVisible;
        }

        private void DrawMainPanel(Rect rect)
        {
            GUI.Box(rect, GUIContent.none, _panelAccentStyle);
            GUILayout.BeginArea(rect, GUIContent.none, _panelAccentStyle);
            _mainScroll = GUILayout.BeginScrollView(_mainScroll, false, true, GUIStyle.none, GUI.skin.verticalScrollbar);

            GUILayout.Label("AI Director", _headerStyle);
            GUILayout.Label("Focused runtime console for recording, planning, playback, and cache management.", _subtleStyle);
            GUILayout.Space(10f);

            GUILayout.BeginHorizontal();
            GUILayout.Label("Workspace", _headerSmallStyle);
            GUILayout.FlexibleSpace();
            DrawInlineButton(_showCachePanel ? "Hide Timelines" : "Show Timelines", true, () =>
            {
                _showCachePanel = !_showCachePanel;
                if (_showCachePanel)
                    RefreshCachedFiles();
            }, false);
            GUILayout.EndHorizontal();

            GUILayout.Space(6f);

            DrawStatusCard(rect.width - 72f);
            GUILayout.Space(10f);

            GUILayout.Label("Planning Mode", _headerSmallStyle);
            GUILayout.Label("Switch between raw model creativity and the stronger camera DSL path for more stable, more controllable shot language.", _subtleStyle);
            GUILayout.BeginHorizontal();
            DrawModeButton("Freeform LLM", PlanningMode.FreeformLLM, "Minimal camera grammar restrictions. Best for exploration.");
            GUILayout.Space(8f);
            DrawModeButton("Camera DSL", PlanningMode.CameraDSL, "Richer camera rule system with DSL primitives for stronger repeatability.");
            GUILayout.EndHorizontal();

            GUILayout.Space(10f);

            GUILayout.Label("Directing Intent", _headerSmallStyle);
            GUILayout.Label("Describe the cinematic goal. This prompt is sent to the backend when you generate a plan.", _subtleStyle);
            intent = GUILayout.TextArea(string.IsNullOrEmpty(intent) ? "" : intent, _textAreaStyle, GUILayout.MinHeight(124f));

            GUILayout.Space(8f);
            GUILayout.Label("Optional Cache Label", _headerSmallStyle);
            cacheLabel = GUILayout.TextField(cacheLabel ?? "", _textFieldStyle, GUILayout.Height(30f));
            GUILayout.Label("Leave blank to save with the generated scene id. Custom labels are still supported for manual snapshots.", _subtleStyle);

            GUILayout.Space(10f);
            GUILayout.Box(GUIContent.none, _dividerStyle, GUILayout.ExpandWidth(true));

            GUILayout.Label("Workflow", _headerSmallStyle);
            GUILayout.Space(6f);

            DrawActionButton(
                "Start Recording",
                "Actors stay idle until recording begins.",
                (_state == State.Idle || _state == State.ReadyToPlay),
                true,
                StartRecording);

            DrawActionButton(
                "Stop Recording",
                "Ends capture, builds the timeline, and saves it to cache if auto-save is enabled.",
                _state == State.Recording,
                false,
                StopRecording);

            DrawActionButton(
                "Generate Plan",
                "Sends the latest timeline and intent to the backend director service.",
                (_state == State.Idle || _state == State.ReadyToPlay) &&
                _recorder.lastTimeline != null &&
                !string.IsNullOrWhiteSpace(intent) &&
                !_apiClient.IsBusy,
                true,
                GeneratePlan);

            DrawActionButton(
                "Play Cinematic",
                "Replays the returned camera plan against the recorded motion.",
                _state == State.ReadyToPlay,
                false,
                PlayCinematic);

            DrawActionButton(
                "Stop Playback",
                "Interrupts playback and returns control to the recording state.",
                _state == State.Playing,
                false,
                StopCinematic,
                true);

            GUILayout.Space(8f);
            GUILayout.Box(GUIContent.none, _dividerStyle, GUILayout.ExpandWidth(true));
            GUILayout.Label("Session Notes", _headerSmallStyle);

            if (_state == State.Recording)
                GUILayout.Label($"REC {Time.time - _recorder.RecordingStartTime:F1}s", _tagStyle);
            else if (_state == State.Generating)
                GUILayout.Label("Waiting for backend response...", _tagStyle);
            else if (_state == State.Playing || _player.IsPlaying)
                GUILayout.Label(_player.GetDebugStatus(), _subtleStyle);
            else
                GUILayout.Label($"Current mode: {GetPlanningModeLabel()}. The overlay scales with screen size and keeps cache browsing separate from the main workflow.", _subtleStyle);

            GUILayout.EndScrollView();
            GUILayout.EndArea();
        }

        private void DrawCachePanel(Rect rect)
        {
            GUI.Box(rect, GUIContent.none, _panelStyle);
            GUILayout.BeginArea(rect, GUIContent.none, _panelStyle);

            GUILayout.Label("Timeline Cache", _headerSmallStyle);
            GUILayout.Label("Cached shooting plans and timelines are both sorted newest-first for fast recovery and playback.", _subtleStyle);
            GUILayout.Space(8f);

            GUILayout.BeginHorizontal();
            GUILayout.Label("Saved Takes", _headerSmallStyle);
            GUILayout.FlexibleSpace();
            DrawInlineButton("Collapse", true, () => _showCachePanel = false, false);
            GUILayout.EndHorizontal();

            GUILayout.Space(8f);

            GUILayout.BeginHorizontal();

            bool canManualSave = _recorder.lastTimeline != null;
            DrawInlineButton("Save Current Timeline", canManualSave, () =>
            {
                string label = string.IsNullOrEmpty(cacheLabel) ? null : cacheLabel;
                string path = _recorder.SaveTimeline(label);
                if (path != null)
                {
                    RefreshCachedFiles();
                    _statusMessage = $"Saved: {System.IO.Path.GetFileName(path)}";
                }
            }, true);

            DrawInlineButton("Refresh List", true, () =>
            {
                RefreshCachedPlans();
                RefreshCachedFiles();
            }, false);
            GUILayout.EndHorizontal();

            GUILayout.Space(8f);

            _cacheScroll = GUILayout.BeginScrollView(_cacheScroll, false, true, GUIStyle.none, GUI.skin.verticalScrollbar);
            DrawCacheTabs();
            GUILayout.Space(8f);

            if (_activeCacheTab == CacheTab.ShootingPlans)
            {
                GUILayout.Label("Shooting Plans", _headerSmallStyle);
                GUILayout.Label("Every generated plan is cached automatically. Load one to restore the plan and make it immediately playable.", _subtleStyle);
                GUILayout.Space(6f);

                if (_cachedPlans == null || _cachedPlans.Length == 0)
                {
                    GUILayout.Label("No cached shooting plans yet. Generate a plan once and it will appear here automatically.", _subtleStyle);
                }
                else
                {
                    for (int i = 0; i < _cachedPlans.Length; i++)
                    {
                        var entry = _cachedPlans[i];
                        Rect itemRect = GUILayoutUtility.GetRect(GUIContent.none, _cacheItemStyle, GUILayout.ExpandWidth(true), GUILayout.Height(88f));
                        if (GUI.Button(itemRect, GUIContent.none, _cacheItemStyle))
                        {
                            if (_apiClient.LoadCachedPlan(entry.filePath, out var response, out string planJson))
                            {
                                _lastResponse = response;
                                _state = State.ReadyToPlay;

                                int hydrated = 0;
                                if (response.scene_timeline != null)
                                {
                                    hydrated = _recorder.AdoptTimeline(
                                        response.scene_timeline,
                                        JsonUtility.ToJson(response.scene_timeline, true));
                                    _recorder.ApplyTimelinePose(0f, out _, out _);
                                }

                                _statusMessage = $"Loaded plan: {entry.displayName}. " +
                                                 $"Hydrated {hydrated} actor timeline(s). Ready to play.";
                            }
                            else
                            {
                                _statusMessage = $"Failed to load shooting plan {entry.displayName}.";
                            }
                        }

                        Rect titleRect = new Rect(itemRect.x + 14f, itemRect.y + 10f, itemRect.width - 28f, 22f);
                        Rect metaRect = new Rect(itemRect.x + 14f, itemRect.y + 34f, itemRect.width - 28f, 18f);
                        Rect fileRect = new Rect(itemRect.x + 14f, itemRect.y + 54f, itemRect.width - 28f, 18f);

                        GUI.Label(titleRect, entry.displayName, _cacheTitleStyle);
                        GUI.Label(metaRect, $"Generated {entry.relativeAge}", _cacheMetaStyle);
                        GUI.Label(fileRect, entry.fileName, _cacheMetaStyle);
                    }
                }
            }
            else
            {
                GUILayout.Label("Timelines", _headerSmallStyle);
                GUILayout.Label("Use these when you want to recover a recording without loading a plan.", _subtleStyle);
                GUILayout.Space(6f);

                if (_cachedFiles == null || _cachedFiles.Length == 0)
                {
                    GUILayout.Label("No cached timelines yet. Record a take or save the current timeline to populate this list.", _subtleStyle);
                    GUILayout.EndScrollView();
                    GUILayout.EndArea();
                    return;
                }

                for (int i = 0; i < _cachedFiles.Length; i++)
                {
                    var entry = _cachedFiles[i];
                    Rect itemRect = GUILayoutUtility.GetRect(GUIContent.none, _cacheItemStyle, GUILayout.ExpandWidth(true), GUILayout.Height(88f));
                    if (GUI.Button(itemRect, GUIContent.none, _cacheItemStyle))
                    {
                        if (_recorder.LoadTimeline(entry.filePath))
                        {
                            _lastResponse = null;
                            _state = State.Idle;

                            if (_recorder.ApplyTimelinePose(0f, out int applied, out int missing))
                            {
                                _statusMessage =
                                    $"Loaded: {entry.displayName}. Applied start pose to {applied} actor(s)" +
                                    (missing > 0 ? $", missing {missing}." : ".") +
                                    " Ready to generate.";
                            }
                            else
                            {
                                _statusMessage = $"Loaded: {entry.displayName}. Timeline is ready to generate.";
                            }
                        }
                        else
                        {
                            _statusMessage = $"Failed to load {entry.displayName}.";
                        }
                    }

                    Rect titleRect = new Rect(itemRect.x + 14f, itemRect.y + 10f, itemRect.width - 28f, 22f);
                    Rect metaRect = new Rect(itemRect.x + 14f, itemRect.y + 34f, itemRect.width - 28f, 18f);
                    Rect fileRect = new Rect(itemRect.x + 14f, itemRect.y + 54f, itemRect.width - 28f, 18f);

                    GUI.Label(titleRect, entry.displayName, _cacheTitleStyle);
                    GUI.Label(metaRect, $"Saved {entry.relativeAge}", _cacheMetaStyle);
                    GUI.Label(fileRect, entry.fileName, _cacheMetaStyle);
                }
            }
            GUILayout.EndScrollView();
            GUILayout.EndArea();
        }

        private void DrawCacheTabs()
        {
            GUILayout.BeginHorizontal();
            DrawTabButton("Shooting Plans", CacheTab.ShootingPlans);
            DrawTabButton("Timelines", CacheTab.Timelines);
            GUILayout.EndHorizontal();
        }

        private void DrawTabButton(string label, CacheTab tab)
        {
            bool isActive = _activeCacheTab == tab;
            if (GUILayout.Button(label, isActive ? _activeTabButtonStyle : _tabButtonStyle))
                _activeCacheTab = tab;
        }

        private void DrawModeButton(string label, PlanningMode mode, string description)
        {
            GUILayout.BeginVertical(_statusCardStyle);
            bool isActive = planningMode == mode;
            if (GUILayout.Button(label, isActive ? _activeTabButtonStyle : _tabButtonStyle, GUILayout.Height(42f)))
            {
                planningMode = mode;
                _apiClient.planningMode = GetPlanningModeApiValue();
                _statusMessage = $"Planning mode set to {GetPlanningModeLabel()}.";
            }
            GUILayout.Label(description, _cacheMetaStyle);
            GUILayout.EndVertical();
        }

        private void DrawStatusCard(float contentWidth)
        {
            GUILayout.BeginVertical(_statusCardStyle);
            GUILayout.BeginHorizontal();
            GUILayout.Label(GetStateLabel(), _tagStyle, GUILayout.Width(120f));
            GUILayout.FlexibleSpace();
            GUILayout.Label(_recorder.lastTimeline != null ? "Timeline ready" : "No timeline", _cacheMetaStyle, GUILayout.Width(100f));
            GUILayout.EndHorizontal();

            float height = _statusStyle.CalcHeight(new GUIContent(_statusMessage), Mathf.Max(120f, contentWidth - 32f));
            GUILayout.Label(_statusMessage, _statusStyle, GUILayout.MinHeight(Mathf.Max(38f, height)));
            GUILayout.EndVertical();
        }

        private string GetStateLabel()
        {
            switch (_state)
            {
                case State.Recording:
                    return "RECORDING";
                case State.Generating:
                    return "GENERATING";
                case State.ReadyToPlay:
                    return "READY";
                case State.Playing:
                    return "PLAYBACK";
                default:
                    return "IDLE";
            }
        }

        private string GetPlanningModeApiValue()
        {
            return planningMode == PlanningMode.CameraDSL ? "camera_dsl" : "freeform_llm";
        }

        private string GetPlanningModeLabel()
        {
            return planningMode == PlanningMode.CameraDSL ? "Camera DSL" : "Freeform LLM";
        }

        private void DrawActionButton(string title, string description, bool enabled, bool primary, System.Action onClick, bool danger = false)
        {
            GUILayout.Label(description, _subtleStyle);
            DrawFullWidthButton(title, enabled, onClick, primary, danger);
        }

        private void DrawFullWidthButton(string label, bool enabled, System.Action onClick, bool primary, bool danger)
        {
            bool previousEnabled = GUI.enabled;
            GUI.enabled = enabled;

            GUIStyle style = danger
                ? _dangerButtonStyle
                : primary
                    ? _primaryButtonStyle
                    : _buttonStyle;

            if (!enabled)
                style = _disabledButtonStyle;

            if (GUILayout.Button(label, style, GUILayout.ExpandWidth(true)))
                onClick?.Invoke();

            GUI.enabled = previousEnabled;
        }

        private void DrawInlineButton(string label, bool enabled, System.Action onClick, bool primary)
        {
            bool previousEnabled = GUI.enabled;
            GUI.enabled = enabled;

            GUIStyle style = enabled
                ? (primary ? _primaryButtonStyle : _buttonStyle)
                : _disabledButtonStyle;

            if (GUILayout.Button(label, style, GUILayout.MinWidth(120f)))
                onClick?.Invoke();

            GUI.enabled = previousEnabled;
        }

    }
}
