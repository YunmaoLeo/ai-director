using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace DirectorRuntime.Editor
{
    /// <summary>
    /// One-click polished demo builder.
    /// Creates a compact slot-car style arena with two cars, paths, controller,
    /// camera and lighting, and applies visual polish defaults.
    /// Menu: AI Director > Setup Demo Scene
    /// </summary>
    public static class DemoSceneSetup
    {
        private const float TrackTopY = 0.14f;
        private const float PathRideY = TrackTopY;
        private const float WheelRadius = 0.16f;
        private const float WheelHalfWidth = 0.09f;

        [MenuItem("AI Director/Setup Demo Scene")]
        public static void SetupDemo()
        {
            RemoveExisting("DemoWorld");
            RemoveExisting("DirectorController");
            RemoveExisting("PathA");
            RemoveExisting("PathB");
            RemoveExisting("CarA");
            RemoveExisting("CarB");
            RemoveExisting("DemoBackdrop");
            RemoveExisting("Demo Reflection Probe");

            var world = new GameObject("DemoWorld");
            BuildEnvironment(world.transform);

            var pathA = BuildPath("PathA", world.transform, new[]
            {
                new Vector3(-14f, PathRideY, 9.5f),
                new Vector3(-2f, PathRideY, 13.5f),
                new Vector3(10.5f, PathRideY, 11f),
                new Vector3(14f, PathRideY, 2f),
                new Vector3(11f, PathRideY, -9f),
                new Vector3(-2f, PathRideY, -13f),
                new Vector3(-12f, PathRideY, -10.5f),
                new Vector3(-14.5f, PathRideY, -2f),
            });

            var pathB = BuildPath("PathB", world.transform, new[]
            {
                new Vector3(-11f, PathRideY, 7.2f),
                new Vector3(-1f, PathRideY, 10.4f),
                new Vector3(8.3f, PathRideY, 8.4f),
                new Vector3(11.2f, PathRideY, 1.5f),
                new Vector3(8.4f, PathRideY, -7.6f),
                new Vector3(-1f, PathRideY, -10.1f),
                new Vector3(-9.3f, PathRideY, -8.6f),
                new Vector3(-11.2f, PathRideY, -1.3f),
            });

            var carA = BuildCar("CarA", new Color(0.86f, 0.12f, 0.1f), new Color(0.98f, 0.3f, 0.22f), pathA.waypoints[0], world.transform);
            var actorA = carA.AddComponent<ReplayableActor>();
            actorA.actorId = "car_red";
            actorA.actorName = "Red Car";
            actorA.category = "vehicle";
            actorA.importance = 0.86f;
            actorA.tags = new List<string> { "dynamic", "primary", "racer" };
            var followA = carA.AddComponent<WaypointFollower>();
            followA.path = pathA;
            followA.speed = 7.2f;
            followA.alignToPath = true;

            var carB = BuildCar("CarB", new Color(0.13f, 0.25f, 0.86f), new Color(0.3f, 0.55f, 0.96f), pathB.waypoints[0], world.transform);
            var actorB = carB.AddComponent<ReplayableActor>();
            actorB.actorId = "car_blue";
            actorB.actorName = "Blue Car";
            actorB.category = "vehicle";
            actorB.importance = 0.82f;
            actorB.tags = new List<string> { "dynamic", "secondary", "racer" };
            var followB = carB.AddComponent<WaypointFollower>();
            followB.path = pathB;
            followB.speed = 6.5f;
            followB.alignToPath = true;

            var directorGo = new GameObject("DirectorController");
            var recorder = directorGo.AddComponent<SceneRecorder>();
            recorder.sceneName = "Polished Slot-Car Duel";
            recorder.sceneType = "dynamic_scene";
            recorder.sceneDescription = "Two slot-style cars competing on a compact stylized track.";
            recorder.sampleRate = 12f;

            var apiClient = directorGo.AddComponent<DirectorApiClient>();
            apiClient.backendUrl = "http://localhost:8000";
            apiClient.directorHint = "auto";

            var player = directorGo.AddComponent<CinematicPlayer>();
            player.transitionBlendTime = 0.24f;

            var controller = directorGo.AddComponent<DirectorController>();
            controller.intent = "Create energetic and cinematic multi-camera coverage of the two-car competition.";
            controller.resetActorsBeforeRecording = true;

            var runner = directorGo.AddComponent<AutomatedDemoRunner>();
            runner.runOnPlay = false;
            runner.recordingSeconds = 8f;
            runner.generateTimeout = 120f;
            runner.playbackTimeout = 150f;
            runner.stopPlayModeOnFinish = false;

            SetupCameraAndLight();

            Selection.activeGameObject = directorGo;
            EditorSceneManager.MarkSceneDirty(SceneManager.GetActiveScene());
            Debug.Log("[DemoSceneSetup] Demo scene ready. Press Play and use AI Director overlay.");
        }

        private static void BuildEnvironment(Transform parent)
        {
            var basePlane = GameObject.CreatePrimitive(PrimitiveType.Plane);
            basePlane.name = "Ground";
            basePlane.transform.SetParent(parent, false);
            basePlane.transform.localScale = new Vector3(8f, 1f, 8f);
            basePlane.transform.position = Vector3.zero;
            SetLitColor(basePlane, new Color(0.14f, 0.3f, 0.16f), 0.0f, 0.2f);

            var track = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            track.name = "TrackSurface";
            track.transform.SetParent(parent, false);
            track.transform.position = new Vector3(0f, 0.06f, 0f);
            track.transform.localScale = new Vector3(18f, 0.08f, 18f);
            SetLitColor(track, new Color(0.17f, 0.18f, 0.2f), 0.02f, 0.25f);

            var infield = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            infield.name = "Infield";
            infield.transform.SetParent(parent, false);
            infield.transform.position = new Vector3(0f, 0.08f, 0f);
            infield.transform.localScale = new Vector3(9f, 0.1f, 9f);
            SetLitColor(infield, new Color(0.16f, 0.34f, 0.18f), 0.0f, 0.18f);

            BuildBarrierRing(parent, 18.5f, 56);
            BuildLaneMarkers(parent, 11f, 42, new Color(0.96f, 0.96f, 0.94f));
            BuildLaneMarkers(parent, 14f, 52, new Color(0.93f, 0.2f, 0.22f));
            BuildStartGate(parent);
        }

        private static WaypointPath BuildPath(string name, Transform parent, Vector3[] waypoints)
        {
            var go = new GameObject(name);
            go.transform.SetParent(parent, false);
            var path = go.AddComponent<WaypointPath>();
            path.loop = true;
            path.subdivisionsPerSegment = 16;
            path.lineWidth = 0.08f;
            path.showAtRuntime = true;
            path.waypoints = new List<Vector3>(waypoints);
            path.Build();
            return path;
        }

        private static GameObject BuildCar(
            string carName,
            Color bodyColor,
            Color accentColor,
            Vector3 position,
            Transform parent)
        {
            var root = new GameObject(carName);
            root.transform.SetParent(parent, false);
            root.transform.position = position;

            // Main shell and aerodynamic surfaces.
            CreatePart(root.transform, "Body", PrimitiveType.Cube, bodyColor, 0.08f, 0.86f,
                new Vector3(0f, 0.23f, 0f), new Vector3(1.34f, 0.24f, 2.2f));
            CreatePart(root.transform, "Chassis", PrimitiveType.Cube, new Color(0.12f, 0.12f, 0.14f), 0.2f, 0.38f,
                new Vector3(0f, 0.14f, 0f), new Vector3(1.22f, 0.12f, 2.06f));
            CreatePart(root.transform, "Floor", PrimitiveType.Cube, new Color(0.08f, 0.08f, 0.1f), 0.18f, 0.32f,
                new Vector3(0f, 0.07f, -0.03f), new Vector3(1.12f, 0.03f, 1.98f));

            CreatePart(root.transform, "Nose", PrimitiveType.Cube, accentColor, 0.1f, 0.75f,
                new Vector3(0f, 0.18f, 1.03f), new Vector3(0.72f, 0.12f, 0.58f));
            CreatePart(root.transform, "FrontSplitter", PrimitiveType.Cube, accentColor, 0.18f, 0.55f,
                new Vector3(0f, 0.08f, 1.22f), new Vector3(0.94f, 0.03f, 0.26f));
            CreatePart(root.transform, "Cabin", PrimitiveType.Cube, bodyColor, 0.1f, 0.74f,
                new Vector3(0f, 0.34f, -0.06f), new Vector3(0.74f, 0.18f, 1f));
            CreatePart(root.transform, "Canopy", PrimitiveType.Cube, new Color(0.36f, 0.52f, 0.64f, 0.42f), 0.0f, 0.92f,
                new Vector3(0f, 0.42f, -0.02f), new Vector3(0.56f, 0.12f, 0.64f));
            CreatePart(root.transform, "HaloPylon", PrimitiveType.Cube, new Color(0.1f, 0.1f, 0.12f), 0.22f, 0.42f,
                new Vector3(0f, 0.44f, 0.2f), new Vector3(0.06f, 0.12f, 0.06f));
            CreatePart(root.transform, "HaloBridge", PrimitiveType.Cube, new Color(0.1f, 0.1f, 0.12f), 0.22f, 0.42f,
                new Vector3(0f, 0.49f, -0.02f), new Vector3(0.36f, 0.04f, 0.62f));

            CreatePart(root.transform, "SidePod_L", PrimitiveType.Cube, accentColor, 0.16f, 0.64f,
                new Vector3(-0.52f, 0.18f, -0.04f), new Vector3(0.18f, 0.1f, 1.22f));
            CreatePart(root.transform, "SidePod_R", PrimitiveType.Cube, accentColor, 0.16f, 0.64f,
                new Vector3(0.52f, 0.18f, -0.04f), new Vector3(0.18f, 0.1f, 1.22f));
            CreatePart(root.transform, "Mirror_L", PrimitiveType.Sphere, accentColor, 0.18f, 0.72f,
                new Vector3(-0.44f, 0.34f, 0.31f), new Vector3(0.09f, 0.09f, 0.09f));
            CreatePart(root.transform, "Mirror_R", PrimitiveType.Sphere, accentColor, 0.18f, 0.72f,
                new Vector3(0.44f, 0.34f, 0.31f), new Vector3(0.09f, 0.09f, 0.09f));

            CreatePart(root.transform, "FrontWing", PrimitiveType.Cube, accentColor, 0.18f, 0.55f,
                new Vector3(0f, 0.11f, 1.36f), new Vector3(1.16f, 0.04f, 0.18f));
            CreatePart(root.transform, "EngineCover", PrimitiveType.Cube, bodyColor, 0.1f, 0.74f,
                new Vector3(0f, 0.3f, -0.78f), new Vector3(0.64f, 0.16f, 0.68f));
            CreatePart(root.transform, "RearWingTop", PrimitiveType.Cube, accentColor, 0.18f, 0.58f,
                new Vector3(0f, 0.37f, -1.28f), new Vector3(1.08f, 0.05f, 0.2f));
            CreatePart(root.transform, "RearWingSupport_L", PrimitiveType.Cube, new Color(0.13f, 0.13f, 0.16f), 0.22f, 0.38f,
                new Vector3(-0.42f, 0.26f, -1.18f), new Vector3(0.06f, 0.22f, 0.06f));
            CreatePart(root.transform, "RearWingSupport_R", PrimitiveType.Cube, new Color(0.13f, 0.13f, 0.16f), 0.22f, 0.38f,
                new Vector3(0.42f, 0.26f, -1.18f), new Vector3(0.06f, 0.22f, 0.06f));
            CreatePart(root.transform, "Diffuser", PrimitiveType.Cube, new Color(0.1f, 0.1f, 0.12f), 0.2f, 0.35f,
                new Vector3(0f, 0.09f, -1.22f), new Vector3(0.94f, 0.05f, 0.22f));

            CreateWheel(root.transform, "WheelFL", new Vector3(-0.56f, WheelRadius, 0.76f));
            CreateWheel(root.transform, "WheelFR", new Vector3(0.56f, WheelRadius, 0.76f));
            CreateWheel(root.transform, "WheelRL", new Vector3(-0.56f, WheelRadius, -0.76f));
            CreateWheel(root.transform, "WheelRR", new Vector3(0.56f, WheelRadius, -0.76f));

            return root;
        }

        private static void CreatePart(
            Transform parent,
            string name,
            PrimitiveType primitive,
            Color color,
            float metallic,
            float smoothness,
            Vector3 localPosition,
            Vector3 localScale)
        {
            var go = GameObject.CreatePrimitive(primitive);
            go.name = name;
            go.transform.SetParent(parent, false);
            go.transform.localPosition = localPosition;
            go.transform.localScale = localScale;
            SetLitColor(go, color, metallic, smoothness);
        }

        private static void CreateWheel(Transform parent, string name, Vector3 localPos)
        {
            var wheel = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            wheel.name = name;
            wheel.transform.SetParent(parent, false);
            wheel.transform.localPosition = localPos;
            wheel.transform.localScale = new Vector3(WheelRadius * 2f, WheelHalfWidth, WheelRadius * 2f);
            wheel.transform.localRotation = Quaternion.Euler(90f, 0f, 0f);
            SetLitColor(wheel, new Color(0.1f, 0.1f, 0.12f), 0.2f, 0.32f);

            var hub = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            hub.name = $"{name}_Hub";
            hub.transform.SetParent(wheel.transform, false);
            hub.transform.localPosition = Vector3.zero;
            hub.transform.localScale = new Vector3(0.42f, 0.6f, 0.42f);
            hub.transform.localRotation = Quaternion.Euler(0f, 0f, 0f);
            SetLitColor(hub, new Color(0.68f, 0.7f, 0.76f), 0.35f, 0.72f);
        }

        private static void BuildBarrierRing(Transform parent, float radius, int count)
        {
            var root = new GameObject("BarrierRing");
            root.transform.SetParent(parent, false);

            for (int i = 0; i < count; i++)
            {
                float angle = i / (float)count * Mathf.PI * 2f;
                var block = GameObject.CreatePrimitive(PrimitiveType.Cube);
                block.name = $"Barrier_{i + 1}";
                block.transform.SetParent(root.transform, false);
                block.transform.position = new Vector3(Mathf.Cos(angle) * radius, 0.45f, Mathf.Sin(angle) * radius);
                block.transform.rotation = Quaternion.Euler(0f, -angle * Mathf.Rad2Deg + 90f, 0f);
                block.transform.localScale = new Vector3(1.2f, 0.8f, 0.35f);

                var c = i % 2 == 0 ? new Color(0.93f, 0.93f, 0.95f) : new Color(0.95f, 0.2f, 0.2f);
                SetLitColor(block, c, 0f, 0.35f);
            }
        }

        private static void BuildLaneMarkers(Transform parent, float radius, int count, Color color)
        {
            var root = new GameObject($"LaneMarker_{radius:F1}");
            root.transform.SetParent(parent, false);

            for (int i = 0; i < count; i++)
            {
                float angle = i / (float)count * Mathf.PI * 2f;
                var marker = GameObject.CreatePrimitive(PrimitiveType.Cube);
                marker.name = $"Marker_{i + 1}";
                marker.transform.SetParent(root.transform, false);
                marker.transform.position = new Vector3(Mathf.Cos(angle) * radius, TrackTopY, Mathf.Sin(angle) * radius);
                marker.transform.rotation = Quaternion.Euler(0f, -angle * Mathf.Rad2Deg + 90f, 0f);
                marker.transform.localScale = new Vector3(0.55f, 0.02f, 0.12f);
                SetLitColor(marker, color, 0f, 0.12f);
            }
        }

        private static void BuildStartGate(Transform parent)
        {
            var gate = new GameObject("StartGate");
            gate.transform.SetParent(parent, false);
            gate.transform.position = new Vector3(0f, 0f, 16.2f);

            var left = GameObject.CreatePrimitive(PrimitiveType.Cube);
            left.name = "Arch_Base_L";
            left.transform.SetParent(gate.transform, false);
            left.transform.localPosition = new Vector3(-2.2f, 1.6f, 0f);
            left.transform.localScale = new Vector3(0.5f, 3.2f, 0.5f);
            SetLitColor(left, new Color(0.4f, 0.42f, 0.46f), 0.04f, 0.36f);

            var right = GameObject.CreatePrimitive(PrimitiveType.Cube);
            right.name = "Arch_Base_R";
            right.transform.SetParent(gate.transform, false);
            right.transform.localPosition = new Vector3(2.2f, 1.6f, 0f);
            right.transform.localScale = new Vector3(0.5f, 3.2f, 0.5f);
            SetLitColor(right, new Color(0.4f, 0.42f, 0.46f), 0.04f, 0.36f);

            var top = GameObject.CreatePrimitive(PrimitiveType.Cube);
            top.name = "Arch_Top";
            top.transform.SetParent(gate.transform, false);
            top.transform.localPosition = new Vector3(0f, 3.1f, 0f);
            top.transform.localScale = new Vector3(5f, 0.45f, 0.5f);
            SetLitColor(top, new Color(0.82f, 0.14f, 0.14f), 0.05f, 0.5f);
        }

        private static void SetupCameraAndLight()
        {
            var cam = Camera.main;
            if (cam == null)
            {
                var camGo = new GameObject("Main Camera");
                cam = camGo.AddComponent<Camera>();
                camGo.tag = "MainCamera";
                camGo.AddComponent<AudioListener>();
            }

            cam.transform.position = new Vector3(-14f, 11f, -17f);
            cam.transform.rotation = Quaternion.Euler(24f, 36f, 0f);
            cam.fieldOfView = 52f;

            var lights = Object.FindObjectsByType<Light>(FindObjectsSortMode.None);
            Light key = null;
            foreach (var l in lights)
            {
                if (l.type == LightType.Directional)
                {
                    key = l;
                    break;
                }
            }
            if (key == null)
            {
                var go = new GameObject("Directional Light");
                key = go.AddComponent<Light>();
                key.type = LightType.Directional;
            }

            key.intensity = 1.25f;
            key.color = new Color(1f, 0.97f, 0.92f);
            key.shadows = LightShadows.Soft;
            key.transform.rotation = Quaternion.Euler(48f, -35f, 0f);
        }

        private static void SetLitColor(GameObject go, Color color, float metallic, float smoothness)
        {
            var renderer = go.GetComponent<Renderer>();
            if (renderer == null) return;

            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null)
                shader = Shader.Find("Standard");

            var mat = new Material(shader);
            if (mat.HasProperty("_BaseColor")) mat.SetColor("_BaseColor", color);
            if (mat.HasProperty("_Color")) mat.SetColor("_Color", color);
            if (mat.HasProperty("_Metallic")) mat.SetFloat("_Metallic", metallic);
            if (mat.HasProperty("_Smoothness")) mat.SetFloat("_Smoothness", smoothness);
            if (mat.HasProperty("_Glossiness")) mat.SetFloat("_Glossiness", smoothness);
            renderer.sharedMaterial = mat;
        }

        private static void RemoveExisting(string objectName)
        {
            while (true)
            {
                var existing = GameObject.Find(objectName);
                if (existing == null)
                    break;

                Object.DestroyImmediate(existing);
            }
        }
    }
}
