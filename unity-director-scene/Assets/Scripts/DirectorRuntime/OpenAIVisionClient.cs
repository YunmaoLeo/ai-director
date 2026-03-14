using System;
using System.Collections;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

namespace AIDirector.UnityRuntime
{
    public class OpenAIVisionClient : MonoBehaviour
    {
        [SerializeField] private string apiKey;
        [SerializeField] private string model = "gpt-4o-mini";
        [SerializeField] private string endpoint = "https://api.openai.com/v1/chat/completions";
        [SerializeField] private Camera analysisCamera;
        [SerializeField] private Vector2Int captureResolution = new Vector2Int(1280, 720);
        [SerializeField] private bool includeImageDataInResult;

        public string Model => model;

        public IEnumerator AnalyzeSceneView(string prompt, Action<VisionAnalysisData> onSuccess, Action<string> onError)
        {
            if (string.IsNullOrWhiteSpace(apiKey))
            {
                onError?.Invoke("OpenAI API key is missing.");
                yield break;
            }

            if (analysisCamera == null)
            {
                onError?.Invoke("Analysis camera is not assigned.");
                yield break;
            }

            byte[] pngBytes = null;
            string captureError = null;

            yield return CaptureCameraPng((bytes, error) =>
            {
                pngBytes = bytes;
                captureError = error;
            });

            if (!string.IsNullOrEmpty(captureError))
            {
                onError?.Invoke(captureError);
                yield break;
            }

            var imageDataUrl = "data:image/png;base64," + Convert.ToBase64String(pngBytes);
            yield return SendVisionRequest(prompt, imageDataUrl, onSuccess, onError);
        }

        private IEnumerator CaptureCameraPng(Action<byte[], string> onCompleted)
        {
            yield return new WaitForEndOfFrame();

            var renderTexture = new RenderTexture(captureResolution.x, captureResolution.y, 24);
            var previousTarget = analysisCamera.targetTexture;
            var previousActive = RenderTexture.active;
            var texture = new Texture2D(captureResolution.x, captureResolution.y, TextureFormat.RGB24, false);

            try
            {
                analysisCamera.targetTexture = renderTexture;
                analysisCamera.Render();
                RenderTexture.active = renderTexture;
                texture.ReadPixels(new Rect(0, 0, captureResolution.x, captureResolution.y), 0, 0);
                texture.Apply();
                onCompleted?.Invoke(texture.EncodeToPNG(), null);
            }
            finally
            {
                analysisCamera.targetTexture = previousTarget;
                RenderTexture.active = previousActive;
                Destroy(renderTexture);
                Destroy(texture);
            }
        }

        private IEnumerator SendVisionRequest(string prompt, string imageDataUrl, Action<VisionAnalysisData> onSuccess, Action<string> onError)
        {
            var requestBody = new OpenAIChatRequestData
            {
                model = model,
                response_format = new OpenAIResponseFormatData { type = "text" }
            };
            requestBody.messages.Add(new OpenAIChatMessageData
            {
                role = "user",
                content =
                {
                    new OpenAIChatContentData { type = "text", text = prompt },
                    new OpenAIChatContentData { type = "image_url", image_url = new OpenAIImageUrlData { url = imageDataUrl } }
                }
            });

            var json = DirectorJsonUtility.ToJson(requestBody, false);
            using var request = new UnityWebRequest(endpoint, UnityWebRequest.kHttpVerbPOST);
            var bodyRaw = Encoding.UTF8.GetBytes(json);
            request.uploadHandler = new UploadHandlerRaw(bodyRaw);
            request.downloadHandler = new DownloadHandlerBuffer();
            request.SetRequestHeader("Content-Type", "application/json");
            request.SetRequestHeader("Authorization", $"Bearer {apiKey}");

            yield return request.SendWebRequest();

            if (request.result != UnityWebRequest.Result.Success)
            {
                onError?.Invoke($"OpenAI request failed: {request.error}\n{request.downloadHandler.text}");
                yield break;
            }

            var response = DirectorJsonUtility.FromJson<OpenAIChatResponseData>(request.downloadHandler.text);
            if (response == null)
            {
                onError?.Invoke("OpenAI response could not be parsed.");
                yield break;
            }

            if (response.error != null && !string.IsNullOrWhiteSpace(response.error.message))
            {
                onError?.Invoke(response.error.message);
                yield break;
            }

            var content = response.choices != null && response.choices.Count > 0 ? response.choices[0].message.content : string.Empty;
            onSuccess?.Invoke(new VisionAnalysisData
            {
                provider = "openai",
                model = model,
                prompt = prompt,
                analysis_text = content,
                image_data_url = includeImageDataInResult ? imageDataUrl : null
            });
        }
    }
}
