import { useEffect, useRef, useState } from 'react';
import type { SceneSummary, ShotTrajectory, TrajectoryPlan } from '../types';
import TopDownCanvas from '../components/TopDownCanvas';

interface Props {
  scene: SceneSummary | null;
  trajectory: TrajectoryPlan | null;
  selectedShotId: string | null;
}

export default function TrajectoryPanel({ scene, trajectory, selectedShotId }: Props) {
  const playbackDuration = selectedShotId
    ? trajectory?.trajectories.find(t => t.shot_id === selectedShotId)?.duration ?? 0
    : trajectory?.total_duration ?? 0;
  const [isPlaying, setIsPlaying] = useState(false);
  const [playheadSeconds, setPlayheadSeconds] = useState(0);
  const lastFrameRef = useRef<number | null>(null);

  useEffect(() => {
    setPlayheadSeconds(0);
    setIsPlaying(false);
    lastFrameRef.current = null;
  }, [trajectory, selectedShotId]);

  useEffect(() => {
    if (!isPlaying || playbackDuration <= 0) {
      lastFrameRef.current = null;
      return;
    }

    let frameId = 0;
    const tick = (time: number) => {
      if (lastFrameRef.current == null) {
        lastFrameRef.current = time;
      }

      const delta = (time - lastFrameRef.current) / 1000;
      lastFrameRef.current = time;
      setPlayheadSeconds(prev => {
        const next = prev + delta;
        if (next >= playbackDuration) {
          setIsPlaying(false);
          return playbackDuration;
        }
        return next;
      });
      frameId = window.requestAnimationFrame(tick);
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [isPlaying, playbackDuration]);

  if (!scene || !trajectory) {
    return <div className="panel"><h3>Trajectory Preview</h3><p className="muted">No trajectory data</p></div>;
  }

  const selectedTraj = selectedShotId
    ? trajectory.trajectories.find(t => t.shot_id === selectedShotId)
    : null;
  const playbackState = samplePlaybackState(trajectory, playheadSeconds, selectedShotId);

  return (
    <div className="panel">
      <h3>Trajectory Preview</h3>
      <div className="tag-list" style={{ marginBottom: 12 }}>
        <button className="tag-button" onClick={() => setIsPlaying(prev => !prev)} disabled={playbackDuration <= 0}>
          {isPlaying ? 'Pause' : 'Play'}
        </button>
        <button className="tag-button" onClick={() => { setIsPlaying(false); setPlayheadSeconds(0); }}>
          Reset
        </button>
        <span className="muted">
          {playheadSeconds.toFixed(1)}s / {playbackDuration.toFixed(1)}s
        </span>
      </div>
      <input
        type="range"
        min={0}
        max={playbackDuration || 0}
        step={0.01}
        value={Math.min(playheadSeconds, playbackDuration || 0)}
        onChange={e => {
          setIsPlaying(false);
          setPlayheadSeconds(Number(e.target.value));
        }}
        style={{ width: '100%', marginBottom: 12 }}
      />
      <TopDownCanvas
        scene={scene}
        trajectories={trajectory.trajectories}
        selectedShotId={selectedShotId}
        currentCameraPosition={playbackState.position}
        currentLookAtPosition={playbackState.lookAt}
        currentShotId={playbackState.shotId}
        width={560}
        height={440}
      />

      {selectedTraj && (
        <div className="metrics-grid">
          <h4>Metrics: {selectedTraj.shot_id}</h4>
          <div className="metric-row">
            <span>Path Type:</span><span>{selectedTraj.path_type}</span>
          </div>
          <div className="metric-row">
            <span>FOV:</span><span>{selectedTraj.fov}</span>
          </div>
          <div className="metric-row">
            <span>Points:</span><span>{selectedTraj.sampled_points.length}</span>
          </div>
          <div className="metric-row">
            <span>Visibility:</span>
            <MetricBar value={selectedTraj.metrics.visibility_score} />
          </div>
          <div className="metric-row">
            <span>Smoothness:</span>
            <MetricBar value={selectedTraj.metrics.smoothness_score} />
          </div>
          <div className="metric-row">
            <span>Framing:</span>
            <MetricBar value={selectedTraj.metrics.framing_score} />
          </div>
          <div className="metric-row">
            <span>Clearance:</span>
            <MetricBar value={selectedTraj.metrics.clearance_score} />
          </div>
          <div className="metric-row">
            <span>Occlusion Risk:</span>
            <MetricBar value={selectedTraj.metrics.occlusion_risk} color="#c62828" />
          </div>
        </div>
      )}
    </div>
  );
}

function samplePlaybackState(
  trajectoryPlan: TrajectoryPlan,
  playheadSeconds: number,
  selectedShotId: string | null,
): {
  shotId: string | null;
  position: [number, number, number] | null;
  lookAt: [number, number, number] | null;
} {
  const shots = selectedShotId
    ? trajectoryPlan.trajectories.filter(t => t.shot_id === selectedShotId)
    : trajectoryPlan.trajectories;
  if (shots.length === 0) {
    return { shotId: null, position: null, lookAt: null };
  }

  let remaining = Math.max(0, playheadSeconds);
  let activeShot: ShotTrajectory = shots[shots.length - 1];

  for (const shot of shots) {
    if (remaining <= shot.duration) {
      activeShot = shot;
      break;
    }
    remaining -= shot.duration;
  }

  if (activeShot.sampled_points.length === 0) {
    return { shotId: activeShot.shot_id, position: null, lookAt: activeShot.look_at_position };
  }

  if (activeShot.sampled_points.length === 1 || activeShot.duration <= 0) {
    return {
      shotId: activeShot.shot_id,
      position: activeShot.sampled_points[0],
      lookAt: activeShot.look_at_position,
    };
  }

  const normalized = Math.min(1, activeShot.duration <= 0 ? 1 : remaining / activeShot.duration);
  const scaledIndex = normalized * (activeShot.sampled_points.length - 1);
  const startIndex = Math.floor(scaledIndex);
  const endIndex = Math.min(activeShot.sampled_points.length - 1, startIndex + 1);
  const localT = scaledIndex - startIndex;
  return {
    shotId: activeShot.shot_id,
    position: lerpPoint(activeShot.sampled_points[startIndex], activeShot.sampled_points[endIndex], localT),
    lookAt: activeShot.look_at_position,
  };
}

function lerpPoint(
  a: [number, number, number],
  b: [number, number, number],
  t: number,
): [number, number, number] {
  return [
    a[0] + (b[0] - a[0]) * t,
    a[1] + (b[1] - a[1]) * t,
    a[2] + (b[2] - a[2]) * t,
  ];
}

function MetricBar({ value, color = '#4CAF50' }: { value: number; color?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1 }}>
      <div style={{
        width: 100, height: 8, background: '#333', borderRadius: 4, overflow: 'hidden',
      }}>
        <div style={{
          width: `${value * 100}%`, height: '100%', background: color, borderRadius: 4,
        }} />
      </div>
      <span style={{ fontSize: 11, fontFamily: 'monospace' }}>{(value * 100).toFixed(0)}%</span>
    </div>
  );
}
