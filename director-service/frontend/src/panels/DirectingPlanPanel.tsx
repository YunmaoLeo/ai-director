import type { DirectingPlan } from '../types';
import ShotTimeline from '../components/ShotTimeline';

const SHOT_COLORS = [
  '#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4',
];

interface Props {
  plan: DirectingPlan | null;
  selectedShotId: string | null;
  onSelectShot: (shotId: string | null) => void;
}

export default function DirectingPlanPanel({ plan, selectedShotId, onSelectShot }: Props) {
  if (!plan) {
    return <div className="panel"><h3>Directing Plan</h3><p className="muted">No plan generated</p></div>;
  }

  return (
    <div className="panel">
      <h3>Directing Plan</h3>
      <div className="meta">
        <span>Shots: {plan.shots.length}</span>
        <span>Duration: {plan.total_duration}s</span>
        <span>Intent: {plan.intent}</span>
      </div>

      <ShotTimeline
        shots={plan.shots}
        totalDuration={plan.total_duration}
        selectedShotId={selectedShotId}
        onSelectShot={onSelectShot}
      />

      <div className="shot-cards">
        {plan.shots.map((shot, idx) => {
          const isSelected = selectedShotId === shot.shot_id;
          return (
            <div
              key={shot.shot_id}
              className={`shot-card ${isSelected ? 'selected' : ''}`}
              onClick={() => onSelectShot(isSelected ? null : shot.shot_id)}
              style={{ borderLeftColor: SHOT_COLORS[idx % SHOT_COLORS.length] }}
            >
              <div className="shot-card-header">
                <strong>{shot.shot_id}</strong>
                <div className="shot-badges">
                  <span className="badge">{shot.shot_type}</span>
                  <span className="badge badge-outline">{shot.movement}</span>
                  <span className="badge badge-dim">{shot.pacing}</span>
                </div>
              </div>
              <p className="shot-goal">{shot.goal}</p>
              <div className="shot-meta">
                <span>Subject: <code>{shot.subject}</code></span>
                <span>Duration: {shot.duration}s</span>
              </div>
              {shot.rationale && <p className="shot-rationale">{shot.rationale}</p>}
            </div>
          );
        })}
      </div>
    </div>
  );
}
