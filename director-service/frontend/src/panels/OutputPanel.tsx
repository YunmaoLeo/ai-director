import { useEffect, useState } from 'react';
import type { GenerateResponse, RunSummary, TemporalGenerateResponse } from '../types';
import JsonViewer from '../components/JsonViewer';
import ValidationBadge from '../components/ValidationBadge';
import PassArtifactViewer from '../components/PassArtifactViewer';
import { fetchRun, fetchRuns, fetchTemporalRun, fetchTemporalRuns } from '../lib/api';
import type { AppMode } from '../App';

interface Props {
  result: GenerateResponse | null;
  history: GenerateResponse[];
  onLoadSavedRun: (run: GenerateResponse) => void;
  onLoadTemporalRun?: (run: TemporalGenerateResponse) => void;
  mode?: AppMode;
  temporalResult?: TemporalGenerateResponse | null;
}

type Tab = 'directing_plan' | 'trajectory_plan' | 'validation' | 'pass_artifacts';

export default function OutputPanel({ result, history, onLoadSavedRun, onLoadTemporalRun, mode = 'static', temporalResult }: Props) {
  const [tab, setTab] = useState<Tab>('directing_plan');
  const [historyIdx, setHistoryIdx] = useState<number | null>(null);
  const [savedRuns, setSavedRuns] = useState<RunSummary[]>([]);
  const [loadingRunPrefix, setLoadingRunPrefix] = useState<string | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);

  const displayResult = historyIdx !== null ? history[historyIdx] : result;
  const activeValidation = mode === 'temporal' ? temporalResult?.validation_report : displayResult?.validation_report;

  useEffect(() => {
    const loader = mode === 'temporal' ? fetchTemporalRuns : fetchRuns;
    loader()
      .then(setSavedRuns)
      .catch(err => setRunsError(err instanceof Error ? err.message : String(err)));
  }, [mode, result?.output_prefix, temporalResult?.output_prefix]);

  return (
    <div className="panel">
      <h3>
        Output
        {activeValidation && <ValidationBadge report={activeValidation} />}
      </h3>
      {mode === 'temporal' && !temporalResult && <p className="muted">No temporal output loaded. Select a saved run below or generate a new one.</p>}
      {mode === 'static' && !displayResult && <p className="muted">No output loaded. Select a saved run below or generate a new one.</p>}
      {mode === 'static' && displayResult && (displayResult.debug_scene_id || displayResult.output_prefix) && (
        <div className="meta" style={{ marginBottom: 12 }}>
          {displayResult.debug_scene_id && <span>Debug Scene: <code>{displayResult.debug_scene_id}</code></span>}
          {displayResult.debug_scene_file && <span>Scene File: <code>{displayResult.debug_scene_file}</code></span>}
          {displayResult.output_prefix && <span>Output Prefix: <code>{displayResult.output_prefix}</code></span>}
          {displayResult.llm_provider && <span>Provider: <code>{displayResult.llm_provider}</code></span>}
          {displayResult.llm_model_requested && <span>Model Requested: <code>{displayResult.llm_model_requested}</code></span>}
          {displayResult.llm_model && <span>Model: <code>{displayResult.llm_model}</code></span>}
          {displayResult.source_api && <span>API: <code>{displayResult.source_api}</code></span>}
        </div>
      )}
      {mode === 'temporal' && temporalResult?.output_prefix && (
        <div className="meta" style={{ marginBottom: 12 }}>
          {temporalResult.output_prefix && <span>Output Prefix: <code>{temporalResult.output_prefix}</code></span>}
          {temporalResult.llm_provider && <span>Provider: <code>{temporalResult.llm_provider}</code></span>}
          {temporalResult.llm_model && <span>Model: <code>{temporalResult.llm_model}</code></span>}
          {temporalResult.director_policy && <span>Director Policy: <code>{temporalResult.director_policy}</code></span>}
        </div>
      )}

      {((mode === 'static' && displayResult) || (mode === 'temporal' && temporalResult)) && (
        <>
          <div className="tab-bar">
            <button className={tab === 'directing_plan' ? 'active' : ''} onClick={() => setTab('directing_plan')}>
              {mode === 'temporal' ? 'Temporal Plan' : 'Directing Plan'}
            </button>
            <button className={tab === 'trajectory_plan' ? 'active' : ''} onClick={() => setTab('trajectory_plan')}>
              {mode === 'temporal' ? 'Temporal Trajectory' : 'Trajectory Plan'}
            </button>
            <button className={tab === 'validation' ? 'active' : ''} onClick={() => setTab('validation')}>
              Validation
            </button>
            {mode === 'temporal' && temporalResult?.pass_artifacts && (
              <button className={tab === 'pass_artifacts' ? 'active' : ''} onClick={() => setTab('pass_artifacts')}>
                Pass Artifacts
              </button>
            )}
          </div>

          {tab === 'directing_plan' && (
            mode === 'temporal' && temporalResult
              ? <JsonViewer data={temporalResult.temporal_directing_plan} />
              : <JsonViewer data={displayResult!.directing_plan} />
          )}
          {tab === 'trajectory_plan' && (
            mode === 'temporal' && temporalResult
              ? <JsonViewer data={temporalResult.temporal_trajectory_plan} />
              : <JsonViewer data={displayResult!.trajectory_plan} />
          )}
          {tab === 'validation' && (
            <div>
              {(() => {
                const report = mode === 'temporal' && temporalResult
                  ? temporalResult.validation_report
                  : displayResult!.validation_report;
                return (
                  <>
                    {report.errors.length > 0 && (
                      <div className="validation-section">
                        <h4>Errors</h4>
                        {report.errors.map((e, i) => (
                          <div key={i} className="validation-issue error">
                            <strong>[{e.category}]</strong> {e.message}
                            {e.field && <code> ({e.field})</code>}
                          </div>
                        ))}
                      </div>
                    )}
                    {report.warnings.length > 0 && (
                      <div className="validation-section">
                        <h4>Warnings</h4>
                        {report.warnings.map((w, i) => (
                          <div key={i} className="validation-issue warning">
                            <strong>[{w.category}]</strong> {w.message}
                            {w.field && <code> ({w.field})</code>}
                          </div>
                        ))}
                      </div>
                    )}
                    {report.errors.length === 0 && report.warnings.length === 0 && (
                      <p className="muted">No validation issues found.</p>
                    )}
                  </>
                );
              })()}
            </div>
          )}
          {tab === 'pass_artifacts' && mode === 'temporal' && temporalResult?.pass_artifacts && (
            <PassArtifactViewer artifacts={temporalResult.pass_artifacts} />
          )}
        </>
      )}

      {mode === 'static' && displayResult && history.length > 1 && (
        <div style={{ marginTop: 12 }}>
          <h4>Compare Previous ({history.length} results)</h4>
          <div className="tag-list">
            <button
              className={`tag-button ${historyIdx === null ? 'active' : ''}`}
              onClick={() => setHistoryIdx(null)}
            >
              Latest
            </button>
            {history.map((entry, i) => (
              <button
                key={i}
                className={`tag-button ${historyIdx === i ? 'active' : ''}`}
                onClick={() => setHistoryIdx(i)}
                title={`Intent: ${entry.directing_plan.intent}`}
              >
                {`#${i + 1} ${truncateIntent(entry.directing_plan.intent)}`}
              </button>
            ))}
          </div>
        </div>
      )}

      <div style={{ marginTop: 12 }}>
        <h4>Saved Runs ({savedRuns.length})</h4>
        {runsError && <p className="muted" style={{ color: 'var(--red)' }}>{runsError}</p>}
        <div className="tag-list">
          {savedRuns.slice(0, 20).map(run => (
            <button
              key={run.prefix}
              className="tag-button"
              disabled={loadingRunPrefix === run.prefix}
              onClick={async () => {
                try {
                  setLoadingRunPrefix(run.prefix);
                  if (mode === 'temporal') {
                    const bundle = await fetchTemporalRun(run.prefix);
                    onLoadTemporalRun?.(bundle);
                  } else {
                    const bundle = await fetchRun(run.prefix);
                    onLoadSavedRun(bundle);
                  }
                  setHistoryIdx(null);
                  setRunsError(null);
                } catch (err: unknown) {
                  setRunsError(err instanceof Error ? err.message : String(err));
                } finally {
                  setLoadingRunPrefix(null);
                }
              }}
              title={`${run.scene_id} • ${run.intent}`}
            >
              {loadingRunPrefix === run.prefix
                ? 'Loading...'
                : `${run.scene_id} • ${run.llm_model ?? 'model?'} • ${truncateIntent(run.intent)}`}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function truncateIntent(intent: string, maxLen = 42): string {
  if (!intent) return '(no intent)';
  if (intent.length <= maxLen) return intent;
  return `${intent.slice(0, maxLen - 1)}…`;
}
