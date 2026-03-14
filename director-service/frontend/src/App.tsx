import { useState, useEffect, useCallback } from 'react';
import type { SceneListItem, SceneSummary, GenerateResponse } from './types';
import { fetchScenes, fetchScene, generatePlan } from './lib/api';
import ScenePanel from './panels/ScenePanel';
import AbstractionPanel from './panels/AbstractionPanel';
import IntentPanel from './panels/IntentPanel';
import DirectingPlanPanel from './panels/DirectingPlanPanel';
import TrajectoryPanel from './panels/TrajectoryPanel';
import OutputPanel from './panels/OutputPanel';

export default function App() {
  const [scenes, setScenes] = useState<SceneListItem[]>([]);
  const [selectedSceneId, setSelectedSceneId] = useState<string>('');
  const [scene, setScene] = useState<SceneSummary | null>(null);
  const [result, setResult] = useState<GenerateResponse | null>(null);
  const [resultHistory, setResultHistory] = useState<GenerateResponse[]>([]);
  const [intentHistory, setIntentHistory] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedShotId, setSelectedShotId] = useState<string | null>(null);

  useEffect(() => {
    fetchScenes()
      .then(setScenes)
      .catch(err => setError(err.message));
  }, []);

  const handleSceneSelect = useCallback(async (sceneId: string) => {
    setSelectedSceneId(sceneId);
    setResult(null);
    setResultHistory([]);
    setSelectedShotId(null);
    setError(null);
    try {
      const data = await fetchScene(sceneId);
      setScene(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const handleGenerate = useCallback(async (intent: string) => {
    if (!selectedSceneId) return;
    setLoading(true);
    setError(null);
    setSelectedShotId(null);
    try {
      const data = await generatePlan(selectedSceneId, intent);
      setResult(data);
      setResultHistory(prev => [...prev, data]);
      setIntentHistory(prev =>
        prev.includes(intent) ? prev : [...prev, intent]
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [selectedSceneId]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Director</h1>
        <select
          value={selectedSceneId}
          onChange={e => handleSceneSelect(e.target.value)}
        >
          <option value="">Select a scene...</option>
          {scenes.map(s => (
            <option key={s.scene_id} value={s.scene_id}>
              {s.scene_name} ({s.scene_type})
            </option>
          ))}
        </select>
        {error && <span className="error-msg">{error}</span>}
      </header>

      <main className="panels-grid">
        <ScenePanel scene={scene} />
        <AbstractionPanel result={result} />
        <IntentPanel
          onGenerate={handleGenerate}
          loading={loading}
          sceneLoaded={!!scene}
          history={intentHistory}
        />
        <DirectingPlanPanel
          plan={result?.directing_plan ?? null}
          selectedShotId={selectedShotId}
          onSelectShot={setSelectedShotId}
        />
        <TrajectoryPanel
          scene={scene}
          trajectory={result?.trajectory_plan ?? null}
          selectedShotId={selectedShotId}
        />
        <OutputPanel result={result} history={resultHistory} />
      </main>
    </div>
  );
}
