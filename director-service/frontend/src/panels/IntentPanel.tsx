import { useState } from 'react';

interface Props {
  onGenerate: (intent: string) => void;
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

export default function IntentPanel({ onGenerate, loading, sceneLoaded, history }: Props) {
  const [intent, setIntent] = useState('');

  const handleSubmit = () => {
    if (intent.trim() && sceneLoaded) {
      onGenerate(intent.trim());
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
