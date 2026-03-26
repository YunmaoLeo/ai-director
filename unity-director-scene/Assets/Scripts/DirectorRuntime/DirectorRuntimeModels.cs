using System;
using System.Collections.Generic;

namespace AIDirector.UnityRuntime
{
    [Serializable]
    public class SceneListItemData
    {
        public string filename;
        public string scene_id;
        public string scene_name;
        public string scene_type;
    }

    [Serializable]
    public class BoundsData
    {
        public float width;
        public float length;
        public float height;
    }

    [Serializable]
    public class SceneObjectData
    {
        public string id;
        public string name;
        public string category;
        public float[] position;
        public float[] size;
        public float[] forward;
        public float importance = 0.5f;
        public List<string> tags = new List<string>();
    }

    [Serializable]
    public class SpatialRelationData
    {
        public string type;
        public string source;
        public string target;
    }

    [Serializable]
    public class PolygonRegionData
    {
        public List<float[]> points = new List<float[]>();
    }

    [Serializable]
    public class FreeSpaceData
    {
        public List<PolygonRegionData> walkable_regions = new List<PolygonRegionData>();
        public List<PolygonRegionData> blocked_regions = new List<PolygonRegionData>();
        public List<PolygonRegionData> preferred_open_regions = new List<PolygonRegionData>();
    }

    [Serializable]
    public class SceneSummaryData
    {
        public string scene_id;
        public string scene_name;
        public string scene_type;
        public string description;
        public BoundsData bounds = new BoundsData();
        public List<SceneObjectData> objects = new List<SceneObjectData>();
        public List<SpatialRelationData> relations = new List<SpatialRelationData>();
        public FreeSpaceData free_space;
    }

    [Serializable]
    public class ShotConstraintsData
    {
        public List<string> keep_objects_visible = new List<string>();
        public bool avoid_high_angle;
        public bool avoid_occlusion = true;
        public bool preserve_context;
        public bool end_on_subject;
        public bool maintain_room_readability;
    }

    [Serializable]
    public class ShotData
    {
        public string shot_id;
        public string goal;
        public string subject;
        public string shot_type;
        public string movement;
        public float duration;
        public string pacing;
        public ShotConstraintsData constraints = new ShotConstraintsData();
        public string rationale;
    }

    [Serializable]
    public class DirectingPlanData
    {
        public string plan_id;
        public string scene_id;
        public string intent;
        public string summary;
        public float total_duration;
        public List<ShotData> shots = new List<ShotData>();
    }

    [Serializable]
    public class TrajectoryMetricsData
    {
        public float visibility_score;
        public float smoothness_score;
        public float framing_score;
        public float occlusion_risk;
        public float clearance_score;
    }

    [Serializable]
    public class ShotTrajectoryData
    {
        public string shot_id;
        public float[] start_position;
        public float[] end_position;
        public float[] look_at_position;
        public float fov = 60f;
        public string path_type = "linear";
        public List<float[]> sampled_points = new List<float[]>();
        public float duration = 3f;
        public TrajectoryMetricsData metrics = new TrajectoryMetricsData();
    }

    [Serializable]
    public class TrajectoryPlanData
    {
        public string plan_id;
        public string scene_id;
        public float total_duration;
        public List<ShotTrajectoryData> trajectories = new List<ShotTrajectoryData>();
    }

    [Serializable]
    public class ValidationIssueData
    {
        public string level;
        public string category;
        public string message;
        public string field;
    }

    [Serializable]
    public class ValidationReportData
    {
        public bool is_valid;
        public List<ValidationIssueData> errors = new List<ValidationIssueData>();
        public List<ValidationIssueData> warnings = new List<ValidationIssueData>();
    }

    [Serializable]
    public class GenerateResponseData
    {
        public DirectingPlanData directing_plan = new DirectingPlanData();
        public TrajectoryPlanData trajectory_plan = new TrajectoryPlanData();
        public ValidationReportData validation_report = new ValidationReportData();
    }

    [Serializable]
    public class VisionAnalysisData
    {
        public string provider = "openai";
        public string model;
        public string prompt;
        public string analysis_text;
        public string image_data_url;
    }

    [Serializable]
    public class RuntimeGenerateRequestData
    {
        public string scene_id;
        public string intent;
        public SceneSummaryData scene_summary;
        public VisionAnalysisData vision_analysis;
        public string llm_provider;
        public string llm_model;
    }

    [Serializable]
    public class TimeSpanData
    {
        public float start;
        public float end;
        public float duration;
    }

    [Serializable]
    public class ObjectTrackSampleData
    {
        public float timestamp;
        public float[] position;
        public float[] rotation;
        public float[] velocity;
        public bool visible = true;
    }

    [Serializable]
    public class MotionDescriptorData
    {
        public float average_speed;
        public float max_speed;
        public float[] direction_trend;
        public string acceleration_bucket = "constant";
        public float total_displacement;
    }

    [Serializable]
    public class ObjectTrackData
    {
        public string object_id;
        public List<ObjectTrackSampleData> samples = new List<ObjectTrackSampleData>();
        public MotionDescriptorData motion = new MotionDescriptorData();
        public List<int> keyframe_indices = new List<int>();
    }

    [Serializable]
    public class SceneEventData
    {
        public string event_id;
        public string event_type;
        public float timestamp;
        public float duration;
        public List<string> object_ids = new List<string>();
        public string description;
    }

    [Serializable]
    public class CameraCandidateData
    {
        public string region_id;
        public float time_start;
        public float time_end;
        public float[] center;
        public float radius;
        public float clearance_score = 0.5f;
    }

    [Serializable]
    public class SceneTimelineData
    {
        public string scene_id;
        public string scene_name;
        public string scene_type;
        public string description;
        public BoundsData bounds = new BoundsData();
        public TimeSpanData time_span = new TimeSpanData();
        public List<SceneObjectData> objects_static = new List<SceneObjectData>();
        public List<ObjectTrackData> object_tracks = new List<ObjectTrackData>();
        public List<SceneEventData> events = new List<SceneEventData>();
        public List<CameraCandidateData> camera_candidates = new List<CameraCandidateData>();
        public List<SpatialRelationData> relations = new List<SpatialRelationData>();
        public FreeSpaceData free_space;
    }

    [Serializable]
    public class TemporalGenerateRequestData
    {
        public string scene_id;
        public string intent;
        public SceneTimelineData scene_timeline;
        public string llm_provider;
        public string llm_model;
        public string director_hint;
        public string director_notes;
        // Backward-compat for older backend builds
        public string cinematic_style;
        public string style_notes;
    }

    [Serializable]
    public class BeatData
    {
        public string beat_id;
        public float time_start;
        public float time_end;
        public string goal;
        public string mood;
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
        public string pacing;
        public Dictionary<string, object> constraints = new Dictionary<string, object>();
        public string rationale;
        public string transition_in;
        public string beat_id;
    }

    [Serializable]
    public class CameraProgramItemData
    {
        public string camera_id;
        public string role;
        public string primary_subject;
        public string shot_type_bias;
        public string movement_bias;
        public string notes;
    }

    [Serializable]
    public class CutDecisionItemData
    {
        public string cut_id;
        public float timestamp;
        public string from_camera_id;
        public string to_camera_id;
        public string transition;
        public string reason;
        public string shot_id;
    }

    [Serializable]
    public class TemporalDirectingPlanData
    {
        public string plan_id;
        public string scene_id;
        public string intent;
        public string summary;
        public TimeSpanData time_span;
        public string director_policy;
        public string director_rationale;
        public List<BeatData> beats = new List<BeatData>();
        public List<TemporalShotData> shots = new List<TemporalShotData>();
        public List<CameraProgramItemData> camera_program = new List<CameraProgramItemData>();
        public List<CutDecisionItemData> edit_decision_list = new List<CutDecisionItemData>();
    }

    [Serializable]
    public class TimedTrajectoryPointData
    {
        public float timestamp;
        public float[] position;
        public float[] look_at;
        public float fov = 60f;
    }

    [Serializable]
    public class TemporalShotTrajectoryData
    {
        public string shot_id;
        public float time_start;
        public float time_end;
        public string path_type = "linear";
        public List<TimedTrajectoryPointData> timed_points = new List<TimedTrajectoryPointData>();
        public TrajectoryMetricsData metrics = new TrajectoryMetricsData();
    }

    [Serializable]
    public class TemporalTrajectoryPlanData
    {
        public string plan_id;
        public string scene_id;
        public TimeSpanData time_span;
        public List<TemporalShotTrajectoryData> trajectories = new List<TemporalShotTrajectoryData>();
    }

    [Serializable]
    public class PlanningPassArtifactData
    {
        public string pass_type;
        public int pass_index;
        public string model_provider;
        public string model_id;
        public string input_summary;
        public string output_raw;
        public Dictionary<string, object> output_parsed = new Dictionary<string, object>();
        public float duration_ms;
        public bool success = true;
        public string error_message;
    }

    [Serializable]
    public class TemporalGenerateResponseData
    {
        public TemporalDirectingPlanData temporal_directing_plan = new TemporalDirectingPlanData();
        public TemporalTrajectoryPlanData temporal_trajectory_plan = new TemporalTrajectoryPlanData();
        public ValidationReportData validation_report = new ValidationReportData();
        public List<PlanningPassArtifactData> pass_artifacts = new List<PlanningPassArtifactData>();
        public SceneTimelineData scene_timeline;
        public string output_prefix;
        public string scene_id;
        public string intent;
        public string llm_provider;
        public string llm_model;
        public string director_hint;
        public string director_policy;
        public string director_rationale;
        public string director_notes;
        public string saved_at;
        public bool temporal = true;
    }

    [Serializable]
    public class OpenAIChatRequestData
    {
        public string model;
        public List<OpenAIChatMessageData> messages = new List<OpenAIChatMessageData>();
        public float temperature = 0.2f;
        public OpenAIResponseFormatData response_format;
    }

    [Serializable]
    public class OpenAIResponseFormatData
    {
        public string type = "text";
    }

    [Serializable]
    public class OpenAIChatMessageData
    {
        public string role;
        public List<OpenAIChatContentData> content = new List<OpenAIChatContentData>();
    }

    [Serializable]
    public class OpenAIChatContentData
    {
        public string type;
        public string text;
        public OpenAIImageUrlData image_url;
    }

    [Serializable]
    public class OpenAIImageUrlData
    {
        public string url;
    }

    [Serializable]
    public class OpenAIChatResponseData
    {
        public List<OpenAIChoiceData> choices = new List<OpenAIChoiceData>();
        public OpenAIErrorData error;
    }

    [Serializable]
    public class OpenAIChoiceData
    {
        public OpenAIMessageTextData message = new OpenAIMessageTextData();
    }

    [Serializable]
    public class OpenAIMessageTextData
    {
        public string content;
    }

    [Serializable]
    public class OpenAIErrorData
    {
        public string message;
    }
}
