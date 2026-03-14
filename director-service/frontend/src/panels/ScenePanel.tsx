import type { SceneSummary } from '../types';
import TopDownCanvas from '../components/TopDownCanvas';

interface Props {
  scene: SceneSummary | null;
}

export default function ScenePanel({ scene }: Props) {
  if (!scene) {
    return <div className="panel"><h3>Scene</h3><p className="muted">No scene loaded</p></div>;
  }

  return (
    <div className="panel">
      <h3>Scene: {scene.scene_name}</h3>
      <p className="muted">{scene.description}</p>
      <div className="meta">
        <span>Type: {scene.scene_type}</span>
        <span>Size: {scene.bounds.width}m x {scene.bounds.length}m x {scene.bounds.height}m</span>
        <span>Objects: {scene.objects.length}</span>
      </div>
      <h4>Objects</h4>
      <table>
        <thead>
          <tr><th>ID</th><th>Name</th><th>Category</th><th>Importance</th><th>Tags</th></tr>
        </thead>
        <tbody>
          {scene.objects.map(obj => (
            <tr key={obj.id}>
              <td><code>{obj.id}</code></td>
              <td>{obj.name}</td>
              <td>{obj.category}</td>
              <td>{obj.importance}</td>
              <td>{obj.tags.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>Top-Down View</h4>
      <TopDownCanvas scene={scene} />
    </div>
  );
}
