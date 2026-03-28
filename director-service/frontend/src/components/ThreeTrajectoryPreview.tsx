import { useEffect, useRef } from 'react';
import * as THREE from 'three';
import type { SceneSummary, ShotTrajectory } from '../types';

interface Props {
  scene: SceneSummary;
  trajectories: ShotTrajectory[];
  currentCameraPosition: [number, number, number] | null;
  currentLookAtPosition: [number, number, number] | null;
  currentFov: number;
  currentShotId?: string | null;
  viewMode?: 'camera' | 'observer';
  width?: number;
  height?: number;
}

export default function ThreeTrajectoryPreview({
  scene,
  trajectories,
  currentCameraPosition,
  currentLookAtPosition,
  currentFov,
  currentShotId,
  viewMode = 'camera',
  width = 560,
  height = 230,
}: Props) {
  const mountRef = useRef<HTMLDivElement>(null);
  const runtimeRef = useRef<PreviewRuntime | null>(null);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) {
      return;
    }

    const runtime = createRuntime(mount, width, height);
    runtimeRef.current = runtime;
    return () => {
      runtime.dispose();
      runtimeRef.current = null;
    };
  }, [width, height]);

  useEffect(() => {
    const runtime = runtimeRef.current;
    if (!runtime) {
      return;
    }

    updateSceneContent(runtime, scene, trajectories, currentShotId);
    updateCameraPose(runtime, currentCameraPosition, currentLookAtPosition, currentFov, scene);
    runtime.render(viewMode);
  }, [scene, trajectories, currentCameraPosition, currentLookAtPosition, currentFov, currentShotId, viewMode]);

  return <div ref={mountRef} style={{ width, height }} className="preview-3d-shell" />;
}

interface PreviewRuntime {
  renderer: THREE.WebGLRenderer;
  worldScene: THREE.Scene;
  playbackCamera: THREE.PerspectiveCamera;
  observerCamera: THREE.PerspectiveCamera;
  root: THREE.Group;
  playbackMarker: THREE.Group;
  lookLine: THREE.Line;
  mount: HTMLDivElement;
  width: number;
  height: number;
  dispose: () => void;
  render: (viewMode: 'camera' | 'observer') => void;
}

function createRuntime(mount: HTMLDivElement, width: number, height: number): PreviewRuntime {
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

  const ambient = new THREE.AmbientLight(0xffffff, 1.2);
  worldScene.add(ambient);

  const keyLight = new THREE.DirectionalLight(0xdde7ff, 1.8);
  keyLight.position.set(6, 8, 4);
  worldScene.add(keyLight);

  const rimLight = new THREE.DirectionalLight(0x7cc7ff, 0.7);
  rimLight.position.set(-4, 3, -6);
  worldScene.add(rimLight);

  const observerCamera = new THREE.PerspectiveCamera(42, width / height, 0.1, 100);
  observerCamera.position.set(sceneCenterX(10), 8, 11);
  observerCamera.lookAt(0, 1.2, 0);

  const playbackCamera = new THREE.PerspectiveCamera(60, width / height, 0.1, 100);
  const playbackMarker = createPlaybackMarker();
  root.add(playbackMarker);

  const lookLine = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]),
    new THREE.LineDashedMaterial({ color: 0xffffff, dashSize: 0.18, gapSize: 0.12, transparent: true, opacity: 0.85 }),
  );
  root.add(lookLine);

  const render = (viewMode: 'camera' | 'observer') => {
    const showObserverOverlays = viewMode === 'observer';
    playbackMarker.visible = showObserverOverlays;
    lookLine.visible = showObserverOverlays;
    renderer.render(worldScene, viewMode === 'observer' ? observerCamera : playbackCamera);
  };

  return {
    renderer,
    worldScene,
    playbackCamera,
    observerCamera,
    root,
    playbackMarker,
    lookLine,
    mount,
    width,
    height,
    dispose: () => {
      renderer.dispose();
      mount.innerHTML = '';
    },
    render,
  };
}

function updateSceneContent(
  runtime: PreviewRuntime,
  scene: SceneSummary,
  trajectories: ShotTrajectory[],
  currentShotId?: string | null,
) {
  runtime.root.clear();
  runtime.root.add(runtime.playbackMarker);
  runtime.root.add(runtime.lookLine);

  const floorGeometry = new THREE.PlaneGeometry(scene.bounds.width, scene.bounds.length, 1, 1);
  const floorMaterial = new THREE.MeshStandardMaterial({
    color: 0x132033,
    roughness: 0.95,
    metalness: 0.05,
  });
  const floor = new THREE.Mesh(floorGeometry, floorMaterial);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(scene.bounds.width / 2, 0, scene.bounds.length / 2);
  runtime.root.add(floor);

  const roomEdges = new THREE.LineSegments(
    new THREE.EdgesGeometry(new THREE.BoxGeometry(scene.bounds.width, scene.bounds.height, scene.bounds.length)),
    new THREE.LineBasicMaterial({ color: 0x35547c, transparent: true, opacity: 0.65 }),
  );
  roomEdges.position.set(scene.bounds.width / 2, scene.bounds.height / 2, scene.bounds.length / 2);
  runtime.root.add(roomEdges);

  scene.objects.forEach((objectData) => {
    const displaySize = getDisplaySize(objectData.size, objectData.category);
    const geometry = new THREE.BoxGeometry(
      displaySize[0],
      displaySize[1],
      displaySize[2],
    );
    const material = new THREE.MeshStandardMaterial({
      color: categoryColor(objectData.category),
      roughness: 0.75,
      metalness: 0.12,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.set(objectData.position[0], objectData.position[1], objectData.position[2]);
    runtime.root.add(mesh);

    const edge = new THREE.LineSegments(
      new THREE.EdgesGeometry(geometry),
      new THREE.LineBasicMaterial({ color: 0xe6eefc, transparent: true, opacity: 0.35 }),
    );
    edge.position.copy(mesh.position);
    runtime.root.add(edge);
  });

  trajectories.forEach((trajectory, index) => {
    if (trajectory.sampled_points.length < 2) {
      return;
    }

    const isActive = currentShotId ? trajectory.shot_id === currentShotId : false;
    const points = trajectory.sampled_points.map((point) => new THREE.Vector3(point[0], point[1], point[2]));
    const geometry = new THREE.BufferGeometry().setFromPoints(points);
    const material = new THREE.LineBasicMaterial({
      color: shotColor(index),
      transparent: true,
      opacity: currentShotId ? (isActive ? 1 : 0.22) : 0.5,
    });
    const line = new THREE.Line(geometry, material);
    runtime.root.add(line);
  });

  const observerDistance = Math.max(scene.bounds.width, scene.bounds.length) * 1.5;
  runtime.observerCamera.position.set(
    scene.bounds.width / 2 + observerDistance * 0.65,
    Math.max(scene.bounds.height * 1.8, 5),
    scene.bounds.length / 2 + observerDistance * 0.85,
  );
  runtime.observerCamera.lookAt(scene.bounds.width / 2, scene.bounds.height * 0.35, scene.bounds.length / 2);
}

function updateCameraPose(
  runtime: PreviewRuntime,
  currentCameraPosition: [number, number, number] | null,
  currentLookAtPosition: [number, number, number] | null,
  currentFov: number,
  scene: SceneSummary,
) {
  const fallbackPosition: [number, number, number] = [
    scene.bounds.width * 0.5,
    Math.max(1.6, scene.bounds.height * 0.55),
    Math.max(scene.bounds.length * 0.85, 1.5),
  ];
  const fallbackLookAt: [number, number, number] = [
    scene.bounds.width * 0.5,
    Math.max(1, scene.bounds.height * 0.35),
    scene.bounds.length * 0.5,
  ];

  const position = currentCameraPosition ?? fallbackPosition;
  const lookAt = currentLookAtPosition ?? fallbackLookAt;

  runtime.playbackCamera.position.set(position[0], position[1], position[2]);
  runtime.playbackCamera.fov = currentFov > 1 ? currentFov : 60;
  runtime.playbackCamera.aspect = runtime.width / runtime.height;
  runtime.playbackCamera.updateProjectionMatrix();
  runtime.playbackCamera.lookAt(lookAt[0], lookAt[1], lookAt[2]);

  runtime.playbackMarker.position.set(position[0], position[1], position[2]);
  runtime.playbackMarker.lookAt(lookAt[0], lookAt[1], lookAt[2]);
  runtime.playbackMarker.visible = true;

  runtime.lookLine.geometry.dispose();
  runtime.lookLine.geometry = new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(position[0], position[1], position[2]),
    new THREE.Vector3(lookAt[0], lookAt[1], lookAt[2]),
  ]);
  const dashed = runtime.lookLine.material;
  if (dashed instanceof THREE.LineDashedMaterial) {
    runtime.lookLine.computeLineDistances();
  }
}

function createPlaybackMarker(): THREE.Group {
  const group = new THREE.Group();

  const body = new THREE.Mesh(
    new THREE.BoxGeometry(0.18, 0.12, 0.28),
    new THREE.MeshStandardMaterial({ color: 0xffffff, roughness: 0.35, metalness: 0.1 }),
  );
  group.add(body);

  const lens = new THREE.Mesh(
    new THREE.CylinderGeometry(0.035, 0.035, 0.14, 12),
    new THREE.MeshStandardMaterial({
      color: 0x58a6ff,
      roughness: 0.2,
      metalness: 0.35,
      transparent: true,
      opacity: 0.35,
    }),
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

function getDisplaySize(size: [number, number, number], category?: string): [number, number, number] {
  const scale = (category ?? '').toLowerCase() === 'vehicle' ? 0.65 : 1;
  return [
    Math.max(size[0] * scale, 0.08),
    Math.max(size[1] * scale, 0.08),
    Math.max(size[2] * scale, 0.08),
  ];
}

function categoryColor(category: string): number {
  const map: Record<string, number> = {
    furniture: 0x6d5d49,
    architectural: 0x35547c,
    lighting: 0xffd166,
    equipment: 0x4a7c59,
    decoration: 0xa66f43,
  };
  return map[category] ?? 0x586274;
}

function sceneCenterX(fallback: number): number {
  return fallback * 0.5;
}
