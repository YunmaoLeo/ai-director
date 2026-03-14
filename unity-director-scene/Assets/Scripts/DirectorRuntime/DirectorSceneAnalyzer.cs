using System.Collections.Generic;
using UnityEngine;

namespace AIDirector.UnityRuntime
{
    public class DirectorSceneAnalyzer : MonoBehaviour
    {
        [Header("Scene Identity")]
        [SerializeField] private string sceneId = "unity_scene";
        [SerializeField] private string sceneName = "Unity Scene";
        [SerializeField] private string sceneType = "interior";
        [SerializeField] [TextArea(2, 5)] private string sceneDescription = "Runtime-generated scene summary from Unity.";

        [Header("Coordinate Space")]
        [SerializeField] private Transform coordinateOrigin;
        [SerializeField] private bool includeUntaggedObjects;
        [SerializeField] private bool includeInactiveObjects;

        public Vector3 LastNormalizationOffset { get; private set; }

        public SceneSummaryData CaptureSceneSummary()
        {
            var discoveredObjects = CollectObjects();
            var sceneSummary = new SceneSummaryData
            {
                scene_id = sceneId,
                scene_name = sceneName,
                scene_type = sceneType,
                description = sceneDescription
            };

            if (discoveredObjects.Count == 0)
            {
                sceneSummary.bounds = new BoundsData();
                return sceneSummary;
            }

            var min = new Vector3(float.MaxValue, float.MaxValue, float.MaxValue);
            var max = new Vector3(float.MinValue, float.MinValue, float.MinValue);

            foreach (var obj in discoveredObjects)
            {
                min = Vector3.Min(min, obj.min);
                max = Vector3.Max(max, obj.max);
            }

            LastNormalizationOffset = min;

            foreach (var obj in discoveredObjects)
            {
                sceneSummary.objects.Add(ToSceneObjectData(obj));
            }

            sceneSummary.bounds = new BoundsData
            {
                width = Mathf.Max(0.01f, max.x - min.x),
                length = Mathf.Max(0.01f, max.z - min.z),
                height = Mathf.Max(0.01f, max.y - min.y)
            };

            sceneSummary.relations = BuildRelations(sceneSummary.objects);
            sceneSummary.description = BuildDescription(sceneSummary);
            return sceneSummary;
        }

        private List<AnalyzedObject> CollectObjects()
        {
            var analyzed = new List<AnalyzedObject>();
            var tags = FindObjectsByType<DirectorSceneObjectTag>(includeInactiveObjects ? FindObjectsInactive.Include : FindObjectsInactive.Exclude, FindObjectsSortMode.None);

            foreach (var tag in tags)
            {
                if (!tag.IncludeInSceneSummary)
                {
                    continue;
                }

                if (!TryBuildAnalyzedObject(tag.gameObject, tag, out var result))
                {
                    continue;
                }

                analyzed.Add(result);
            }

            if (includeUntaggedObjects)
            {
                var renderers = FindObjectsByType<Renderer>(includeInactiveObjects ? FindObjectsInactive.Include : FindObjectsInactive.Exclude, FindObjectsSortMode.None);
                var visitedObjects = new HashSet<GameObject>();
                foreach (var renderer in renderers)
                {
                    if (!visitedObjects.Add(renderer.gameObject))
                    {
                        continue;
                    }

                    if (renderer.GetComponentInParent<DirectorSceneObjectTag>() != null)
                    {
                        continue;
                    }

                    if (!TryBuildAnalyzedObject(renderer.gameObject, null, out var result))
                    {
                        continue;
                    }

                    analyzed.Add(result);
                }
            }

            return analyzed;
        }

        private bool TryBuildAnalyzedObject(GameObject target, DirectorSceneObjectTag tag, out AnalyzedObject analyzedObject)
        {
            analyzedObject = default;

            if (target == null)
            {
                return false;
            }

            if (!includeInactiveObjects && !target.activeInHierarchy)
            {
                return false;
            }

            var hasBounds = TryGetObjectBounds(target, out var bounds);
            var worldCenter = hasBounds ? bounds.center : target.transform.position;
            var worldSize = hasBounds ? bounds.size : Vector3.one * 0.5f;

            var localCenter = ToAnalysisSpace(worldCenter);
            var localMin = ToAnalysisSpace(worldCenter - (worldSize * 0.5f));
            var localMax = ToAnalysisSpace(worldCenter + (worldSize * 0.5f));
            var localSize = localMax - localMin;

            analyzedObject = new AnalyzedObject
            {
                id = tag != null ? tag.ObjectId : target.name.ToLowerInvariant().Replace(" ", "_"),
                displayName = tag != null ? tag.DisplayName : target.name,
                category = tag != null ? tag.Category : "environment",
                importance = tag != null ? tag.Importance : 0.3f,
                tags = tag != null ? tag.Tags : new string[0],
                center = localCenter,
                size = new Vector3(Mathf.Abs(localSize.x), Mathf.Abs(localSize.y), Mathf.Abs(localSize.z)),
                forward = tag != null ? ToAnalysisDirection(tag.GetForward()) : ToAnalysisDirection(target.transform.forward),
                min = Vector3.Min(localMin, localMax),
                max = Vector3.Max(localMin, localMax)
            };

            return true;
        }

        private SceneObjectData ToSceneObjectData(AnalyzedObject analyzedObject)
        {
            return new SceneObjectData
            {
                id = analyzedObject.id,
                name = analyzedObject.displayName,
                category = analyzedObject.category,
                position = ToFloatArray(analyzedObject.center - LastNormalizationOffset),
                size = ToFloatArray(analyzedObject.size),
                forward = ToFloatArray(analyzedObject.forward),
                importance = analyzedObject.importance,
                tags = new List<string>(analyzedObject.tags)
            };
        }

        private List<SpatialRelationData> BuildRelations(List<SceneObjectData> objects)
        {
            var relations = new List<SpatialRelationData>();

            for (var i = 0; i < objects.Count; i++)
            {
                for (var j = i + 1; j < objects.Count; j++)
                {
                    var source = objects[i];
                    var target = objects[j];
                    var sourcePos = ToVector3(source.position);
                    var targetPos = ToVector3(target.position);
                    var horizontalDistance = Vector2.Distance(new Vector2(sourcePos.x, sourcePos.z), new Vector2(targetPos.x, targetPos.z));
                    var verticalDelta = Mathf.Abs(sourcePos.y - targetPos.y);

                    if (horizontalDistance < 1.5f)
                    {
                        relations.Add(new SpatialRelationData { type = "near", source = source.id, target = target.id });
                    }

                    if (sourcePos.y > targetPos.y && verticalDelta < 1.2f && horizontalDistance < 0.75f)
                    {
                        relations.Add(new SpatialRelationData { type = "on_top_of", source = source.id, target = target.id });
                    }
                }
            }

            return relations;
        }

        private string BuildDescription(SceneSummaryData sceneSummary)
        {
            return $"{sceneDescription} Contains {sceneSummary.objects.Count} analyzed objects inside an estimated {sceneSummary.bounds.width:F1}m x {sceneSummary.bounds.length:F1}m x {sceneSummary.bounds.height:F1}m volume.";
        }

        private Vector3 ToAnalysisSpace(Vector3 worldPoint)
        {
            return coordinateOrigin != null ? coordinateOrigin.InverseTransformPoint(worldPoint) : worldPoint;
        }

        private Vector3 ToAnalysisDirection(Vector3 worldDirection)
        {
            return coordinateOrigin != null ? coordinateOrigin.InverseTransformDirection(worldDirection).normalized : worldDirection.normalized;
        }

        private static bool TryGetObjectBounds(GameObject target, out Bounds bounds)
        {
            var renderers = target.GetComponentsInChildren<Renderer>();
            if (renderers.Length > 0)
            {
                bounds = renderers[0].bounds;
                for (var i = 1; i < renderers.Length; i++)
                {
                    bounds.Encapsulate(renderers[i].bounds);
                }

                return true;
            }

            var colliders = target.GetComponentsInChildren<Collider>();
            if (colliders.Length > 0)
            {
                bounds = colliders[0].bounds;
                for (var i = 1; i < colliders.Length; i++)
                {
                    bounds.Encapsulate(colliders[i].bounds);
                }

                return true;
            }

            bounds = default;
            return false;
        }

        private static float[] ToFloatArray(Vector3 value)
        {
            return new[] { value.x, value.y, value.z };
        }

        private static Vector3 ToVector3(float[] values)
        {
            if (values == null || values.Length < 3)
            {
                return Vector3.zero;
            }

            return new Vector3(values[0], values[1], values[2]);
        }

        private struct AnalyzedObject
        {
            public string id;
            public string displayName;
            public string category;
            public float importance;
            public string[] tags;
            public Vector3 center;
            public Vector3 size;
            public Vector3 forward;
            public Vector3 min;
            public Vector3 max;
        }
    }
}
