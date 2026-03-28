using UnityEngine;
using UnityEngine.Rendering;

namespace DirectorRuntime
{
    /// <summary>
    /// Lightweight visual pass for demo scenes:
    /// - applies distinct car palettes
    /// - adds richer environment materials
    /// - optionally spawns minimal decorative backdrop geometry
    /// - tweaks basic lighting and reflections
    /// </summary>
    [DisallowMultipleComponent]
    public class DemoVisualPolish : MonoBehaviour
    {
        [Tooltip("Apply visual polish automatically on Awake.")]
        public bool applyOnAwake = true;

        [Tooltip("When true, creates simple decorative props if the scene is sparse.")]
        public bool createBackdropIfMissing = true;

        [Tooltip("Tune ambient and key light for a cleaner demo look.")]
        public bool tuneLighting = true;

        [Tooltip("Enable and style waypoint line renderers.")]
        public bool styleWaypointLines = true;

        private static Material _carBodyRed;
        private static Material _carAccentRed;
        private static Material _carBodyBlue;
        private static Material _carAccentBlue;
        private static Material _carWheel;
        private static Material _carCarbon;
        private static Material _carGlass;
        private static Material _trackAsphalt;
        private static Material _grass;
        private static Material _barrierA;
        private static Material _barrierB;
        private static Material _architectural;
        private static Material _grandstand;

        private static Shader GetLitShader()
        {
            var shader = Shader.Find("Universal Render Pipeline/Lit");
            if (shader == null)
                shader = Shader.Find("Standard");
            return shader;
        }

        private static Material BuildLitMaterial(string name, Color baseColor, float metallic, float smoothness)
        {
            var mat = new Material(GetLitShader()) { name = name };

            if (mat.HasProperty("_BaseColor"))
                mat.SetColor("_BaseColor", baseColor);
            if (mat.HasProperty("_Color"))
                mat.SetColor("_Color", baseColor);
            if (mat.HasProperty("_Metallic"))
                mat.SetFloat("_Metallic", metallic);
            if (mat.HasProperty("_Smoothness"))
                mat.SetFloat("_Smoothness", smoothness);
            if (mat.HasProperty("_Glossiness"))
                mat.SetFloat("_Glossiness", smoothness);

            return mat;
        }

        private static void EnsureMaterialCache()
        {
            if (_carBodyRed != null) return;

            _carBodyRed = BuildLitMaterial("Runtime_CarBodyRed", new Color(0.83f, 0.13f, 0.11f), 0.08f, 0.82f);
            _carAccentRed = BuildLitMaterial("Runtime_CarAccentRed", new Color(0.98f, 0.28f, 0.22f), 0.18f, 0.66f);
            _carBodyBlue = BuildLitMaterial("Runtime_CarBodyBlue", new Color(0.12f, 0.28f, 0.86f), 0.08f, 0.82f);
            _carAccentBlue = BuildLitMaterial("Runtime_CarAccentBlue", new Color(0.25f, 0.55f, 0.95f), 0.18f, 0.66f);
            _carWheel = BuildLitMaterial("Runtime_CarWheel", new Color(0.1f, 0.1f, 0.12f), 0.25f, 0.35f);
            _carCarbon = BuildLitMaterial("Runtime_CarCarbon", new Color(0.08f, 0.09f, 0.11f), 0.32f, 0.46f);
            _carGlass = BuildLitMaterial("Runtime_CarGlass", new Color(0.35f, 0.52f, 0.63f, 0.42f), 0.0f, 0.92f);

            if (_carGlass.HasProperty("_Surface")) _carGlass.SetFloat("_Surface", 1f);
            if (_carGlass.HasProperty("_Blend")) _carGlass.SetFloat("_Blend", 0f);
            if (_carGlass.HasProperty("_SrcBlend")) _carGlass.SetFloat("_SrcBlend", 5f);
            if (_carGlass.HasProperty("_DstBlend")) _carGlass.SetFloat("_DstBlend", 10f);
            if (_carGlass.HasProperty("_ZWrite")) _carGlass.SetFloat("_ZWrite", 0f);

            _trackAsphalt = BuildLitMaterial("Runtime_TrackAsphalt", new Color(0.16f, 0.17f, 0.19f), 0.01f, 0.24f);
            _grass = BuildLitMaterial("Runtime_Grass", new Color(0.15f, 0.32f, 0.17f), 0.0f, 0.15f);
            _barrierA = BuildLitMaterial("Runtime_BarrierA", new Color(0.9f, 0.92f, 0.94f), 0.0f, 0.36f);
            _barrierB = BuildLitMaterial("Runtime_BarrierB", new Color(0.95f, 0.25f, 0.23f), 0.0f, 0.36f);
            _architectural = BuildLitMaterial("Runtime_Architectural", new Color(0.55f, 0.56f, 0.61f), 0.0f, 0.28f);
            _grandstand = BuildLitMaterial("Runtime_Grandstand", new Color(0.24f, 0.27f, 0.33f), 0.05f, 0.45f);
        }

        void Awake()
        {
            if (applyOnAwake)
                Apply();
        }

        [ContextMenu("Apply Demo Visual Polish")]
        public void Apply()
        {
            EnsureMaterialCache();
            ApplyVehicleMaterials();
            ApplyEnvironmentMaterials();
            if (styleWaypointLines)
                StyleWaypointPaths();
            if (createBackdropIfMissing)
                EnsureBackdropGeometry();
            if (tuneLighting)
                TuneSceneLighting();
        }

        private void ApplyVehicleMaterials()
        {
            var actors = Object.FindObjectsByType<ReplayableActor>(FindObjectsSortMode.None);
            int paletteIndex = 0;

            foreach (var actor in actors)
            {
                string category = actor.category == null ? "" : actor.category.ToLowerInvariant();
                if (!category.Contains("vehicle") && !category.Contains("car"))
                    continue;

                bool useRedPalette = paletteIndex % 2 == 0;
                string key = ((actor.actorId ?? "") + " " + (actor.actorName ?? "")).ToLowerInvariant();
                if (key.Contains("blue"))
                    useRedPalette = false;
                else if (key.Contains("red"))
                    useRedPalette = true;

                var body = useRedPalette ? _carBodyRed : _carBodyBlue;
                var accent = useRedPalette ? _carAccentRed : _carAccentBlue;

                var renderers = actor.GetComponentsInChildren<Renderer>(true);
                foreach (var renderer in renderers)
                {
                    string name = renderer.gameObject.name.ToLowerInvariant();
                    if (name.Contains("wheel") || name.Contains("tire"))
                        renderer.sharedMaterial = _carWheel;
                    else if (name.Contains("hub") || name.Contains("chassis") || name.Contains("floor") ||
                             name.Contains("support") || name.Contains("halo") || name.Contains("diffuser"))
                        renderer.sharedMaterial = _carCarbon;
                    else if (name.Contains("glass") || name.Contains("window") || name.Contains("canopy"))
                        renderer.sharedMaterial = _carGlass;
                    else if (name.Contains("hood") || name.Contains("spoiler") || name.Contains("accent") ||
                             name.Contains("wing") || name.Contains("sidepod") || name.Contains("nose") ||
                             name.Contains("splitter") || name.Contains("mirror"))
                        renderer.sharedMaterial = accent;
                    else
                        renderer.sharedMaterial = body;
                }

                paletteIndex++;
            }
        }

        private void ApplyEnvironmentMaterials()
        {
            var renderers = Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None);
            foreach (var renderer in renderers)
            {
                if (renderer.GetComponentInParent<ReplayableActor>() != null)
                    continue;

                string name = renderer.gameObject.name.ToLowerInvariant();
                Material target = null;

                if (name.Contains("ground") || name.Contains("track") || name.Contains("ramp"))
                    target = _trackAsphalt;
                else if (name.Contains("infield") || name.Contains("grass"))
                    target = _grass;
                else if (name.Contains("barrier") || name.Contains("guard") || name.Contains("wall"))
                    target = Mathf.Abs(renderer.gameObject.GetInstanceID()) % 2 == 0 ? _barrierA : _barrierB;
                else if (name.Contains("arch") || name.Contains("pylon") || name.Contains("tower"))
                    target = _architectural;

                if (target != null)
                    renderer.sharedMaterial = target;
            }
        }

        private void StyleWaypointPaths()
        {
            var paths = Object.FindObjectsByType<WaypointPath>(FindObjectsSortMode.None);
            for (int i = 0; i < paths.Length; i++)
            {
                paths[i].showAtRuntime = true;
                paths[i].lineWidth = 0.08f;
                paths[i].pathColor = i % 2 == 0
                    ? new Color(1f, 0.84f, 0.3f, 0.75f)
                    : new Color(0.3f, 0.78f, 1f, 0.75f);
                paths[i].Build();
            }
        }

        private void EnsureBackdropGeometry()
        {
            if (GameObject.Find("DemoBackdrop") != null)
                return;

            Vector3 center = Vector3.zero;
            var actors = Object.FindObjectsByType<ReplayableActor>(FindObjectsSortMode.None);
            if (actors.Length > 0)
            {
                for (int i = 0; i < actors.Length; i++)
                    center += actors[i].transform.position;
                center /= actors.Length;
            }

            var root = new GameObject("DemoBackdrop");
            root.transform.position = center;

            float radius = 28f;
            for (int i = 0; i < 10; i++)
            {
                float angle = i / 10f * Mathf.PI * 2f;
                var block = GameObject.CreatePrimitive(PrimitiveType.Cube);
                block.name = $"Grandstand_{i + 1}";
                block.transform.SetParent(root.transform, false);
                block.transform.position = center + new Vector3(Mathf.Cos(angle) * radius, 2f, Mathf.Sin(angle) * radius);
                block.transform.rotation = Quaternion.Euler(0f, -angle * Mathf.Rad2Deg + 90f, 0f);
                block.transform.localScale = new Vector3(10f, 4f, 2.4f);
                var r = block.GetComponent<Renderer>();
                if (r != null) r.sharedMaterial = _grandstand;
            }

            var infield = GameObject.CreatePrimitive(PrimitiveType.Cylinder);
            infield.name = "Infield";
            infield.transform.SetParent(root.transform, false);
            infield.transform.position = center + Vector3.up * -0.45f;
            infield.transform.localScale = new Vector3(7f, 0.1f, 7f);
            var infieldRenderer = infield.GetComponent<Renderer>();
            if (infieldRenderer != null) infieldRenderer.sharedMaterial = _grass;
        }

        private void TuneSceneLighting()
        {
            RenderSettings.ambientMode = AmbientMode.Flat;
            RenderSettings.ambientLight = new Color(0.45f, 0.47f, 0.5f);
            RenderSettings.fog = true;
            RenderSettings.fogColor = new Color(0.74f, 0.79f, 0.86f);
            RenderSettings.fogDensity = 0.004f;

            var lights = Object.FindObjectsByType<Light>(FindObjectsSortMode.None);
            Light keyLight = null;
            foreach (var light in lights)
            {
                if (light.type == LightType.Directional)
                {
                    keyLight = light;
                    break;
                }
            }

            if (keyLight == null)
            {
                var go = new GameObject("Directional Light");
                keyLight = go.AddComponent<Light>();
                keyLight.type = LightType.Directional;
            }

            keyLight.intensity = 1.28f;
            keyLight.color = new Color(1f, 0.97f, 0.92f);
            keyLight.shadows = LightShadows.Soft;
            keyLight.transform.rotation = Quaternion.Euler(46f, -32f, 0f);

            var probes = Object.FindObjectsByType<ReflectionProbe>(FindObjectsSortMode.None);
            ReflectionProbe probe = probes.Length > 0 ? probes[0] : null;
            if (probe == null)
            {
                var probeGo = new GameObject("Demo Reflection Probe");
                probe = probeGo.AddComponent<ReflectionProbe>();
            }
            probe.mode = ReflectionProbeMode.Realtime;
            probe.refreshMode = ReflectionProbeRefreshMode.OnAwake;
            probe.size = new Vector3(140f, 40f, 140f);
            probe.transform.position = Vector3.up * 10f;
            probe.intensity = 0.9f;
        }
    }
}
