using System.Collections;
using UnityEngine;

namespace AIDirector.UnityRuntime
{
    public class DirectorRuntimeController : MonoBehaviour
    {
        private enum PlanningMode
        {
            StaticScene = 0,
            TemporalScene = 1
        }

        [Header("Pipeline")]
        [SerializeField] private PlanningMode planningMode = PlanningMode.StaticScene;
        [SerializeField] private DirectorSceneAnalyzer sceneAnalyzer;
        [SerializeField] private DirectorTemporalSceneAnalyzer temporalSceneAnalyzer;
        [SerializeField] private OpenAIVisionClient openAIVisionClient;
        [SerializeField] private DirectorBackendClient backendClient;
        [SerializeField] private DirectorCameraPlayback cameraPlayback;
        [SerializeField] private bool useVisionAnalysis = true;
        [SerializeField] private bool sendRuntimeSceneSummary = true;
        [SerializeField] private bool autoPlayTrajectory = true;

        [Header("Request")]
        [SerializeField] [TextArea(2, 4)] private string intent = "Create a slow cinematic exploration of this scene.";
        [SerializeField] [TextArea(2, 6)] private string visionPrompt = "Analyze this Unity scene for cinematic camera planning. Summarize major subjects, spatial layout, possible reveals, sightline constraints, and important occluders.";
        [SerializeField] private string cinematicStyle = "auto";
        [SerializeField] [TextArea(1, 4)] private string styleNotes = "";

        [Header("Debug Output")]
        [SerializeField] [TextArea(6, 20)] private string lastSceneSummaryJson;
        [SerializeField] [TextArea(6, 20)] private string lastSceneTimelineJson;
        [SerializeField] [TextArea(6, 20)] private string lastVisionAnalysis;
        [SerializeField] [TextArea(6, 20)] private string lastGenerateResponseJson;
        [SerializeField] [TextArea(6, 20)] private string lastTemporalGenerateResponseJson;
        [SerializeField] private bool pipelineRunning;

        private GenerateResponseData lastResponse;
        private TemporalGenerateResponseData lastTemporalResponse;

        [ContextMenu("Run Director Pipeline")]
        public void RunDirectorPipeline()
        {
            if (pipelineRunning)
            {
                Debug.LogWarning("Director pipeline is already running.");
                return;
            }

            StartCoroutine(RunDirectorPipelineRoutine());
        }

        [ContextMenu("Replay Last Trajectory")]
        public void ReplayLastTrajectory()
        {
            if (lastResponse == null || lastResponse.trajectory_plan == null)
            {
                Debug.LogWarning("No trajectory plan has been generated yet.");
                return;
            }

            cameraPlayback.PlayTrajectoryPlan(lastResponse.trajectory_plan, sceneAnalyzer != null ? sceneAnalyzer.LastNormalizationOffset : Vector3.zero);
        }

        [ContextMenu("Replay Last Temporal Trajectory")]
        public void ReplayLastTemporalTrajectory()
        {
            if (lastTemporalResponse == null || lastTemporalResponse.temporal_trajectory_plan == null)
            {
                Debug.LogWarning("No temporal trajectory plan has been generated yet.");
                return;
            }

            cameraPlayback.PlayTemporalTrajectoryPlan(lastTemporalResponse.temporal_trajectory_plan, sceneAnalyzer != null ? sceneAnalyzer.LastNormalizationOffset : Vector3.zero);
        }

        private IEnumerator RunDirectorPipelineRoutine()
        {
            pipelineRunning = true;
            lastVisionAnalysis = string.Empty;
            lastGenerateResponseJson = string.Empty;
            lastTemporalGenerateResponseJson = string.Empty;

            if (backendClient == null)
            {
                Debug.LogError("Backend client is required.");
                pipelineRunning = false;
                yield break;
            }

            if (planningMode == PlanningMode.TemporalScene)
            {
                yield return RunTemporalPipelineRoutine();
            }
            else
            {
                yield return RunStaticPipelineRoutine();
            }
        }

        private IEnumerator RunStaticPipelineRoutine()
        {
            if (sceneAnalyzer == null)
            {
                Debug.LogError("Scene analyzer is required for static mode.");
                pipelineRunning = false;
                yield break;
            }

            var sceneSummary = sceneAnalyzer.CaptureSceneSummary();
            lastSceneSummaryJson = DirectorJsonUtility.ToJson(sceneSummary);

            yield return RunVisionStep();
            var visionAnalysis = BuildVisionPayload();

            var backendCompleted = false;
            string backendError = null;

            if (sendRuntimeSceneSummary)
            {
                var request = new RuntimeGenerateRequestData
                {
                    scene_id = sceneSummary.scene_id,
                    intent = intent,
                    scene_summary = sceneSummary,
                    vision_analysis = visionAnalysis
                };

                yield return backendClient.GenerateFromRuntimeScene(
                    request,
                    response =>
                    {
                        lastResponse = response;
                        lastGenerateResponseJson = DirectorJsonUtility.ToJson(response);
                        backendCompleted = true;
                    },
                    error =>
                    {
                        backendError = error;
                        backendCompleted = true;
                    });
            }
            else
            {
                yield return backendClient.GenerateFromSceneId(
                    sceneSummary.scene_id,
                    intent,
                    response =>
                    {
                        lastResponse = response;
                        lastGenerateResponseJson = DirectorJsonUtility.ToJson(response);
                        backendCompleted = true;
                    },
                    error =>
                    {
                        backendError = error;
                        backendCompleted = true;
                    });
            }

            while (!backendCompleted)
            {
                yield return null;
            }

            pipelineRunning = false;

            if (!string.IsNullOrWhiteSpace(backendError))
            {
                Debug.LogError(backendError);
                yield break;
            }

            if (autoPlayTrajectory && cameraPlayback != null && lastResponse != null && lastResponse.trajectory_plan != null)
            {
                cameraPlayback.PlayTrajectoryPlan(lastResponse.trajectory_plan, sceneAnalyzer.LastNormalizationOffset);
            }
        }

        private IEnumerator RunTemporalPipelineRoutine()
        {
            if (sceneAnalyzer == null || temporalSceneAnalyzer == null)
            {
                Debug.LogError("Scene analyzer and temporal scene analyzer are required for temporal mode.");
                pipelineRunning = false;
                yield break;
            }

            var timelineReady = false;
            string timelineError = null;
            SceneTimelineData timeline = null;

            yield return temporalSceneAnalyzer.CaptureSceneTimeline(
                data =>
                {
                    timeline = data;
                    timelineReady = true;
                },
                error =>
                {
                    timelineError = error;
                    timelineReady = true;
                });

            while (!timelineReady)
            {
                yield return null;
            }

            if (!string.IsNullOrWhiteSpace(timelineError) || timeline == null)
            {
                pipelineRunning = false;
                Debug.LogError(!string.IsNullOrWhiteSpace(timelineError) ? timelineError : "Timeline capture failed.");
                yield break;
            }

            lastSceneTimelineJson = DirectorJsonUtility.ToJson(timeline);

            yield return RunVisionStep();
            if (!string.IsNullOrWhiteSpace(lastVisionAnalysis))
            {
                timeline.description = string.IsNullOrWhiteSpace(timeline.description)
                    ? $"Vision analysis:\n{lastVisionAnalysis}"
                    : $"{timeline.description}\n\nVision analysis:\n{lastVisionAnalysis}";
            }

            var temporalCompleted = false;
            string temporalError = null;
            var request = new TemporalGenerateRequestData
            {
                scene_id = timeline.scene_id,
                intent = intent,
                scene_timeline = timeline,
                cinematic_style = string.IsNullOrWhiteSpace(cinematicStyle) ? "auto" : cinematicStyle.Trim(),
                style_notes = string.IsNullOrWhiteSpace(styleNotes) ? null : styleNotes.Trim()
            };

            yield return backendClient.GenerateTemporalFromRuntimeTimeline(
                request,
                response =>
                {
                    lastTemporalResponse = response;
                    lastTemporalGenerateResponseJson = DirectorJsonUtility.ToJson(response);
                    temporalCompleted = true;
                },
                error =>
                {
                    temporalError = error;
                    temporalCompleted = true;
                });

            while (!temporalCompleted)
            {
                yield return null;
            }

            pipelineRunning = false;

            if (!string.IsNullOrWhiteSpace(temporalError))
            {
                Debug.LogError(temporalError);
                yield break;
            }

            if (autoPlayTrajectory
                && cameraPlayback != null
                && lastTemporalResponse != null
                && lastTemporalResponse.temporal_trajectory_plan != null)
            {
                cameraPlayback.PlayTemporalTrajectoryPlan(lastTemporalResponse.temporal_trajectory_plan, sceneAnalyzer.LastNormalizationOffset);
            }
        }

        private IEnumerator RunVisionStep()
        {
            lastVisionAnalysis = string.Empty;
            if (!useVisionAnalysis || openAIVisionClient == null)
            {
                yield break;
            }

            var completed = false;
            var failed = false;
            string errorMessage = null;

            yield return openAIVisionClient.AnalyzeSceneView(
                visionPrompt,
                result =>
                {
                    lastVisionAnalysis = result != null ? result.analysis_text : string.Empty;
                    completed = true;
                },
                error =>
                {
                    errorMessage = error;
                    failed = true;
                    completed = true;
                });

            while (!completed)
            {
                yield return null;
            }

            if (failed)
            {
                Debug.LogWarning($"Vision analysis failed: {errorMessage}");
                lastVisionAnalysis = string.Empty;
            }
        }

        private VisionAnalysisData BuildVisionPayload()
        {
            if (string.IsNullOrWhiteSpace(lastVisionAnalysis))
            {
                return null;
            }

            return new VisionAnalysisData
            {
                provider = "openai",
                model = openAIVisionClient != null ? openAIVisionClient.Model : null,
                prompt = visionPrompt,
                analysis_text = lastVisionAnalysis
            };
        }
    }
}
