import { useEffect, useRef, useState } from 'react';
import type { SceneSummary, ShotTrajectory, TrajectoryPlan, TemporalGenerateResponse, ObjectTrack } from '../types';
import TopDownCanvas from '../components/TopDownCanvas';
import ThreeTrajectoryPreview from '../components/ThreeTrajectoryPreview';
import AnimatedThreePreview from '../components/AnimatedThreePreview';
import TemporalTimeline from '../components/TemporalTimeline';
import type { AppMode } from '../App';

interface Props {
  scene: SceneSummary | null;
  trajectory: TrajectoryPlan | null;
  selectedShotId: string | null;
  mode?: AppMode;
  temporalResult?: TemporalGenerateResponse | null;
}

export default function TrajectoryPanel({ scene, trajectory, selectedShotId, mode = 'static', temporalResult }: Props) {
  const playbackDuration = selectedShotId
    ? trajectory?.trajectories.find(t => t.shot_id === selectedShotId)?.duration ?? 0
    : trajectory?.total_duration ?? 0;
  const [isPlaying, setIsPlaying] = useState(false);
  const [playheadSeconds, setPlayheadSeconds] = useState(0);
  const [previewMode, setPreviewMode] = useState<'camera' | 'observer'>('camera');
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

  // Temporal mode rendering
  if (mode === 'temporal') {
    const tempTraj = temporalResult?.temporal_trajectory_plan;
    const tempPlan = temporalResult?.temporal_directing_plan;
    const timeSpan = tempPlan?.time_span;
    const objectTracks: ObjectTrack[] = [];

    if (!scene || !tempTraj || !tempPlan || !timeSpan) {
      return <div className="panel"><h3>Temporal Preview</h3><p className="muted">No temporal data</p></div>;
    }

    const totalDuration = timeSpan.duration;
    const [tempPlayhead, setTempPlayhead] = useState(timeSpan.start);
    const [tempPlaying, setTempPlaying] = useState(false);
    const [tempSpeed, setTempSpeed] = useState(1);
    const [tempPreviewMode, setTempPreviewMode] = useState<'camera' | 'observer'>('observer');
    const tempLastFrame = useRef<number | null>(null);

    useEffect(() => {
      setTempPlayhead(timeSpan.start);
      setTempPlaying(false);
      tempLastFrame.current = null;
    }, [temporalResult]);

    useEffect(() => {
      if (!tempPlaying || totalDuration <= 0) {
        tempLastFrame.current = null;
        return;
      }
      let frameId = 0;
      const tick = (time: number) => {
        if (tempLastFrame.current == null) tempLastFrame.current = time;
        const delta = ((time - tempLastFrame.current) / 1000) * tempSpeed;
        tempLastFrame.current = time;
        setTempPlayhead(prev => {
          const next = prev + delta;
          if (next >= timeSpan.end) {
            setTempPlaying(false);
            return timeSpan.end;
          }
          return next;
        });
        frameId = window.requestAnimationFrame(tick);
      };
      frameId = window.requestAnimationFrame(tick);
      return () => window.cancelAnimationFrame(frameId);
    }, [tempPlaying, totalDuration, tempSpeed]);

    return (
      <div className="panel">
        <h3>Temporal Preview</h3>
        <div className="tag-list" style={{ marginBottom: 8 }}>
          <button className="tag-button" onClick={() => setTempPlaying(p => !p)}>
            {tempPlaying ? 'Pause' : 'Play'}
          </button>
          <button className="tag-button" onClick={() => { setTempPlaying(false); setTempPlayhead(timeSpan.start); }}>
            Reset
          </button>
          <span className="muted">{tempPlayhead.toFixed(1)}s / {timeSpan.end.toFixed(1)}s</span>
        </div>
        <input
          type="range"
          min={timeSpan.start}
          max={timeSpan.end}
          step={0.01}
          value={tempPlayhead}
          onChange={e => { setTempPlaying(false); setTempPlayhead(Number(e.target.value)); }}
          style={{ width: '100%', marginBottom: 8 }}
        />
        <TemporalTimeline
          timeSpan={timeSpan}
          beats={tempPlan.beats}
          shots={tempPlan.shots}
          events={[]}
          playheadSeconds={tempPlayhead}
          onSeek={t => { setTempPlaying(false); setTempPlayhead(t); }}
          selectedShotId={selectedShotId}
          onSelectShot={() => {}}
          playbackSpeed={tempSpeed}
          onSpeedChange={setTempSpeed}
        />
        <div className="preview-3d-block" style={{ marginTop: 8 }}>
          <div className="preview-3d-header">
            <span>3D Animated Preview</span>
            <div className="tag-list" style={{ marginTop: 0 }}>
              <button
                className={`tag-button ${tempPreviewMode === 'camera' ? 'active' : ''}`}
                onClick={() => setTempPreviewMode('camera')}
              >Camera</button>
              <button
                className={`tag-button ${tempPreviewMode === 'observer' ? 'active' : ''}`}
                onClick={() => setTempPreviewMode('observer')}
              >Observer</button>
            </div>
          </div>
          <AnimatedThreePreview
            scene={scene}
            trajectories={tempTraj.trajectories}
            objectTracks={objectTracks}
            playheadSeconds={tempPlayhead}
            currentShotId={selectedShotId}
            viewMode={tempPreviewMode}
            width={760}
            height={360}
          />
        </div>
      </div>
    );
  }

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
      <div className="preview-3d-block">
        <div className="preview-3d-header">
          <span>3D Camera Preview</span>
          <div className="tag-list" style={{ marginTop: 0 }}>
            <button
              className={`tag-button ${previewMode === 'camera' ? 'active' : ''}`}
              onClick={() => setPreviewMode('camera')}
              type="button"
            >
              Camera View
            </button>
            <button
              className={`tag-button ${previewMode === 'observer' ? 'active' : ''}`}
              onClick={() => setPreviewMode('observer')}
              type="button"
            >
              Observer View
            </button>
            <span className="muted">
              FOV {playbackState.fov.toFixed(1)}°
            </span>
          </div>
        </div>
        <ThreeTrajectoryPreview
          scene={scene}
          trajectories={trajectory.trajectories}
          currentCameraPosition={playbackState.position}
          currentLookAtPosition={playbackState.lookAt}
          currentFov={playbackState.fov}
          currentShotId={playbackState.shotId}
          viewMode={previewMode}
          width={760}
          height={360}
        />
      </div>
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
  fov: number;
} {
  const shots = selectedShotId
    ? trajectoryPlan.trajectories.filter(t => t.shot_id === selectedShotId)
    : trajectoryPlan.trajectories;
  if (shots.length === 0) {
    return { shotId: null, position: null, lookAt: null, fov: 60 };
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
    return { shotId: activeShot.shot_id, position: null, lookAt: activeShot.look_at_position, fov: activeShot.fov };
  }

  if (activeShot.sampled_points.length === 1 || activeShot.duration <= 0) {
    return {
      shotId: activeShot.shot_id,
      position: activeShot.sampled_points[0],
      lookAt: activeShot.look_at_position,
      fov: activeShot.fov,
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
    fov: activeShot.fov,
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
