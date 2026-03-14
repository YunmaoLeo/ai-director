import { useState } from 'react';
import type { GenerateResponse } from '../types';
import JsonViewer from '../components/JsonViewer';
import ValidationBadge from '../components/ValidationBadge';

interface Props {
  result: GenerateResponse | null;
  history: GenerateResponse[];
}

type Tab = 'directing_plan' | 'trajectory_plan' | 'validation';

export default function OutputPanel({ result, history }: Props) {
  const [tab, setTab] = useState<Tab>('directing_plan');
  const [historyIdx, setHistoryIdx] = useState<number | null>(null);

  const displayResult = historyIdx !== null ? history[historyIdx] : result;

  if (!displayResult) {
    return <div className="panel"><h3>Output</h3><p className="muted">No output to display</p></div>;
  }

  return (
    <div className="panel">
      <h3>
        Output
        <ValidationBadge report={displayResult.validation_report} />
      </h3>
      {(displayResult.debug_scene_id || displayResult.output_prefix) && (
        <div className="meta" style={{ marginBottom: 12 }}>
          {displayResult.debug_scene_id && <span>Debug Scene: <code>{displayResult.debug_scene_id}</code></span>}
          {displayResult.debug_scene_file && <span>Scene File: <code>{displayResult.debug_scene_file}</code></span>}
          {displayResult.output_prefix && <span>Output Prefix: <code>{displayResult.output_prefix}</code></span>}
        </div>
      )}

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

      {history.length > 1 && (
        <div style={{ marginTop: 12 }}>
          <h4>Compare Previous ({history.length} results)</h4>
          <div className="tag-list">
            <button
              className={`tag-button ${historyIdx === null ? 'active' : ''}`}
              onClick={() => setHistoryIdx(null)}
            >
              Latest
            </button>
            {history.map((_, i) => (
              <button
                key={i}
                className={`tag-button ${historyIdx === i ? 'active' : ''}`}
                onClick={() => setHistoryIdx(i)}
              >
                #{i + 1}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
