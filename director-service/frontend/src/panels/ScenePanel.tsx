import { useEffect, useRef, useState } from 'react';
import type {
  SceneSummary,
  SceneTimeline,
  ObjectTrackSample,
  SceneEvent,
  SemanticSceneEvent,
} from '../types';
import TopDownCanvas from '../components/TopDownCanvas';
import type { AppMode } from '../App';

interface Props {
  scene: SceneSummary | null;
  mode?: AppMode;
  sceneTimeline?: SceneTimeline | null;
}

export default function ScenePanel({ scene, mode = 'static', sceneTimeline }: Props) {
  const [playheadSeconds, setPlayheadSeconds] = useState(sceneTimeline?.time_span.start ?? 0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const lastFrameRef = useRef<number | null>(null);

  const hasTemporalScene = mode === 'temporal' && !!sceneTimeline;
  const timeSpan = sceneTimeline?.time_span;

  useEffect(() => {
    setPlayheadSeconds(sceneTimeline?.time_span.start ?? 0);
    setIsPlaying(false);
    lastFrameRef.current = null;
  }, [sceneTimeline]);

  useEffect(() => {
    if (!hasTemporalScene || !isPlaying || !timeSpan || timeSpan.duration <= 0) {
      lastFrameRef.current = null;
      return;
    }

    let frameId = 0;
    const tick = (time: number) => {
      if (lastFrameRef.current == null) {
        lastFrameRef.current = time;
      }
      const delta = ((time - lastFrameRef.current) / 1000) * playbackSpeed;
      lastFrameRef.current = time;

      setPlayheadSeconds(prev => {
        const next = prev + delta;
        if (next >= timeSpan.end) {
          setIsPlaying(false);
          return timeSpan.end;
        }
        return next;
      });

      frameId = window.requestAnimationFrame(tick);
    };

    frameId = window.requestAnimationFrame(tick);
    return () => window.cancelAnimationFrame(frameId);
  }, [hasTemporalScene, isPlaying, playbackSpeed, timeSpan]);

  if (!scene) {
    return <div className="panel"><h3>Scene</h3><p className="muted">No scene loaded</p></div>;
  }

  const objectPositionOverrides: Record<string, [number, number, number]> = {};
  const objectVisibilityOverrides: Record<string, boolean> = {};
  const rawEvents: SceneEvent[] = sceneTimeline?.raw_events ?? sceneTimeline?.events ?? [];
  const semanticEvents: SemanticSceneEvent[] = sceneTimeline?.semantic_events ?? [];
  if (hasTemporalScene && sceneTimeline) {
    for (const track of sceneTimeline.object_tracks) {
      if (track.samples.length === 0) continue;
      const sampled = sampleTrack(track.samples, playheadSeconds);
      objectPositionOverrides[track.object_id] = sampled.position;
      objectVisibilityOverrides[track.object_id] = sampled.visible;
    }
  }

  const activeSemanticEvents = hasTemporalScene
    ? semanticEvents.filter(
        evt => isTimeInWindow(playheadSeconds, evt.time_start, evt.time_end),
      )
    : [];
  const activeRawEvents = hasTemporalScene
    ? rawEvents.filter(
        evt => isTimeInWindow(playheadSeconds, evt.timestamp, evt.timestamp + evt.duration),
      )
    : [];
  const activeEventObjectIds = (activeSemanticEvents.length > 0 ? activeSemanticEvents : activeRawEvents)
    .flatMap(evt => evt.object_ids);
  const activeRawEventSummaries = summarizeRawEvents(activeRawEvents);
  const handleScenePlayToggle = () => {
    if (!timeSpan) return;
    setIsPlaying(prev => {
      if (prev) return false;
      if (playheadSeconds >= timeSpan.end - 0.001) {
        setPlayheadSeconds(timeSpan.start);
      }
      return true;
    });
  };

  return (
    <div className="panel">
      <h3>Scene: {scene.scene_name}</h3>
      <p className="muted">{scene.description}</p>
      <div className="meta">
        <span>Type: {scene.scene_type}</span>
        <span>Size: {scene.bounds.width}m x {scene.bounds.length}m x {scene.bounds.height}m</span>
        <span>Objects: {scene.objects.length}</span>
        {hasTemporalScene && timeSpan && <span>Timeline: {timeSpan.duration.toFixed(1)}s</span>}
        {hasTemporalScene && <span>Events: raw {rawEvents.length}{semanticEvents.length > 0 ? ` / semantic ${semanticEvents.length}` : ''}</span>}
      </div>

      {hasTemporalScene && timeSpan && (
        <>
          <h4>Timeline Preview</h4>
          <div className="tag-list" style={{ marginBottom: 8 }}>
            <button className="tag-button" type="button" onClick={handleScenePlayToggle}>
              {isPlaying ? 'Pause' : 'Play'}
            </button>
            <button
              className="tag-button"
              type="button"
              onClick={() => {
                setIsPlaying(false);
                setPlayheadSeconds(timeSpan.start);
              }}
            >
              Reset
            </button>
            <button className={`tag-button ${playbackSpeed === 0.5 ? 'active' : ''}`} type="button" onClick={() => setPlaybackSpeed(0.5)}>0.5x</button>
            <button className={`tag-button ${playbackSpeed === 1 ? 'active' : ''}`} type="button" onClick={() => setPlaybackSpeed(1)}>1x</button>
            <button className={`tag-button ${playbackSpeed === 2 ? 'active' : ''}`} type="button" onClick={() => setPlaybackSpeed(2)}>2x</button>
            <span className="muted">{playheadSeconds.toFixed(2)}s / {timeSpan.end.toFixed(2)}s</span>
          </div>
          <input
            type="range"
            min={timeSpan.start}
            max={timeSpan.end}
            step={0.01}
            value={playheadSeconds}
            onChange={event => {
              setIsPlaying(false);
              setPlayheadSeconds(Number(event.target.value));
            }}
            style={{ width: '100%', marginBottom: 8 }}
          />
          {activeSemanticEvents.length > 0 && (
            <div className="tag-list" style={{ marginBottom: 8 }}>
              {activeSemanticEvents.map(evt => (
                <span key={evt.semantic_id} className="tag tag-blue">
                  {evt.label}: {evt.summary}
                </span>
              ))}
            </div>
          )}
          {activeSemanticEvents.length === 0 && activeRawEvents.length > 0 && (
            <div className="tag-list" style={{ marginBottom: 8 }}>
              {activeRawEventSummaries.map(summary => (
                <span key={summary} className="tag tag-blue">
                  {summary}
                </span>
              ))}
            </div>
          )}
        </>
      )}

      <h4>Objects</h4>
      <table>
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Category</th>
            <th>Importance</th>
            <th>Position</th>
            <th>Tags</th>
          </tr>
        </thead>
        <tbody>
          {scene.objects.map(obj => (
            <tr key={obj.id}>
              <td><code>{obj.id}</code></td>
              <td>{obj.name}</td>
              <td>{obj.category}</td>
              <td>{obj.importance}</td>
              <td>
                <code>
                  {(objectPositionOverrides[obj.id]?.[0] ?? obj.position[0]).toFixed(2)},
                  {(objectPositionOverrides[obj.id]?.[1] ?? obj.position[1]).toFixed(2)},
                  {(objectPositionOverrides[obj.id]?.[2] ?? obj.position[2]).toFixed(2)}
                </code>
              </td>
              <td>{obj.tags.join(', ')}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <h4>Top-Down View</h4>
      <TopDownCanvas
        scene={scene}
        objectPositionOverrides={hasTemporalScene ? objectPositionOverrides : undefined}
        objectVisibilityOverrides={hasTemporalScene ? objectVisibilityOverrides : undefined}
        highlightedObjectIds={hasTemporalScene ? activeEventObjectIds : undefined}
      />
    </div>
  );
}

function sampleTrack(
  samples: ObjectTrackSample[],
  time: number,
): { position: [number, number, number]; visible: boolean } {
  if (samples.length === 0) {
    return { position: [0, 0, 0], visible: true };
  }
  if (samples.length === 1 || time <= samples[0].timestamp) {
    return { position: samples[0].position, visible: samples[0].visible };
  }
  if (time >= samples[samples.length - 1].timestamp) {
    const last = samples[samples.length - 1];
    return { position: last.position, visible: last.visible };
  }

  for (let index = 0; index < samples.length - 1; index += 1) {
    const current = samples[index];
    const next = samples[index + 1];
    if (time >= current.timestamp && time <= next.timestamp) {
      const duration = next.timestamp - current.timestamp;
      const ratio = duration > 0 ? (time - current.timestamp) / duration : 0;
      return {
        position: lerpTuple(current.position, next.position, ratio),
        visible: ratio < 0.5 ? current.visible : next.visible,
      };
    }
  }

  const fallback = samples[samples.length - 1];
  return { position: fallback.position, visible: fallback.visible };
}

function lerpTuple(
  a: [number, number, number],
  b: [number, number, number],
  ratio: number,
): [number, number, number] {
  return [
    a[0] + (b[0] - a[0]) * ratio,
    a[1] + (b[1] - a[1]) * ratio,
    a[2] + (b[2] - a[2]) * ratio,
  ];
}

function isTimeInWindow(time: number, start: number, end: number): boolean {
  const normalizedEnd = end >= start ? end : start;
  if (Math.abs(normalizedEnd - start) < 0.001) {
    return Math.abs(time - start) <= 0.35;
  }
  return time >= start && time <= normalizedEnd;
}

function summarizeRawEvents(events: SceneEvent[]): string[] {
  const counts = new Map<string, number>();
  for (const evt of events) {
    const key = (evt.event_type || 'event').trim().toLowerCase();
    if (!key) continue;
    counts.set(key, (counts.get(key) ?? 0) + 1);
  }

  return Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([type, count]) => `${type} x${count}`);
}
