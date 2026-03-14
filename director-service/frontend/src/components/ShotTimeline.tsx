import type { Shot } from '../types';

const SHOT_COLORS = [
  '#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4',
];

interface Props {
  shots: Shot[];
  totalDuration: number;
  selectedShotId: string | null;
  onSelectShot: (shotId: string | null) => void;
}

export default function ShotTimeline({ shots, totalDuration, selectedShotId, onSelectShot }: Props) {
  return (
    <div style={{ display: 'flex', gap: 2, height: 32, marginTop: 8 }}>
      {shots.map((shot, idx) => {
        const widthPct = (shot.duration / totalDuration) * 100;
        const isSelected = selectedShotId === shot.shot_id;
        return (
          <div
            key={shot.shot_id}
            onClick={() => onSelectShot(isSelected ? null : shot.shot_id)}
            style={{
              width: `${widthPct}%`,
              backgroundColor: SHOT_COLORS[idx % SHOT_COLORS.length],
              opacity: selectedShotId && !isSelected ? 0.4 : 1,
              borderRadius: 4,
              cursor: 'pointer',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: 10,
              color: '#fff',
              fontFamily: 'monospace',
              border: isSelected ? '2px solid #fff' : '2px solid transparent',
              transition: 'opacity 0.2s',
            }}
            title={`${shot.shot_id}: ${shot.goal} (${shot.duration}s)`}
          >
            {shot.duration}s
          </div>
        );
      })}
    </div>
  );
}
