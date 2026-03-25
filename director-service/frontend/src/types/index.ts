export interface SceneListItem {
  filename: string;
  scene_id: string;
  scene_name: string;
  scene_type: string;
}

export interface Bounds {
  width: number;
  length: number;
  height: number;
}

export interface SceneObject {
  id: string;
  name: string;
  category: string;
  position: [number, number, number];
  size: [number, number, number];
  forward: [number, number, number] | null;
  importance: number;
  tags: string[];
}

export interface SpatialRelation {
  type: string;
  source: string;
  target: string;
}

export interface SceneSummary {
  scene_id: string;
  scene_name: string;
  scene_type: string;
  description: string;
  bounds: Bounds;
  objects: SceneObject[];
  relations: SpatialRelation[];
}

export interface ShotConstraints {
  keep_objects_visible: string[];
  avoid_high_angle: boolean;
  avoid_occlusion: boolean;
  preserve_context: boolean;
  end_on_subject: boolean;
  maintain_room_readability: boolean;
}

export interface Shot {
  shot_id: string;
  goal: string;
  subject: string;
  shot_type: string;
  movement: string;
  duration: number;
  pacing: string;
  constraints: ShotConstraints;
  rationale: string;
}

export interface DirectingPlan {
  plan_id: string;
  scene_id: string;
  intent: string;
  summary: string;
  total_duration: number;
  shots: Shot[];
}

export interface TrajectoryMetrics {
  visibility_score: number;
  smoothness_score: number;
  framing_score: number;
  occlusion_risk: number;
  clearance_score: number;
}

export interface ShotTrajectory {
  shot_id: string;
  start_position: [number, number, number];
  end_position: [number, number, number];
  look_at_position: [number, number, number];
  fov: number;
  path_type: string;
  sampled_points: [number, number, number][];
  duration: number;
  metrics: TrajectoryMetrics;
}

export interface TrajectoryPlan {
  plan_id: string;
  scene_id: string;
  total_duration: number;
  trajectories: ShotTrajectory[];
}

export interface ValidationIssue {
  level: string;
  category: string;
  message: string;
  field: string;
}

export interface ValidationReport {
  is_valid: boolean;
  errors: ValidationIssue[];
  warnings: ValidationIssue[];
}

export interface GenerateResponse {
  directing_plan: DirectingPlan;
  trajectory_plan: TrajectoryPlan;
  validation_report: ValidationReport;
  debug_scene_id?: string | null;
  debug_scene_file?: string | null;
  output_prefix?: string | null;
  llm_provider?: string | null;
  llm_model?: string | null;
  llm_model_requested?: string | null;
  source_api?: string | null;
  saved_at?: string | null;
}

export interface RunSummary {
  prefix: string;
  created_at: string;
  scene_id: string;
  intent: string;
  llm_provider?: string;
  llm_model?: string;
  source_api?: string;
  debug_scene_id?: string;
  debug_scene_file?: string;
}

export interface LlmModelsResponse {
  llm_provider: string;
  default_model: string;
  recommended_models: string[];
  aliases: Record<string, string>;
}

// --- Temporal types ---

export interface TimeSpan {
  start: number;
  end: number;
  duration: number;
}

export interface ObjectTrackSample {
  timestamp: number;
  position: [number, number, number];
  rotation: [number, number, number];
  velocity: [number, number, number];
  visible: boolean;
}

export interface ObjectTrack {
  object_id: string;
  samples: ObjectTrackSample[];
  motion: {
    average_speed: number;
    max_speed: number;
    direction_trend: [number, number, number];
    acceleration_bucket: string;
    total_displacement: number;
  };
  keyframe_indices: number[];
}

export interface SceneEvent {
  event_id: string;
  event_type: string;
  timestamp: number;
  duration: number;
  object_ids: string[];
  description: string;
}

export interface SceneTimeline {
  scene_id: string;
  scene_name: string;
  scene_type: string;
  description: string;
  bounds: Bounds;
  time_span: TimeSpan;
  objects_static: SceneObject[];
  object_tracks: ObjectTrack[];
  events: SceneEvent[];
  camera_candidates: unknown[];
  relations: SpatialRelation[];
}

export interface Beat {
  beat_id: string;
  time_start: number;
  time_end: number;
  goal: string;
  mood: string;
  subjects: string[];
}

export interface TemporalShot {
  shot_id: string;
  time_start: number;
  time_end: number;
  goal: string;
  subject: string;
  shot_type: string;
  movement: string;
  pacing: string;
  constraints: Record<string, unknown>;
  rationale: string;
  transition_in: string;
  beat_id: string;
}

export interface TemporalDirectingPlan {
  plan_id: string;
  scene_id: string;
  intent: string;
  summary: string;
  time_span: TimeSpan | null;
  beats: Beat[];
  shots: TemporalShot[];
}

export interface TimedTrajectoryPoint {
  timestamp: number;
  position: [number, number, number];
  look_at: [number, number, number];
  fov: number;
}

export interface TemporalShotTrajectory {
  shot_id: string;
  time_start: number;
  time_end: number;
  path_type: string;
  timed_points: TimedTrajectoryPoint[];
  metrics: TrajectoryMetrics;
}

export interface TemporalTrajectoryPlan {
  plan_id: string;
  scene_id: string;
  time_span: TimeSpan | null;
  trajectories: TemporalShotTrajectory[];
}

export interface PlanningPassArtifact {
  pass_type: string;
  pass_index: number;
  model_provider: string;
  model_id: string;
  input_summary: string;
  output_raw: string;
  output_parsed: Record<string, unknown>;
  duration_ms: number;
  success: boolean;
  error_message: string;
}

export interface TemporalGenerateResponse {
  temporal_directing_plan: TemporalDirectingPlan;
  temporal_trajectory_plan: TemporalTrajectoryPlan;
  validation_report: ValidationReport;
  pass_artifacts: PlanningPassArtifact[];
  scene_timeline?: SceneTimeline;
  output_prefix?: string | null;
  scene_id?: string | null;
  intent?: string | null;
  llm_provider?: string | null;
  llm_model?: string | null;
  cinematic_style_requested?: string | null;
  cinematic_style?: string | null;
  style_rationale?: string | null;
  style_notes?: string | null;
  saved_at?: string | null;
  temporal: boolean;
}
