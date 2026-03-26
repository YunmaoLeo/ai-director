import type { GenerateResponse, TemporalGenerateResponse } from '../types';
import type { AppMode } from '../App';

interface Props {
  result: GenerateResponse | null;
  mode?: AppMode;
  temporalResult?: TemporalGenerateResponse | null;
}

export default function AbstractionPanel({ result, mode = 'static', temporalResult }: Props) {
  if (mode === 'temporal') {
    const plan = temporalResult?.temporal_directing_plan;
    const timeline = temporalResult?.scene_timeline;
    if (!plan || !timeline) {
      return <div className="panel"><h3>Cinematic Abstraction</h3><p className="muted">Generate a temporal plan to see abstraction data</p></div>;
    }

    const subjects = [...new Set(plan.shots.map(s => s.subject))];
    const shotTypes = [...new Set(plan.shots.map(s => s.shot_type))];
    const movements = [...new Set(plan.shots.map(s => s.movement))];
    const semanticEvents = timeline.semantic_events ?? [];
    const rawEvents = timeline.raw_events ?? timeline.events ?? [];

    return (
      <div className="panel">
        <h3>Cinematic Abstraction</h3>
        <p className="muted">Temporal abstraction derived from tracks + event interpretation</p>

        <h4>Temporal Summary</h4>
        <p>{plan.summary}</p>
        <div className="meta">
          <span>Duration: {plan.time_span?.duration?.toFixed(1) ?? '-'}s</span>
          <span>Tracks: {timeline.object_tracks.length}</span>
          <span>Events: raw {rawEvents.length} / semantic {semanticEvents.length}</span>
          {temporalResult?.director_policy && <span>Policy: {temporalResult.director_policy}</span>}
        </div>

        <h4>Subjects Referenced</h4>
        <div className="tag-list">
          {subjects.map(subject => (
            <span key={subject} className="tag">{subject}</span>
          ))}
        </div>

        <h4>Shot Types Used</h4>
        <div className="tag-list">
          {shotTypes.map(type => (
            <span key={type} className="tag tag-blue">{type}</span>
          ))}
        </div>

        <h4>Movements Used</h4>
        <div className="tag-list">
          {movements.map(mov => (
            <span key={mov} className="tag tag-green">{mov}</span>
          ))}
        </div>
      </div>
    );
  }

  if (!result) {
    return <div className="panel"><h3>Cinematic Abstraction</h3><p className="muted">Generate a plan to see abstraction data</p></div>;
  }

  const plan = result.directing_plan;

  return (
    <div className="panel">
      <h3>Cinematic Abstraction</h3>
      <p className="muted">Derived from scene analysis and directing plan</p>

      <h4>Plan Summary</h4>
      <p>{plan.summary}</p>

      <h4>Subjects Referenced</h4>
      <div className="tag-list">
        {[...new Set(plan.shots.map(s => s.subject))].map(subject => (
          <span key={subject} className="tag">{subject}</span>
        ))}
      </div>

      <h4>Shot Types Used</h4>
      <div className="tag-list">
        {[...new Set(plan.shots.map(s => s.shot_type))].map(type => (
          <span key={type} className="tag tag-blue">{type}</span>
        ))}
      </div>

      <h4>Movements Used</h4>
      <div className="tag-list">
        {[...new Set(plan.shots.map(s => s.movement))].map(mov => (
          <span key={mov} className="tag tag-green">{mov}</span>
        ))}
      </div>
    </div>
  );
}
