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
        [Serializable]
        public class CachedPlanInfo
        {
            public string filePath;
            public string fileName;
            public string displayName;
            public string relativeAge;
            public long lastWriteTicks;
        }

        [Header("Backend Connection")]
        [Tooltip("Base URL of the director backend (no trailing slash).")]
        public string backendUrl = "http://localhost:8000";

        [Tooltip("Request timeout in seconds.")]
        public int timeoutSeconds = 120;

        [Header("LLM Settings (optional)")]
        public string llmProvider = "";
        public string llmModel = "";
        public string planningMode = "freeform_llm";
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
                planning_mode = string.IsNullOrEmpty(planningMode) ? "freeform_llm" : planningMode,
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

        public string SaveGeneratedPlan(string label = null)
        {
            if (string.IsNullOrEmpty(lastResponseJson))
                return null;

            string cacheRoot = GetPlanCacheRoot();
            string suffix = System.DateTime.Now.ToString("yyyyMMdd_HHmmssfff");
            string safeLabel = string.IsNullOrEmpty(label) ? suffix : $"{label}_{suffix}";
            string fileName = $"shooting_plan_{safeLabel}.json";
            string path = System.IO.Path.Combine(cacheRoot, fileName);
            System.IO.File.WriteAllText(path, lastResponseJson);
            Debug.Log($"[DirectorApiClient] Shooting plan cached to {path}");
            return path;
        }

        public CachedPlanInfo[] ListCachedPlans()
        {
            string dir = GetPlanCacheRoot();
            if (!System.IO.Directory.Exists(dir))
                return new CachedPlanInfo[0];

            var files = System.IO.Directory.GetFiles(dir, "shooting_plan_*.json");
            var entries = new CachedPlanInfo[files.Length];
            for (int i = 0; i < files.Length; i++)
            {
                string filePath = files[i];
                string fileName = System.IO.Path.GetFileName(filePath);
                var lastWrite = System.IO.File.GetLastWriteTime(filePath);

                entries[i] = new CachedPlanInfo
                {
                    filePath = filePath,
                    fileName = fileName,
                    displayName = lastWrite.ToString("yyyy-MM-dd HH:mm:ss"),
                    relativeAge = FormatRelativeAge(lastWrite),
                    lastWriteTicks = lastWrite.Ticks
                };
            }

            System.Array.Sort(entries, (a, b) => b.lastWriteTicks.CompareTo(a.lastWriteTicks));
            return entries;
        }

        public bool LoadCachedPlan(string pathOrName, out TemporalGenerateResponseData response, out string json)
        {
            response = null;
            json = null;

            string path = pathOrName;
            if (!System.IO.File.Exists(path))
                path = System.IO.Path.Combine(GetPlanCacheRoot(), pathOrName);
            if (!System.IO.File.Exists(path))
                return false;

            json = System.IO.File.ReadAllText(path);
            response = JsonUtility.FromJson<TemporalGenerateResponseData>(json);
            if (response == null)
                return false;

            lastResponseJson = json;
            return true;
        }

        private string GetPlanCacheRoot()
        {
            string projectRoot = System.IO.Path.GetDirectoryName(Application.dataPath);
            string dir = System.IO.Path.Combine(projectRoot, "PlanCache");
            if (!System.IO.Directory.Exists(dir))
                System.IO.Directory.CreateDirectory(dir);
            return dir;
        }

        private static string FormatRelativeAge(System.DateTime timestamp)
        {
            var delta = System.DateTime.Now - timestamp;
            if (delta.TotalSeconds < 60)
                return "just now";
            if (delta.TotalMinutes < 60)
                return $"{Mathf.Max(1, Mathf.FloorToInt((float)delta.TotalMinutes))} min ago";
            if (delta.TotalHours < 24)
                return $"{Mathf.Max(1, Mathf.FloorToInt((float)delta.TotalHours))} hr ago";
            return $"{Mathf.Max(1, Mathf.FloorToInt((float)delta.TotalDays))} day ago";
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
