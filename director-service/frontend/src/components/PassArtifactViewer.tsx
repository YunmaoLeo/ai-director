import { useState } from 'react';
import type { PlanningPassArtifact } from '../types';
import JsonViewer from './JsonViewer';

interface Props {
  artifacts: PlanningPassArtifact[];
}

const PASS_LABELS: Record<string, string> = {
  global_beat: 'Pass 1: Beat Planning',
  shot_intent: 'Pass 2: Shot Intent',
  constraint_critique: 'Pass 3: Critique',
  deterministic_solve: 'Deterministic Solve',
  validation: 'Validation',
};

export default function PassArtifactViewer({ artifacts }: Props) {
  const [selectedIndex, setSelectedIndex] = useState(0);

  if (!artifacts || artifacts.length === 0) {
    return <p className="muted">No pass artifacts available.</p>;
  }

  const selected = artifacts[Math.min(selectedIndex, artifacts.length - 1)];

  return (
    <div>
      <div className="tag-list" style={{ marginBottom: 8 }}>
        {artifacts.map((a, i) => (
          <button
            key={i}
            className={`tag-button ${selectedIndex === i ? 'active' : ''}`}
            onClick={() => setSelectedIndex(i)}
            style={{
              borderColor: a.success ? undefined : '#c62828',
              color: a.success ? undefined : '#ef9a9a',
            }}
          >
            {PASS_LABELS[a.pass_type] ?? a.pass_type}
            {!a.success && ' (failed)'}
          </button>
        ))}
      </div>

      <div style={{ fontSize: 12, marginBottom: 8 }}>
        <div className="metric-row">
          <span>Pass Type:</span>
          <span>{selected.pass_type}</span>
        </div>
        <div className="metric-row">
          <span>Duration:</span>
          <span>{selected.duration_ms.toFixed(0)}ms</span>
        </div>
        <div className="metric-row">
          <span>Success:</span>
          <span style={{ color: selected.success ? '#4CAF50' : '#c62828' }}>
            {selected.success ? 'Yes' : 'No'}
          </span>
        </div>
        {selected.model_provider && (
          <div className="metric-row">
            <span>Provider:</span>
            <span>{selected.model_provider}</span>
          </div>
        )}
        {selected.model_id && (
          <div className="metric-row">
            <span>Model:</span>
            <span>{selected.model_id}</span>
          </div>
        )}
        {selected.input_summary && (
          <div className="metric-row">
            <span>Input:</span>
            <span>{selected.input_summary}</span>
          </div>
        )}
        {selected.error_message && (
          <div className="metric-row">
            <span>Error:</span>
            <span style={{ color: '#ef9a9a' }}>{selected.error_message}</span>
          </div>
        )}
      </div>

      <details style={{ marginTop: 4 }}>
        <summary style={{ cursor: 'pointer', fontSize: 12, color: '#aaa' }}>
          Parsed Output
        </summary>
        <JsonViewer data={selected.output_parsed} />
      </details>

      {selected.output_raw && (
        <details style={{ marginTop: 4 }}>
          <summary style={{ cursor: 'pointer', fontSize: 12, color: '#aaa' }}>
            Raw Output ({selected.output_raw.length} chars)
          </summary>
          <pre style={{ fontSize: 10, maxHeight: 200, overflow: 'auto', whiteSpace: 'pre-wrap' }}>
            {selected.output_raw}
          </pre>
        </details>
      )}
    </div>
  );
}
