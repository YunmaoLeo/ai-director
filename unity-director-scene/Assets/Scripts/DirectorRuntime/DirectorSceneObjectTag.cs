using UnityEngine;

namespace AIDirector.UnityRuntime
{
    public class DirectorSceneObjectTag : MonoBehaviour
    {
        [SerializeField] private string objectId;
        [SerializeField] private string displayName;
        [SerializeField] private string category = "environment";
        [SerializeField] [Range(0f, 1f)] private float importance = 0.5f;
        [SerializeField] private string[] tags = new string[0];
        [SerializeField] private bool includeInSceneSummary = true;
        [SerializeField] private bool overrideForward;
        [SerializeField] private Vector3 forward = Vector3.forward;

        public string ObjectId => string.IsNullOrWhiteSpace(objectId) ? gameObject.name.ToLowerInvariant().Replace(" ", "_") : objectId;
        public string DisplayName => string.IsNullOrWhiteSpace(displayName) ? gameObject.name : displayName;
        public string Category => category;
        public float Importance => importance;
        public string[] Tags => tags;
        public bool IncludeInSceneSummary => includeInSceneSummary;

        public Vector3 GetForward()
        {
            return overrideForward ? forward.normalized : transform.forward.normalized;
        }
    }
}
