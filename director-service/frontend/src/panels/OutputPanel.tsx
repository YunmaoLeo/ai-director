import { useEffect, useState } from 'react';
import type { GenerateResponse, RunSummary } from '../types';
import JsonViewer from '../components/JsonViewer';
import ValidationBadge from '../components/ValidationBadge';
import { fetchRun, fetchRuns } from '../lib/api';

interface Props {
  result: GenerateResponse | null;
  history: GenerateResponse[];
  onLoadSavedRun: (run: GenerateResponse) => void;
}

type Tab = 'directing_plan' | 'trajectory_plan' | 'validation';

export default function OutputPanel({ result, history, onLoadSavedRun }: Props) {
  const [tab, setTab] = useState<Tab>('directing_plan');
  const [historyIdx, setHistoryIdx] = useState<number | null>(null);
  const [savedRuns, setSavedRuns] = useState<RunSummary[]>([]);
  const [loadingRunPrefix, setLoadingRunPrefix] = useState<string | null>(null);
  const [runsError, setRunsError] = useState<string | null>(null);

  const displayResult = historyIdx !== null ? history[historyIdx] : result;

  useEffect(() => {
    fetchRuns()
      .then(setSavedRuns)
      .catch(err => setRunsError(err instanceof Error ? err.message : String(err)));
  }, [result?.output_prefix]);

  return (
    <div className="panel">
      <h3>
        Output
        {displayResult && <ValidationBadge report={displayResult.validation_report} />}
      </h3>
      {!displayResult && <p className="muted">No output loaded. Select a saved run below or generate a new one.</p>}
      {displayResult && (displayResult.debug_scene_id || displayResult.output_prefix) && (
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

      {displayResult && (
        <>
          <div className="tab-bar">
            <button className={tab === 'directing_plan' ? 'active' : ''} onClick={() => setTab('directing_plan')}>
              Directing Plan
            </button>
            <button className={tab === 'trajectory_plan' ? 'active' : ''} onClick={() => setTab('trajectory_plan')}>
              Trajectory Plan
            </button>
            <button className={tab === 'validation' ? 'active' : ''} onClick={() => setTab('validation')}>
              Validation
            </button>
          </div>

          {tab === 'directing_plan' && <JsonViewer data={displayResult.directing_plan} />}
          {tab === 'trajectory_plan' && <JsonViewer data={displayResult.trajectory_plan} />}
          {tab === 'validation' && (
            <div>
              {displayResult.validation_report.errors.length > 0 && (
                <div className="validation-section">
                  <h4>Errors</h4>
                  {displayResult.validation_report.errors.map((e, i) => (
                    <div key={i} className="validation-issue error">
                      <strong>[{e.category}]</strong> {e.message}
                      {e.field && <code> ({e.field})</code>}
                    </div>
                  ))}
                </div>
              )}
              {displayResult.validation_report.warnings.length > 0 && (
                <div className="validation-section">
                  <h4>Warnings</h4>
                  {displayResult.validation_report.warnings.map((w, i) => (
                    <div key={i} className="validation-issue warning">
                      <strong>[{w.category}]</strong> {w.message}
                      {w.field && <code> ({w.field})</code>}
                    </div>
                  ))}
                </div>
              )}
              {displayResult.validation_report.errors.length === 0 &&
               displayResult.validation_report.warnings.length === 0 && (
                <p className="muted">No validation issues found.</p>
              )}
            </div>
          )}
        </>
      )}

      {displayResult && history.length > 1 && (
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
                  const bundle = await fetchRun(run.prefix);
                  onLoadSavedRun(bundle);
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
