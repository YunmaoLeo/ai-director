import type { SceneSummary, TrajectoryPlan } from '../types';
import TopDownCanvas from '../components/TopDownCanvas';

interface Props {
  scene: SceneSummary | null;
  trajectory: TrajectoryPlan | null;
  selectedShotId: string | null;
}

export default function TrajectoryPanel({ scene, trajectory, selectedShotId }: Props) {
  if (!scene || !trajectory) {
    return <div className="panel"><h3>Trajectory Preview</h3><p className="muted">No trajectory data</p></div>;
  }

  const selectedTraj = selectedShotId
    ? trajectory.trajectories.find(t => t.shot_id === selectedShotId)
    : null;

  return (
    <div className="panel">
      <h3>Trajectory Preview</h3>
      <TopDownCanvas
        scene={scene}
        trajectories={trajectory.trajectories}
        selectedShotId={selectedShotId}
        width={560}
        height={440}
      />

      {selectedTraj && (
        <div className="metrics-grid">
          <h4>Metrics: {selectedTraj.shot_id}</h4>
          <div className="metric-row">
            <span>Path Type:</span><span>{selectedTraj.path_type}</span>
          </div>
          <div className="metric-row">
            <span>FOV:</span><span>{selectedTraj.fov}</span>
          </div>
          <div className="metric-row">
            <span>Points:</span><span>{selectedTraj.sampled_points.length}</span>
          </div>
          <div className="metric-row">
            <span>Visibility:</span>
            <MetricBar value={selectedTraj.metrics.visibility_score} />
          </div>
          <div className="metric-row">
            <span>Smoothness:</span>
            <MetricBar value={selectedTraj.metrics.smoothness_score} />
          </div>
          <div className="metric-row">
            <span>Framing:</span>
            <MetricBar value={selectedTraj.metrics.framing_score} />
          </div>
          <div className="metric-row">
            <span>Clearance:</span>
            <MetricBar value={selectedTraj.metrics.clearance_score} />
          </div>
          <div className="metric-row">
            <span>Occlusion Risk:</span>
            <MetricBar value={selectedTraj.metrics.occlusion_risk} color="#c62828" />
          </div>
        </div>
      )}
    </div>
  );
}

function MetricBar({ value, color = '#4CAF50' }: { value: number; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      <div style={{
        width: 100, height: 8, background: '#333', borderRadius: 4, overflow: 'hidden',
      }}>
        <div style={{
          width: `${value * 100}%`, height: '100%', background: color, borderRadius: 4,
        }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'monospace' }}>{(value * 100).toFixed(0)}%</span>
    </div>
  );
}
