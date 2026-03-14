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
