using System;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace DirectorRuntime
{
    /// <summary>
    /// HTTP bridge to the backend temporal planning API.
    /// Sends TemporalGenerateRequestData and returns TemporalGenerateResponseData.
    /// </summary>
    public class DirectorApiClient : MonoBehaviour
    {
        [Header("Backend Connection")]
        [Tooltip("Base URL of the director backend (no trailing slash).")]
        public string backendUrl = "http://localhost:8000";

        [Tooltip("Request timeout in seconds.")]
        public int timeoutSeconds = 120;

        [Header("LLM Settings (optional)")]
        public string llmProvider = "";
        public string llmModel = "";
        public string directorHint = "auto";
        public string directorNotes = "";

        /// <summary>Last raw request JSON for debug.</summary>
        [HideInInspector] public string lastRequestJson;
        /// <summary>Last raw response JSON for debug.</summary>
        [HideInInspector] public string lastResponseJson;

        public bool IsBusy { get; private set; }

        /// <summary>
        /// Sends a temporal generate request to the backend.
        /// Calls onSuccess or onError when complete.
        /// </summary>
        public void SendTemporalGenerate(
            SceneTimelineData timeline,
            string intent,
            Action<TemporalGenerateResponseData> onSuccess,
            Action<string> onError)
        {
            if (IsBusy)
            {
                onError?.Invoke("Request already in progress.");
                return;
            }

            var request = new TemporalGenerateRequestData
            {
                scene_id = timeline.scene_id,
                intent = intent,
                scene_timeline = timeline,
                director_hint = directorHint
            };
            if (!string.IsNullOrEmpty(llmProvider)) request.llm_provider = llmProvider;
            if (!string.IsNullOrEmpty(llmModel)) request.llm_model = llmModel;
            if (!string.IsNullOrEmpty(directorNotes)) request.director_notes = directorNotes;

            lastRequestJson = JsonUtility.ToJson(request, true);
            Debug.Log($"[DirectorApiClient] Sending temporal generate request to {backendUrl}. " +
                      $"SceneId: {timeline.scene_id}, Intent: \"{intent}\"");

            StartCoroutine(PostRequest(
                $"{backendUrl}/api/unity/temporal/generate",
                lastRequestJson,
                onSuccess,
                onError
            ));
        }

        private System.Collections.IEnumerator PostRequest(
            string url,
            string jsonBody,
            Action<TemporalGenerateResponseData> onSuccess,
            Action<string> onError)
        {
            IsBusy = true;
            var bodyBytes = Encoding.UTF8.GetBytes(jsonBody);
            var webReq = new UnityWebRequest(url, "POST")
            {
                uploadHandler = new UploadHandlerRaw(bodyBytes),
                downloadHandler = new DownloadHandlerBuffer(),
                timeout = timeoutSeconds
            };
            webReq.SetRequestHeader("Content-Type", "application/json");

            yield return webReq.SendWebRequest();

            IsBusy = false;

            if (webReq.result != UnityWebRequest.Result.Success)
            {
                string errBody = webReq.downloadHandler?.text ?? "";
                string errMsg = $"HTTP {webReq.responseCode}: {webReq.error}";
                if (!string.IsNullOrEmpty(errBody))
                    errMsg += $"\nBody: {errBody}";
                Debug.LogError($"[DirectorApiClient] Request failed. {errMsg}");
                lastResponseJson = errBody;
                onError?.Invoke(errMsg);
                yield break;
            }

            lastResponseJson = webReq.downloadHandler.text;
            Debug.Log($"[DirectorApiClient] Response received ({lastResponseJson.Length} chars).");

            TemporalGenerateResponseData response;
            try
            {
                response = JsonUtility.FromJson<TemporalGenerateResponseData>(lastResponseJson);
            }
            catch (Exception ex)
            {
                Debug.LogError($"[DirectorApiClient] Failed to parse response: {ex.Message}");
                onError?.Invoke($"Parse error: {ex.Message}");
                yield break;
            }

            if (response == null)
            {
                onError?.Invoke("Parsed response is null.");
                yield break;
            }

            Debug.Log($"[DirectorApiClient] Response parsed. " +
                      $"Policy: {response.director_policy}, " +
                      $"Trajectories: {response.temporal_trajectory_plan?.trajectories?.Count ?? 0}");
            onSuccess?.Invoke(response);
        }

        /// <summary>
        /// Optionally saves the last request and response to local files for debugging.
        /// </summary>
        public void SaveDebugArtifacts(string folder = null)
        {
            if (string.IsNullOrEmpty(folder))
                folder = Application.persistentDataPath;

            if (!string.IsNullOrEmpty(lastRequestJson))
            {
                string reqPath = System.IO.Path.Combine(folder, "last_temporal_request.json");
                System.IO.File.WriteAllText(reqPath, lastRequestJson);
                Debug.Log($"[DirectorApiClient] Request saved to {reqPath}");
            }
            if (!string.IsNullOrEmpty(lastResponseJson))
            {
                string resPath = System.IO.Path.Combine(folder, "last_temporal_response.json");
                System.IO.File.WriteAllText(resPath, lastResponseJson);
                Debug.Log($"[DirectorApiClient] Response saved to {resPath}");
            }
        }
    }
}
