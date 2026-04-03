using Unity.AI.Navigation;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

public static class HumanInteractionNavMeshBuilder
{
    [MenuItem("AI Director/Rebuild Human Interaction NavMesh")]
    public static void Rebuild()
    {
        var scene = EditorSceneManager.GetActiveScene();
        if (!scene.IsValid() || scene.path != "Assets/Scenes/HumanInteractionScene.unity")
        {
            Debug.LogWarning("[AI Director] Open HumanInteractionScene before rebuilding the navmesh.");
            return;
        }

        var cityBlock = GameObject.Find("CityBlock");
        if (cityBlock == null)
        {
            Debug.LogError("[AI Director] Could not find CityBlock.");
            return;
        }

        var surface = cityBlock.GetComponent<NavMeshSurface>();
        if (surface == null)
        {
            Debug.LogError("[AI Director] CityBlock is missing NavMeshSurface.");
            return;
        }

        surface.BuildNavMesh();
        EditorSceneManager.MarkSceneDirty(scene);
        Debug.Log("[AI Director] HumanInteractionScene navmesh rebuilt.");
    }
}
