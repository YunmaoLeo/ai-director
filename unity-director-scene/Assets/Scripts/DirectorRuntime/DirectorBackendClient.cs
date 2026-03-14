using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace AIDirector.UnityRuntime
{
    public class DirectorBackendClient : MonoBehaviour
    {
        [SerializeField] private string baseUrl = "http://127.0.0.1:8000";
        [SerializeField] private string generatePath = "/api/generate";
        [SerializeField] private string runtimeGeneratePath = "/api/unity/generate";
        [SerializeField] private string bearerToken;

        public IEnumerator GenerateFromSceneId(string sceneId, string intent, Action<GenerateResponseData> onSuccess, Action<string> onError)
        {
            var requestData = new RuntimeGenerateRequestData
            {
                scene_id = sceneId,
                intent = intent
            };

            yield return PostJson(BuildUrl(generatePath), DirectorJsonUtility.ToJson(requestData, false), onSuccess, onError);
        }

        public IEnumerator GenerateFromRuntimeScene(RuntimeGenerateRequestData requestData, Action<GenerateResponseData> onSuccess, Action<string> onError)
        {
            yield return PostJson(BuildUrl(runtimeGeneratePath), DirectorJsonUtility.ToJson(requestData, false), onSuccess, onError);
        }

        private IEnumerator PostJson(string url, string json, Action<GenerateResponseData> onSuccess, Action<string> onError)
        {
            using var request = new UnityWebRequest(url, UnityWebRequest.kHttpVerbPOST);
            var bodyRaw = Encoding.UTF8.GetBytes(json);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");

            if (!string.IsNullOrWhiteSpace(bearerToken))
            {
                request.SetRequestHeader("Authorization", $"Bearer {bearerToken}");
            }

            yield return request.SendWebRequest();

            if (request.result != UnityWebRequest.Result.Success)
            {
                onError?.Invoke($"Backend request failed: {request.error}\n{request.downloadHandler.text}");
                yield break;
            }

            var response = DirectorJsonUtility.FromJson<GenerateResponseData>(request.downloadHandler.text);
            if (response == null)
            {
                onError?.Invoke("Backend response could not be parsed.");
                yield break;
            }

            onSuccess?.Invoke(response);
        }

        private string BuildUrl(string path)
        {
            var trimmedBaseUrl = baseUrl.TrimEnd('/');
            var normalizedPath = path.StartsWith("/") ? path : "/" + path;
            return trimmedBaseUrl + normalizedPath;
        }
    }
}
