import { useEffect, useState } from 'react';
import { fetchLlmModels } from '../lib/api';

interface Props {
  onGenerate: (intent: string, llmModel: string) => void;
  loading: boolean;
  sceneLoaded: boolean;
  history: string[];
}

const EXAMPLE_INTENTS = [
  'Give me an overview of this room',
  'Reveal the window after focusing on the desk',
  'Create a slow cinematic exploration of the room',
  'Focus on the main subject in detail',
];

const FALLBACK_MODELS = [
  'gpt-5.2-chat-latest',
  'gpt-5.2',
  'gpt-5.1-chat-latest',
  'gpt-5.1',
  'gpt-5-chat-latest',
  'gpt-5',
  'gpt-4.1',
  'gpt-4.1-mini',
  'gpt-4o',
  'gpt-4o-mini',
];

export default function IntentPanel({ onGenerate, loading, sceneLoaded, history }: Props) {
  const [intent, setIntent] = useState('');
  const [llmModel, setLlmModel] = useState('gpt-5.2-chat-latest');
  const [modelOptions, setModelOptions] = useState<string[]>(FALLBACK_MODELS);

  useEffect(() => {
    fetchLlmModels()
      .then(data => {
        const merged = Array.from(new Set([...data.recommended_models, ...FALLBACK_MODELS]));
        setModelOptions(merged);
        if (!llmModel.trim() || llmModel === 'gpt-5.2-chat-latest') {
          setLlmModel(data.default_model || merged[0] || 'gpt-5.2-chat-latest');
        }
      })
      .catch(() => {
        // Keep fallback list; no-op.
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSubmit = () => {
    if (intent.trim() && sceneLoaded) {
      onGenerate(intent.trim(), llmModel.trim() || 'gpt-5.2-chat-latest');
    }
  };

  return (
    <div className="panel">
      <h3>Intent</h3>
      <textarea
        value={intent}
        onChange={e => setIntent(e.target.value)}
        placeholder="Enter your directing intent..."
        rows={3}
        disabled={!sceneLoaded}
        onKeyDown={e => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleSubmit();
          }
        }}
      />
      <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
        <select
          value={llmModel}
          onChange={e => setLlmModel(e.target.value)}
          style={{
            flex: 1,
            minWidth: 180,
            background: 'var(--bg)',
            color: 'var(--text)',
            border: '1px solid var(--border)',
            borderRadius: 6,
            padding: '6px 10px',
            fontSize: 13,
          }}
        >
          {modelOptions.map(model => (
            <option key={model} value={model}>
              {model}
            </option>
          ))}
        </select>
        <button onClick={handleSubmit} disabled={loading || !sceneLoaded || !intent.trim()}>
          {loading ? 'Generating...' : 'Generate Plan'}
        </button>
      </div>

      <h4>Quick Examples</h4>
      <div className="tag-list">
        {EXAMPLE_INTENTS.map(ex => (
          <button
            key={ex}
            className="tag-button"
            onClick={() => setIntent(ex)}
            disabled={!sceneLoaded}
          >
            {ex}
          </button>
        ))}
      </div>

      {history.length > 0 && (
        <>
          <h4>History</h4>
          <ul className="history-list">
            {history.map((h, i) => (
              <li key={i} onClick={() => setIntent(h)} style={{ cursor: 'pointer' }}>
                {h}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
