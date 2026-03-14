import type { GenerateResponse } from '../types';

interface Props {
  result: GenerateResponse | null;
}

export default function AbstractionPanel({ result }: Props) {
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
