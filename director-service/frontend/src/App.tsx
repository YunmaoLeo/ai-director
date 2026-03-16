import { useState, useEffect, useCallback, useRef } from 'react';
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
  const [columnWidths, setColumnWidths] = useState<[number, number, number]>([33, 33, 34]);
  const [rowSplits, setRowSplits] = useState<[number, number, number]>([54, 46, 30]);
  const workspaceRef = useRef<HTMLElement | null>(null);
  const columnRefs = useRef<Array<HTMLDivElement | null>>([]);

  const loadScenes = useCallback(async () => {
    try {
      const nextScenes = await fetchScenes();
      setScenes(nextScenes);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    loadScenes();
  }, [loadScenes]);

  useEffect(() => {
    if (!result?.debug_scene_id) return;
    loadScenes();
  }, [result?.debug_scene_id, loadScenes]);

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

  const handleGenerate = useCallback(async (intent: string, llmModel: string) => {
    if (!selectedSceneId) return;
    setLoading(true);
    setError(null);
    setSelectedShotId(null);
    try {
      const data = await generatePlan(selectedSceneId, intent, llmModel);
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

  const handleLoadSavedRun = useCallback(async (savedRun: GenerateResponse) => {
    setResult(savedRun);
    setResultHistory(prev => [...prev, savedRun]);
    setSelectedShotId(null);
    setError(null);
    const runSceneId = savedRun.directing_plan.scene_id;
    if (!runSceneId) {
      return;
    }
    setSelectedSceneId(runSceneId);
    try {
      const sceneData = await fetchScene(runSceneId);
      setScene(sceneData);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  const beginColumnResize = useCallback((index: 0 | 1, startClientX: number) => {
    const startWidths = [...columnWidths] as [number, number, number];
    const workspace = workspaceRef.current;
    if (!workspace) return;
    const totalWidth = workspace.getBoundingClientRect().width;
    const minPct = 18;

    const onMove = (event: MouseEvent) => {
      const deltaPct = ((event.clientX - startClientX) / totalWidth) * 100;
      const next = [...startWidths] as [number, number, number];
      next[index] = Math.max(minPct, startWidths[index] + deltaPct);
      next[index + 1] = Math.max(minPct, startWidths[index + 1] - deltaPct);
      const overflow = next[index] + next[index + 1] - (startWidths[index] + startWidths[index + 1]);
      if (overflow > 0) {
        next[index + 1] = Math.max(minPct, next[index + 1] - overflow);
      }
      const sum = next[0] + next[1] + next[2];
      const normalized: [number, number, number] = [
        (next[0] / sum) * 100,
        (next[1] / sum) * 100,
        (next[2] / sum) * 100,
      ];
      setColumnWidths(normalized);
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [columnWidths]);

  const beginRowResize = useCallback((columnIndex: 0 | 1 | 2, startClientY: number) => {
    const startSplit = rowSplits[columnIndex];
    const column = columnRefs.current[columnIndex];
    if (!column) return;
    const totalHeight = column.getBoundingClientRect().height;
    const minPct = (160 / Math.max(totalHeight, 1)) * 100;

    const onMove = (event: MouseEvent) => {
      const deltaPct = ((event.clientY - startClientY) / totalHeight) * 100;
      const nextValue = Math.max(minPct, Math.min(100 - minPct, startSplit + deltaPct));
      setRowSplits(prev => {
        const next = [...prev] as [number, number, number];
        next[columnIndex] = nextValue;
        return next;
      });
    };

    const onUp = () => {
      window.removeEventListener('mousemove', onMove);
      window.removeEventListener('mouseup', onUp);
    };

    window.addEventListener('mousemove', onMove);
    window.addEventListener('mouseup', onUp);
  }, [rowSplits]);

  return (
    <div className="app">
      <header className="app-header">
        <h1>AI Director</h1>
        <button type="button" onClick={() => loadScenes()}>
          Refresh Scenes
        </button>
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

      <main className="workspace" ref={workspaceRef}>
        <div
          className="panel-column"
          ref={node => { columnRefs.current[0] = node; }}
          style={{ width: `${columnWidths[0]}%` }}
        >
          <div className="stack-pane" style={{ height: `${rowSplits[0]}%` }}>
            <ScenePanel scene={scene} />
          </div>
          <div className="stack-splitter" onMouseDown={e => beginRowResize(0, e.clientY)} />
          <div className="stack-pane" style={{ height: `${100 - rowSplits[0]}%` }}>
            <AbstractionPanel result={result} />
          </div>
        </div>

        <div className="workspace-splitter" onMouseDown={e => beginColumnResize(0, e.clientX)} />

        <div
          className="panel-column"
          ref={node => { columnRefs.current[1] = node; }}
          style={{ width: `${columnWidths[1]}%` }}
        >
          <div className="stack-pane" style={{ height: '100%' }}>
            <TrajectoryPanel
              scene={scene}
              trajectory={result?.trajectory_plan ?? null}
              selectedShotId={selectedShotId}
            />
          </div>
        </div>

        <div className="workspace-splitter" onMouseDown={e => beginColumnResize(1, e.clientX)} />

        <div
          className="panel-column"
          ref={node => { columnRefs.current[2] = node; }}
          style={{ width: `${columnWidths[2]}%` }}
        >
          <div className="stack-pane" style={{ height: `${rowSplits[2]}%` }}>
            <IntentPanel
              onGenerate={handleGenerate}
              loading={loading}
              sceneLoaded={!!scene}
              history={intentHistory}
            />
          </div>
          <div className="stack-splitter" onMouseDown={e => beginRowResize(2, e.clientY)} />
          <div className="stack-pane" style={{ height: `${100 - rowSplits[2]}%` }}>
            <div className="substack">
              <div className="sub-pane" style={{ height: '54%' }}>
                <DirectingPlanPanel
                  plan={result?.directing_plan ?? null}
                  selectedShotId={selectedShotId}
                  onSelectShot={setSelectedShotId}
                />
              </div>
              <div className="stack-splitter stack-splitter-thin" />
              <div className="sub-pane" style={{ height: '46%' }}>
                <OutputPanel result={result} history={resultHistory} onLoadSavedRun={handleLoadSavedRun} />
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
