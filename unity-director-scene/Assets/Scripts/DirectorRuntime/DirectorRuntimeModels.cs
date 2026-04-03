using System;
using System.Collections.Generic;
using UnityEngine;

namespace DirectorRuntime
{
    // ── SceneTimeline contract (matches backend scene_timeline.py) ──

    [Serializable]
    public class Vec3
    {
        public float x, y, z;
        public Vec3() { }
        public Vec3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public Vec3(Vector3 v) { x = v.x; y = v.y; z = v.z; }
        public Vector3 ToVector3() => new Vector3(x, y, z);
    }

    [Serializable]
    public class Bounds
    {
        public float width;
        public float length;
        public float height;
    }

    [Serializable]
    public class TimeSpan
    {
        public float start;
        public float end;
        public float duration;
    }

    [Serializable]
    public class SceneObject
    {
        public string id;
        public string name;
        public string category;
        public string description = "";
        public float[] position = new float[3];
        public float[] size = new float[3];
        public float[] forward;
        public float importance = 0.5f;
        public List<string> tags = new List<string>();
    }

    [Serializable]
    public class ObjectTrackSample
    {
        public float timestamp;
        public float[] position = new float[3];
        public float[] rotation = new float[3];
        public float[] velocity = new float[3];
        public bool visible = true;
    }

    [Serializable]
    public class MotionDescriptor
    {
        public float average_speed;
        public float max_speed;
        public float[] direction_trend = new float[] { 0, 0, 0 };
        public string acceleration_bucket = "constant";
        public float total_displacement;
    }

    [Serializable]
    public class ObjectTrack
    {
        public string object_id;
        public List<ObjectTrackSample> samples = new List<ObjectTrackSample>();
        public MotionDescriptor motion = new MotionDescriptor();
        public List<int> keyframe_indices = new List<int>();
    }

    [Serializable]
    public class SceneEvent
    {
        public string event_id;
        public string event_type;
        public float timestamp;
        public float duration;
        public List<string> object_ids = new List<string>();
        public string description = "";
    }

    [Serializable]
    public class SemanticSceneEvent
    {
        public string semantic_id;
        public string label;
        public float time_start;
        public float time_end;
        public List<string> object_ids = new List<string>();
        public string summary = "";
        public string dramatic_role = "develop";
        public string camera_implication = "maintain_subject_continuity";
        public float salience = 0.5f;
        public float confidence = 0.5f;
        public List<string> evidence_event_ids = new List<string>();
        public List<string> tags = new List<string>();
    }

    [Serializable]
    public class CameraCandidate
    {
        public string region_id;
        public float time_start;
        public float time_end;
        public float[] center = new float[3];
        public float radius;
        public float clearance_score = 0.5f;
    }

    [Serializable]
    public class SpatialRelation
    {
        public string type;
        public string source;
        public string target;
    }

    [Serializable]
    public class FreeSpace
    {
        // Serialized as list of polygon rings; kept minimal for now.
        public List<List<float[]>> walkable_regions = new List<List<float[]>>();
        public List<List<float[]>> blocked_regions = new List<List<float[]>>();
        public List<List<float[]>> preferred_open_regions = new List<List<float[]>>();
    }

    [Serializable]
    public class SceneTimelineData
    {
        public string scene_id;
        public string scene_name;
        public string scene_type;
        public string description = "";
        public Bounds bounds = new Bounds();
        public TimeSpan time_span = new TimeSpan();
        public List<SceneObject> objects_static = new List<SceneObject>();
        public List<ObjectTrack> object_tracks = new List<ObjectTrack>();
        public List<SceneEvent> events = new List<SceneEvent>();
        public List<SceneEvent> raw_events = new List<SceneEvent>();
        public List<SemanticSceneEvent> semantic_events = new List<SemanticSceneEvent>();
        public List<CameraCandidate> camera_candidates = new List<CameraCandidate>();
        public List<SpatialRelation> relations = new List<SpatialRelation>();
    }

    // ── Request / Response (matches backend api.py) ──

    [Serializable]
    public class TemporalGenerateRequestData
    {
        public string scene_id;
        public string intent;
        public SceneTimelineData scene_timeline;
        public string llm_provider;
        public string llm_model;
        public string planning_mode = "freeform_llm";
        public string director_hint = "auto";
        public string director_notes;
    }

    [Serializable]
    public class TemporalGenerateResponseData
    {
        public TemporalDirectingPlanData temporal_directing_plan;
        public TemporalTrajectoryPlanData temporal_trajectory_plan;
        public ValidationReportData validation_report;
        public SceneTimelineData scene_timeline;
        public string output_prefix;
        public string scene_id;
        public string intent;
        public string director_policy;
        public string director_rationale;
        public string planning_mode;
        public string saved_at;
    }

    // ── Directing plan (matches backend temporal_directing_plan.py) ──

    [Serializable]
    public class BeatData
    {
        public string beat_id;
        public float time_start;
        public float time_end;
        public string goal;
        public string mood = "neutral";
        public List<string> subjects = new List<string>();
    }

    [Serializable]
    public class TemporalShotData
    {
        public string shot_id;
        public float time_start;
        public float time_end;
        public string goal;
        public string subject;
        public string shot_type;
        public string movement;
        public string pacing = "steady";
        public string rationale = "";
        public string transition_in = "cut";
        public string beat_id = "";
    }

    [Serializable]
    public class CutDecisionItemData
    {
        public string cut_id;
        public float timestamp;
        public string from_camera_id = "";
        public string to_camera_id = "";
        public string transition = "cut";
        public string reason = "";
        public string shot_id = "";
    }

    [Serializable]
    public class TemporalDirectingPlanData
    {
        public string plan_id;
        public string scene_id;
        public string intent;
        public string summary = "";
        public TimeSpan time_span;
        public string director_policy = "balanced";
        public string director_rationale = "";
        public List<BeatData> beats = new List<BeatData>();
        public List<TemporalShotData> shots = new List<TemporalShotData>();
        public List<CutDecisionItemData> edit_decision_list = new List<CutDecisionItemData>();
    }

    // ── Trajectory plan (matches backend temporal_trajectory_plan.py) ──

    [Serializable]
    public class TimedTrajectoryPoint
    {
        public float timestamp;
        public float[] position = new float[3];
        public float[] look_at = new float[3];
        public float fov = 60f;
        public float dutch = 0f;
        public float focus_distance = 10f;
        public float aperture = 5.6f;
        public float focal_length = 50f;
        public float[] lens_shift = new float[2] { 0f, 0f };
        public float bloom_intensity = 0f;
        public float bloom_threshold = 1f;
        public float vignette_intensity = 0f;
        public float post_exposure = 0f;
        public float saturation = 0f;
        public float contrast = 0f;
        public float chromatic_aberration = 0f;
        public float film_grain_intensity = 0f;
        public float motion_blur_intensity = 0f;

        public Vector3 Position => new Vector3(position[0], position[1], position[2]);
        public Vector3 LookAt => new Vector3(look_at[0], look_at[1], look_at[2]);
        public Vector2 LensShift => new Vector2(lens_shift[0], lens_shift[1]);
    }

    [Serializable]
    public class TrajectoryMetrics
    {
        public float visibility_score;
        public float smoothness_score;
        public float framing_score;
        public float occlusion_risk;
        public float clearance_score;
    }

    [Serializable]
    public class TemporalShotTrajectory
    {
        public string shot_id;
        public float time_start;
        public float time_end;
        public string transition_in = "cut";
        public string path_type = "linear";
        public string rig_style = "default";
        public float noise_amplitude = 0f;
        public float noise_frequency = 0f;
        public List<TimedTrajectoryPoint> timed_points = new List<TimedTrajectoryPoint>();
        public TrajectoryMetrics metrics = new TrajectoryMetrics();
    }

    [Serializable]
    public class TemporalTrajectoryPlanData
    {
        public string plan_id;
        public string scene_id;
        public TimeSpan time_span;
        public List<TemporalShotTrajectory> trajectories = new List<TemporalShotTrajectory>();
    }

    // ── Validation report ──

    [Serializable]
    public class ValidationIssue
    {
        public string level;
        public string category;
        public string message;
        public string field = "";
    }

    [Serializable]
    public class ValidationReportData
    {
        public bool is_valid;
        public List<ValidationIssue> errors = new List<ValidationIssue>();
        public List<ValidationIssue> warnings = new List<ValidationIssue>();
    }
}
