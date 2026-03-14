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
}
