import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import type { SceneSummary, TemporalShotTrajectory, ObjectTrack, TimedTrajectoryPoint } from '../types';

interface Props {
  scene: SceneSummary;
  trajectories: TemporalShotTrajectory[];
  objectTracks: ObjectTrack[];
  shotTransitions?: Record<string, string>;
  playheadSeconds: number;
  currentShotId: string | null;
  viewMode: 'camera' | 'observer';
  width?: number;
  height?: number;
}

export default function AnimatedThreePreview({
  scene,
  trajectories,
  objectTracks,
  shotTransitions = {},
  playheadSeconds,
  currentShotId,
  viewMode = 'observer',
  width = 760,
  height = 360,
}: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<AnimatedRuntime | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;
    const runtime = createAnimatedRuntime(mount, width, height);
    runtimeRef.current = runtime;
    return () => {
      runtime.dispose();
      runtimeRef.current = null;
    };
  }, [width, height]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;
    rebuildScene(runtime, scene, trajectories, objectTracks, currentShotId);
  }, [scene, trajectories, objectTracks, currentShotId]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) return;
    updateAnimatedFrame(runtime, playheadSeconds, trajectories, objectTracks, scene, viewMode);
  }, [playheadSeconds, viewMode, trajectories, objectTracks, scene]);

  const flashOpacity = computeTransitionFlashOpacity(playheadSeconds, trajectories, shotTransitions);

  return (
    <div style={{ width, height, position: 'relative' }} className="preview-3d-shell">
      <div ref={mountRef} style={{ width, height }} />
      {flashOpacity > 0 && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            pointerEvents: 'none',
            background: `rgba(255,255,255,${flashOpacity.toFixed(3)})`,
            mixBlendMode: 'screen',
          }}
        />
      )}
    </div>
  );
}

interface AnimatedRuntime {
  renderer: THREE.WebGLRenderer;
  worldScene: THREE.Scene;
  playbackCamera: THREE.PerspectiveCamera;
  observerCamera: THREE.PerspectiveCamera;
  root: THREE.Group;
  trackMeshes: Map<string, THREE.Mesh>;
  staticObjectMap: Map<string, SceneSummary['objects'][number]>;
  playbackMarker: THREE.Group;
  lookLine: THREE.Line;
  mount: HTMLDivElement;
  dispose: () => void;
}

function createAnimatedRuntime(mount: HTMLDivElement, width: number, height: number): AnimatedRuntime {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(width, height);
  renderer.setClearColor(0x09111c, 1);
  mount.innerHTML = '';
  mount.appendChild(renderer.domElement);

  const worldScene = new THREE.Scene();
  worldScene.fog = new THREE.Fog(0x09111c, 7, 28);

  const root = new THREE.Group();
  worldScene.add(root);

  worldScene.add(new THREE.AmbientLight(0xffffff, 1.2));
  const keyLight = new THREE.DirectionalLight(0xdde7ff, 1.8);
  keyLight.position.set(6, 8, 4);
  worldScene.add(keyLight);
  const rimLight = new THREE.DirectionalLight(0x7cc7ff, 0.7);
  rimLight.position.set(-4, 3, -6);
  worldScene.add(rimLight);

  const observerCamera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
  const playbackCamera = new THREE.PerspectiveCamera(60, width / height, 0.1, 100);

  const playbackMarker = createCameraMarker();
  root.add(playbackMarker);

  const lookLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: 0.18, gapSize: 0.12, transparent: true, opacity: 0.85 }),
  );
  root.add(lookLine);

  return {
    renderer,
    worldScene,
    playbackCamera,
    observerCamera,
    root,
    trackMeshes: new Map(),
    staticObjectMap: new Map(),
    playbackMarker,
    lookLine,
    mount,
    dispose: () => {
      renderer.dispose();
      mount.innerHTML = '';
    },
  };
}

function rebuildScene(
  runtime: AnimatedRuntime,
  scene: SceneSummary,
  trajectories: TemporalShotTrajectory[],
  objectTracks: ObjectTrack[],
  currentShotId: string | null,
) {
  runtime.root.clear();
  runtime.root.add(runtime.playbackMarker);
  runtime.root.add(runtime.lookLine);
  runtime.trackMeshes.clear();
  runtime.staticObjectMap.clear();

  // Floor
  const floorGeo = new THREE.PlaneGeometry(scene.bounds.width, scene.bounds.length);
  const floor = new THREE.Mesh(floorGeo, new THREE.MeshStandardMaterial({ color: 0x132033, roughness: 0.95 }));
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(scene.bounds.width / 2, 0, scene.bounds.length / 2);
  runtime.root.add(floor);

  // Room edges
  const roomEdges = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(scene.bounds.width, scene.bounds.height, scene.bounds.length)),
    new THREE.LineBasicMaterial({ color: 0x35547c, transparent: true, opacity: 0.65 }),
  );
  roomEdges.position.set(scene.bounds.width / 2, scene.bounds.height / 2, scene.bounds.length / 2);
  runtime.root.add(roomEdges);

  // Static objects
  const trackedIds = new Set(objectTracks.map((t) => t.object_id));
  scene.objects.forEach((obj) => {
    runtime.staticObjectMap.set(obj.id, obj);
    if (trackedIds.has(obj.id)) return; // Skip tracked objects, they're animated
    const geo = new THREE.BoxGeometry(
      Math.max(obj.size[0], 0.08),
      Math.max(obj.size[1], 0.08),
      Math.max(obj.size[2], 0.08),
    );
    const mat = new THREE.MeshStandardMaterial({
      color: resolveObjectColor(obj.category, obj.name, obj.id),
      roughness: 0.75,
    });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.position.set(obj.position[0], obj.position[1], obj.position[2]);
    runtime.root.add(mesh);
    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0xe6eefc, transparent: true, opacity: 0.35 }),
    );
    edge.position.copy(mesh.position);
    runtime.root.add(edge);
  });

  // Create meshes for tracked objects
  const sceneSpan = Math.max(scene.bounds.width, scene.bounds.length);
  const minFootprint = Math.max(0.14, sceneSpan * 0.02);
  const minHeight = Math.max(0.12, sceneSpan * 0.018);
  objectTracks.forEach((track) => {
    const obj = scene.objects.find((o) => o.id === track.object_id);
    const isVehicle = (obj?.category ?? '').toLowerCase() === 'vehicle';
    const vehicleFootprint = Math.max(minFootprint, 0.22);
    const vehicleHeight = Math.max(minHeight, 0.14);
    const size: [number, number, number] = obj
      ? [
          Math.max(obj.size[0], isVehicle ? vehicleFootprint : minFootprint),
          Math.max(obj.size[1], isVehicle ? vehicleHeight : minHeight),
          Math.max(obj.size[2], isVehicle ? vehicleFootprint : minFootprint),
        ]
      : [0.4, 1.6, 0.4];
    const geo = new THREE.BoxGeometry(size[0], size[1], size[2]);
    const mat = new THREE.MeshStandardMaterial({
      color: resolveObjectColor(obj?.category ?? 'vehicle', obj?.name, obj?.id),
      roughness: 0.45,
      metalness: 0.25,
      emissive: 0x16212f,
      emissiveIntensity: 0.55,
    });
    const mesh = new THREE.Mesh(geo, mat);
    const initialSupportY = obj ? computeSupportSurfaceY(obj.position[0], obj.position[2], runtime.staticObjectMap, obj.id) : null;
    const initialY = obj
      ? Math.max(obj.position[1] + size[1] / 2, (initialSupportY ?? obj.position[1]) + size[1] / 2 + 0.01)
      : size[1] / 2;
    if (obj) {
      mesh.position.set(obj.position[0], initialY, obj.position[2]);
    }
    runtime.root.add(mesh);
    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0xffcc80, transparent: true, opacity: 0.5 }),
    );
    mesh.add(edge);
    runtime.trackMeshes.set(track.object_id, mesh);

    // Draw track path
    if (track.samples.length >= 2) {
      const pathPoints = track.samples.map((s) => {
        const supportY = computeSupportSurfaceY(s.position[0], s.position[2], runtime.staticObjectMap, track.object_id);
        const centerY = Math.max(
          s.position[1] + size[1] / 2,
          (supportY ?? s.position[1]) + size[1] / 2 + 0.01,
        );
        return new THREE.Vector3(s.position[0], centerY, s.position[2]);
      });
      const pathGeo = new THREE.BufferGeometry().setFromPoints(pathPoints);
      const pathLine = new THREE.Line(pathGeo, new THREE.LineBasicMaterial({
        color: 0x96c7ff,
        transparent: true,
        opacity: 0.55,
      }));
      runtime.root.add(pathLine);
    }
  });

  // Fallback: if a vehicle has no valid track mesh, still render it as a simple cube.
  scene.objects.forEach((obj) => {
    if ((obj.category ?? '').toLowerCase() !== 'vehicle') return;
    if (runtime.trackMeshes.has(obj.id)) return;
    const size: [number, number, number] = [
      Math.max(obj.size[0], Math.max(minFootprint, 0.22)),
      Math.max(obj.size[1], Math.max(minHeight, 0.14)),
      Math.max(obj.size[2], Math.max(minFootprint, 0.22)),
    ];
    const geo = new THREE.BoxGeometry(size[0], size[1], size[2]);
    const mat = new THREE.MeshStandardMaterial({
      color: resolveObjectColor(obj.category, obj.name, obj.id),
      roughness: 0.45,
      metalness: 0.25,
      emissive: 0x16212f,
      emissiveIntensity: 0.55,
    });
    const mesh = new THREE.Mesh(geo, mat);
    const supportY = computeSupportSurfaceY(obj.position[0], obj.position[2], runtime.staticObjectMap, obj.id);
    const centerY = Math.max(
      obj.position[1] + size[1] / 2,
      (supportY ?? obj.position[1]) + size[1] / 2 + 0.01,
    );
    mesh.position.set(obj.position[0], centerY, obj.position[2]);
    runtime.root.add(mesh);
    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(geo),
      new THREE.LineBasicMaterial({ color: 0xffcc80, transparent: true, opacity: 0.5 }),
    );
    mesh.add(edge);
    runtime.trackMeshes.set(obj.id, mesh);
  });

  // Draw trajectory paths
  trajectories.forEach((traj, index) => {
    if (traj.timed_points.length < 2) return;
    const isActive = currentShotId ? traj.shot_id === currentShotId : false;
    const points = traj.timed_points.map((p) => new THREE.Vector3(p.position[0], p.position[1], p.position[2]));
    const geo = new THREE.BufferGeometry().setFromPoints(points);
    const mat = new THREE.LineBasicMaterial({
      color: shotColor(index),
      transparent: true,
      opacity: currentShotId ? (isActive ? 1 : 0.22) : 0.5,
    });
    runtime.root.add(new THREE.Line(geo, mat));
  });

  // Position observer camera
  const dist = Math.max(scene.bounds.width, scene.bounds.length) * 1.02;
  runtime.observerCamera.position.set(
    scene.bounds.width / 2 + dist * 0.65,
    Math.max(scene.bounds.height * 1.55, 3.8),
    scene.bounds.length / 2 + dist * 0.78,
  );
  runtime.observerCamera.lookAt(scene.bounds.width / 2, scene.bounds.height * 0.35, scene.bounds.length / 2);
}

function updateAnimatedFrame(
  runtime: AnimatedRuntime,
  playheadSeconds: number,
  trajectories: TemporalShotTrajectory[],
  objectTracks: ObjectTrack[],
  scene: SceneSummary,
  viewMode: 'camera' | 'observer',
) {
  // Update tracked object positions
  objectTracks.forEach((track) => {
    const mesh = runtime.trackMeshes.get(track.object_id);
    if (!mesh || track.samples.length === 0) return;
    const pos = interpolateTrackPosition(track.samples, playheadSeconds);
    const obj = runtime.staticObjectMap.get(track.object_id);
    const halfH = obj ? Math.max(obj.size[1] / 2, 0.07) : 0.8;
    const supportY = computeSupportSurfaceY(pos[0], pos[2], runtime.staticObjectMap, track.object_id);
    const centerY = Math.max(pos[1] + halfH, (supportY ?? pos[1]) + halfH + 0.01);
    mesh.position.set(pos[0], centerY, pos[2]);
    const activeSample = sampleTrackAtTime(track.samples, playheadSeconds);
    mesh.visible = activeSample?.visible ?? true;
  });

  // Find active trajectory point
  const state = sampleTemporalPlayback(trajectories, playheadSeconds);
  const fallbackPos: [number, number, number] = [scene.bounds.width / 2, 1.6, scene.bounds.length * 0.85];
  const fallbackLookAt: [number, number, number] = [scene.bounds.width / 2, 1.0, scene.bounds.length / 2];

  const pos = state.position ?? fallbackPos;
  const lookAt = state.lookAt ?? fallbackLookAt;
  const fov = state.fov > 1 ? state.fov : 60;

  runtime.playbackCamera.position.set(pos[0], pos[1], pos[2]);
  runtime.playbackCamera.fov = fov;
  runtime.playbackCamera.updateProjectionMatrix();
  runtime.playbackCamera.lookAt(lookAt[0], lookAt[1], lookAt[2]);

  runtime.playbackMarker.position.set(pos[0], pos[1], pos[2]);
  runtime.playbackMarker.lookAt(lookAt[0], lookAt[1], lookAt[2]);

  const showObserver = viewMode === 'observer';
  runtime.playbackMarker.visible = showObserver;
  runtime.lookLine.visible = showObserver;

  runtime.lookLine.geometry.dispose();
  runtime.lookLine.geometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(pos[0], pos[1], pos[2]),
    new THREE.Vector3(lookAt[0], lookAt[1], lookAt[2]),
  ]);
  if (runtime.lookLine.material instanceof THREE.LineDashedMaterial) {
    runtime.lookLine.computeLineDistances();
  }

  runtime.renderer.render(runtime.worldScene, viewMode === 'observer' ? runtime.observerCamera : runtime.playbackCamera);
}

function sampleTemporalPlayback(
  trajectories: TemporalShotTrajectory[],
  playheadSeconds: number,
): { shotId: string | null; position: [number, number, number] | null; lookAt: [number, number, number] | null; fov: number } {
  for (const traj of trajectories) {
    if (playheadSeconds >= traj.time_start && playheadSeconds <= traj.time_end && traj.timed_points.length > 0) {
      return { shotId: traj.shot_id, ...interpolateTimedPoints(traj.timed_points, playheadSeconds) };
    }
  }
  // Find closest trajectory
  if (trajectories.length > 0) {
    const sorted = [...trajectories].sort((a, b) => a.time_start - b.time_start);
    if (playheadSeconds <= sorted[0].time_start && sorted[0].timed_points.length > 0) {
      const p = sorted[0].timed_points[0];
      return { shotId: sorted[0].shot_id, position: p.position, lookAt: p.look_at, fov: p.fov };
    }
    const last = sorted[sorted.length - 1];
    if (last.timed_points.length > 0) {
      const p = last.timed_points[last.timed_points.length - 1];
      return { shotId: last.shot_id, position: p.position, lookAt: p.look_at, fov: p.fov };
    }
  }
  return { shotId: null, position: null, lookAt: null, fov: 60 };
}

function interpolateTimedPoints(
  points: TimedTrajectoryPoint[],
  time: number,
): { position: [number, number, number]; lookAt: [number, number, number]; fov: number } {
  if (points.length === 1) {
    return { position: points[0].position, lookAt: points[0].look_at, fov: points[0].fov };
  }
  if (time <= points[0].timestamp) {
    return { position: points[0].position, lookAt: points[0].look_at, fov: points[0].fov };
  }
  if (time >= points[points.length - 1].timestamp) {
    const p = points[points.length - 1];
    return { position: p.position, lookAt: p.look_at, fov: p.fov };
  }
  for (let i = 0; i < points.length - 1; i++) {
    if (time >= points[i].timestamp && time <= points[i + 1].timestamp) {
      const dt = points[i + 1].timestamp - points[i].timestamp;
      const t = dt > 0 ? (time - points[i].timestamp) / dt : 0;
      const smoothT = smoothstep(t);
      const p0 = points[Math.max(0, i - 1)].position;
      const p1 = points[i].position;
      const p2 = points[i + 1].position;
      const p3 = points[Math.min(points.length - 1, i + 2)].position;
      const l0 = points[Math.max(0, i - 1)].look_at;
      const l1 = points[i].look_at;
      const l2 = points[i + 1].look_at;
      const l3 = points[Math.min(points.length - 1, i + 2)].look_at;
      return {
        position: catmullRomTuple(p0, p1, p2, p3, smoothT),
        lookAt: catmullRomTuple(l0, l1, l2, l3, smoothT),
        fov: points[i].fov + (points[i + 1].fov - points[i].fov) * smoothT,
      };
    }
  }
  const p = points[points.length - 1];
  return { position: p.position, lookAt: p.look_at, fov: p.fov };
}

function interpolateTrackPosition(
  samples: { timestamp: number; position: [number, number, number]; visible: boolean }[],
  time: number,
): [number, number, number] {
  if (samples.length === 0) return [0, 0, 0];
  if (samples.length === 1) return samples[0].position;
  if (time <= samples[0].timestamp) return samples[0].position;
  if (time >= samples[samples.length - 1].timestamp) return samples[samples.length - 1].position;

  for (let i = 0; i < samples.length - 1; i++) {
    if (time >= samples[i].timestamp && time <= samples[i + 1].timestamp) {
      const dt = samples[i + 1].timestamp - samples[i].timestamp;
      const t = dt > 0 ? (time - samples[i].timestamp) / dt : 0;
      return lerpTuple(samples[i].position, samples[i + 1].position, t);
    }
  }
  return samples[samples.length - 1].position;
}

function sampleTrackAtTime(
  samples: { timestamp: number; position: [number, number, number]; visible: boolean }[],
  time: number,
): { timestamp: number; position: [number, number, number]; visible: boolean } | null {
  if (samples.length === 0) return null;
  if (samples.length === 1) return samples[0];
  if (time <= samples[0].timestamp) return samples[0];
  if (time >= samples[samples.length - 1].timestamp) return samples[samples.length - 1];
  for (let i = 0; i < samples.length - 1; i++) {
    if (time >= samples[i].timestamp && time <= samples[i + 1].timestamp) {
      return time - samples[i].timestamp <= samples[i + 1].timestamp - time ? samples[i] : samples[i + 1];
    }
  }
  return samples[samples.length - 1];
}

function lerpTuple(
  a: [number, number, number],
  b: [number, number, number],
  t: number,
): [number, number, number] {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function smoothstep(t: number): number {
  return t * t * (3 - 2 * t);
}

function catmullRomTuple(
  p0: [number, number, number],
  p1: [number, number, number],
  p2: [number, number, number],
  p3: [number, number, number],
  t: number,
): [number, number, number] {
  const t2 = t * t;
  const t3 = t2 * t;
  const x = 0.5 * (
    2 * p1[0]
    + (-p0[0] + p2[0]) * t
    + (2 * p0[0] - 5 * p1[0] + 4 * p2[0] - p3[0]) * t2
    + (-p0[0] + 3 * p1[0] - 3 * p2[0] + p3[0]) * t3
  );
  const y = 0.5 * (
    2 * p1[1]
    + (-p0[1] + p2[1]) * t
    + (2 * p0[1] - 5 * p1[1] + 4 * p2[1] - p3[1]) * t2
    + (-p0[1] + 3 * p1[1] - 3 * p2[1] + p3[1]) * t3
  );
  const z = 0.5 * (
    2 * p1[2]
    + (-p0[2] + p2[2]) * t
    + (2 * p0[2] - 5 * p1[2] + 4 * p2[2] - p3[2]) * t2
    + (-p0[2] + 3 * p1[2] - 3 * p2[2] + p3[2]) * t3
  );
  return [x, y, z];
}

function computeTransitionFlashOpacity(
  playheadSeconds: number,
  trajectories: TemporalShotTrajectory[],
  shotTransitions: Record<string, string>,
): number {
  let maxOpacity = 0;
  for (const traj of trajectories) {
    const transition = (shotTransitions[traj.shot_id] || traj.transition_in || 'cut').toLowerCase();
    const dt = playheadSeconds - traj.time_start;
    if (dt < 0) continue;

    if (transition === 'flash_cut') {
      const window = 0.12;
      if (dt <= window) {
        maxOpacity = Math.max(maxOpacity, (1 - dt / window) * 0.72);
      }
    } else if (transition === 'hard_cut') {
      const window = 0.07;
      if (dt <= window) {
        maxOpacity = Math.max(maxOpacity, (1 - dt / window) * 0.24);
      }
    } else if (transition === 'whip') {
      const window = 0.1;
      if (dt <= window) {
        maxOpacity = Math.max(maxOpacity, (1 - dt / window) * 0.14);
      }
    }
  }
  return maxOpacity;
}

function computeSupportSurfaceY(
  x: number,
  z: number,
  staticObjectMap: Map<string, SceneSummary['objects'][number]>,
  ignoreId?: string,
): number | null {
  let bestTop: number | null = null;
  for (const obj of staticObjectMap.values()) {
    if (ignoreId && obj.id === ignoreId) continue;
    const category = (obj.category ?? '').toLowerCase();
    if (category === 'vehicle' || category === 'character') continue;

    const halfX = Math.max(obj.size[0] / 2, 0.01);
    const halfZ = Math.max(obj.size[2] / 2, 0.01);
    const minX = obj.position[0] - halfX;
    const maxX = obj.position[0] + halfX;
    const minZ = obj.position[2] - halfZ;
    const maxZ = obj.position[2] + halfZ;
    if (x < minX || x > maxX || z < minZ || z > maxZ) continue;

    const top = obj.position[1] + obj.size[1] / 2;
    if (bestTop == null || top > bestTop) {
      bestTop = top;
    }
  }
  return bestTop;
}

function createCameraMarker(): THREE.Group {
  const group = new THREE.Group();
  const body = new THREE.Mesh(
    new THREE.BoxGeometry(0.18, 0.12, 0.28),
    new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.35 }),
  );
  group.add(body);
  const lens = new THREE.Mesh(
    new THREE.CylinderGeometry(0.035, 0.035, 0.14, 12),
    new THREE.MeshStandardMaterial({ color: 0x58a6ff, roughness: 0.2, transparent: true, opacity: 0.35 }),
  );
  lens.rotation.x = Math.PI / 2;
  lens.position.z = 0.18;
  group.add(lens);
  return group;
}

function shotColor(index: number): number {
  const palette = [0x4caf50, 0x2196f3, 0xff9800, 0xe91e63, 0x9c27b0, 0x00bcd4];
  return palette[index % palette.length];
}

function categoryColor(category: string): number {
  const map: Record<string, number> = {
    furniture: 0x6d5d49,
    architectural: 0x35547c,
    lighting: 0xffd166,
    equipment: 0x4a7c59,
    decoration: 0xa66f43,
    vehicle: 0x40a9ff,
    character: 0xff8a3d,
  };
  return map[category] ?? 0x586274;
}

function resolveObjectColor(
  category: string,
  name?: string,
  id?: string,
): number {
  const key = `${id ?? ''} ${name ?? ''} ${category ?? ''}`.toLowerCase();

  // Semantic overrides first (better readability for vehicle competitors).
  if (key.includes('car_red') || key.includes('red car') || key.includes(' red ')) {
    return 0xe53935;
  }
  if (key.includes('car_blue') || key.includes('blue car') || key.includes(' blue ')) {
    return 0x1e88e5;
  }
  if (key.includes('green')) {
    return 0x43a047;
  }
  if (key.includes('yellow')) {
    return 0xfdd835;
  }
  if (key.includes('orange')) {
    return 0xfb8c00;
  }
  if (key.includes('purple')) {
    return 0x8e24aa;
  }
  if (key.includes('black')) {
    return 0x424242;
  }
  if (key.includes('white')) {
    return 0xeceff1;
  }

  return categoryColor((category ?? '').toLowerCase());
}
