using System.Collections;
using UnityEngine;

namespace AIDirector.UnityRuntime
{
    public class DirectorRuntimeController : MonoBehaviour
    {
        [Header("Pipeline")]
        [SerializeField] private DirectorSceneAnalyzer sceneAnalyzer;
        [SerializeField] private OpenAIVisionClient openAIVisionClient;
        [SerializeField] private DirectorBackendClient backendClient;
        [SerializeField] private DirectorCameraPlayback cameraPlayback;
        [SerializeField] private bool useVisionAnalysis = true;
        [SerializeField] private bool sendRuntimeSceneSummary = true;
        [SerializeField] private bool autoPlayTrajectory = true;

        [Header("Request")]
        [SerializeField] [TextArea(2, 4)] private string intent = "Create a slow cinematic exploration of this scene.";
        [SerializeField] [TextArea(2, 6)] private string visionPrompt = "Analyze this Unity scene for cinematic camera planning. Summarize major subjects, spatial layout, possible reveals, sightline constraints, and important occluders.";

        [Header("Debug Output")]
        [SerializeField] [TextArea(6, 20)] private string lastSceneSummaryJson;
        [SerializeField] [TextArea(6, 20)] private string lastVisionAnalysis;
        [SerializeField] [TextArea(6, 20)] private string lastGenerateResponseJson;
        [SerializeField] private bool pipelineRunning;

        private GenerateResponseData lastResponse;

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

        private IEnumerator RunDirectorPipelineRoutine()
        {
            pipelineRunning = true;
            lastVisionAnalysis = string.Empty;
            lastGenerateResponseJson = string.Empty;

            if (sceneAnalyzer == null || backendClient == null)
            {
                Debug.LogError("Scene analyzer and backend client are required.");
                pipelineRunning = false;
                yield break;
            }

            var sceneSummary = sceneAnalyzer.CaptureSceneSummary();
            lastSceneSummaryJson = DirectorJsonUtility.ToJson(sceneSummary);
            VisionAnalysisData visionAnalysis = null;

            if (useVisionAnalysis && openAIVisionClient != null)
            {
                var visionCompleted = false;
                var visionFailed = false;
                string visionError = null;

                yield return openAIVisionClient.AnalyzeSceneView(
                    visionPrompt,
                    result =>
                    {
                        visionAnalysis = result;
                        lastVisionAnalysis = result != null ? result.analysis_text : string.Empty;
                        visionCompleted = true;
                    },
                    error =>
                    {
                        visionError = error;
                        visionFailed = true;
                        visionCompleted = true;
                    });

                while (!visionCompleted)
                {
                    yield return null;
                }

                if (visionFailed)
                {
                    Debug.LogWarning($"Vision analysis failed: {visionError}");
                    lastVisionAnalysis = visionError;
                }
            }

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
    }
}
