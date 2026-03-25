import { useRef, useEffect } from 'react';
import type { Beat, TemporalShot, SceneEvent, TimeSpan } from '../types';

interface Props {
  timeSpan: TimeSpan;
  beats: Beat[];
  shots: TemporalShot[];
  events: SceneEvent[];
  playheadSeconds: number;
  onSeek: (time: number) => void;
  selectedShotId: string | null;
  onSelectShot: (shotId: string | null) => void;
  playbackSpeed: number;
  onSpeedChange: (speed: number) => void;
}

const BEAT_COLORS = ['#2196F3', '#4CAF50', '#FF9800', '#9C27B0', '#F44336'];
const SHOT_COLORS = ['#64B5F6', '#81C784', '#FFB74D', '#CE93D8', '#EF9A9A'];

export default function TemporalTimeline({
  timeSpan,
  beats,
  shots,
  events,
  playheadSeconds,
  onSeek,
  selectedShotId,
  onSelectShot,
  playbackSpeed,
  onSpeedChange,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const width = 700;
  const height = 140;
  const margin = { left: 40, right: 10, top: 10, bottom: 24 };
  const innerW = width - margin.left - margin.right;

  const tToX = (t: number) =>
    margin.left + ((t - timeSpan.start) / Math.max(timeSpan.duration, 0.001)) * innerW;

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    ctx.clearRect(0, 0, width, height);
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, width, height);

    // Draw beat lanes (top row)
    const beatRowY = margin.top;
    const beatRowH = 22;
    beats.forEach((beat, i) => {
      const x0 = tToX(beat.time_start);
      const x1 = tToX(beat.time_end);
      ctx.fillStyle = BEAT_COLORS[i % BEAT_COLORS.length] + '80';
      ctx.fillRect(x0, beatRowY, x1 - x0, beatRowH);
      ctx.strokeStyle = BEAT_COLORS[i % BEAT_COLORS.length];
      ctx.lineWidth = 1;
      ctx.strokeRect(x0, beatRowY, x1 - x0, beatRowH);
      ctx.fillStyle = '#fff';
      ctx.font = '10px monospace';
      ctx.fillText(beat.beat_id, x0 + 3, beatRowY + 14);
    });

    // Draw shot lanes (middle row)
    const shotRowY = beatRowY + beatRowH + 4;
    const shotRowH = 28;
    shots.forEach((shot, i) => {
      const x0 = tToX(shot.time_start);
      const x1 = tToX(shot.time_end);
      const isSelected = shot.shot_id === selectedShotId;
      ctx.fillStyle = isSelected
        ? '#FFD54F'
        : SHOT_COLORS[i % SHOT_COLORS.length] + 'A0';
      ctx.fillRect(x0, shotRowY, x1 - x0, shotRowH);
      ctx.strokeStyle = isSelected ? '#FFC107' : '#888';
      ctx.lineWidth = isSelected ? 2 : 1;
      ctx.strokeRect(x0, shotRowY, x1 - x0, shotRowH);
      ctx.fillStyle = isSelected ? '#000' : '#fff';
      ctx.font = '10px monospace';
      const label = `${shot.shot_id} (${shot.shot_type})`;
      ctx.fillText(label, x0 + 3, shotRowY + 16, x1 - x0 - 6);
    });

    // Draw event markers (below shots)
    const eventRowY = shotRowY + shotRowH + 4;
    events.forEach((event) => {
      const x = tToX(event.timestamp);
      ctx.strokeStyle = '#FF5722';
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(x, eventRowY);
      ctx.lineTo(x, eventRowY + 12);
      ctx.stroke();
      ctx.fillStyle = '#FF5722';
      ctx.beginPath();
      ctx.arc(x, eventRowY + 14, 3, 0, Math.PI * 2);
      ctx.fill();
    });

    // Time axis
    const axisY = height - margin.bottom;
    ctx.strokeStyle = '#555';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(margin.left, axisY);
    ctx.lineTo(width - margin.right, axisY);
    ctx.stroke();

    // Time ticks
    const tickInterval = Math.max(1, Math.ceil(timeSpan.duration / 10));
    ctx.fillStyle = '#aaa';
    ctx.font = '10px monospace';
    for (let t = Math.ceil(timeSpan.start); t <= timeSpan.end; t += tickInterval) {
      const x = tToX(t);
      ctx.beginPath();
      ctx.moveTo(x, axisY);
      ctx.lineTo(x, axisY + 4);
      ctx.stroke();
      ctx.fillText(`${t}s`, x - 8, axisY + 14);
    }

    // Playhead
    const px = tToX(playheadSeconds);
    ctx.strokeStyle = '#FFF';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px, margin.top);
    ctx.lineTo(px, axisY);
    ctx.stroke();
    ctx.fillStyle = '#FFF';
    ctx.beginPath();
    ctx.moveTo(px - 4, margin.top);
    ctx.lineTo(px + 4, margin.top);
    ctx.lineTo(px, margin.top + 6);
    ctx.closePath();
    ctx.fill();
  }, [beats, shots, events, playheadSeconds, selectedShotId, timeSpan]);

  const handleClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return;
    const x = e.clientX - rect.left;
    const t = timeSpan.start + ((x - margin.left) / innerW) * timeSpan.duration;
    const clampedT = Math.max(timeSpan.start, Math.min(timeSpan.end, t));

    // Check if clicking on a shot
    const shotRowY = margin.top + 26;
    const shotRowH = 28;
    const y = e.clientY - rect.top;
    if (y >= shotRowY && y <= shotRowY + shotRowH) {
      const clicked = shots.find(
        (s) => clampedT >= s.time_start && clampedT <= s.time_end
      );
      if (clicked) {
        onSelectShot(clicked.shot_id === selectedShotId ? null : clicked.shot_id);
        return;
      }
    }

    onSeek(clampedT);
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
        <span className="muted" style={{ fontSize: 11 }}>Timeline</span>
        <span className="muted" style={{ fontSize: 11 }}>
          Speed:
        </span>
        {[0.5, 1, 2].map((s) => (
          <button
            key={s}
            className={`tag-button ${playbackSpeed === s ? 'active' : ''}`}
            onClick={() => onSpeedChange(s)}
            style={{ padding: '1px 6px', fontSize: 10 }}
          >
            {s}x
          </button>
        ))}
      </div>
      <canvas
        ref={canvasRef}
        width={width}
        height={height}
        onClick={handleClick}
        style={{ cursor: 'pointer', borderRadius: 4, border: '1px solid #333' }}
      />
    </div>
  );
}
