import { useRef, useEffect } from 'react';
import type { SceneSummary, ShotTrajectory } from '../types';

const SHOT_COLORS = [
  '#4CAF50', '#2196F3', '#FF9800', '#E91E63', '#9C27B0', '#00BCD4',
];

interface Props {
  scene: SceneSummary;
  trajectories?: ShotTrajectory[];
  selectedShotId?: string | null;
  currentCameraPosition?: [number, number, number] | null;
  currentLookAtPosition?: [number, number, number] | null;
  currentShotId?: string | null;
  objectPositionOverrides?: Record<string, [number, number, number]>;
  objectVisibilityOverrides?: Record<string, boolean>;
  highlightedObjectIds?: string[];
  width?: number;
  height?: number;
}

export default function TopDownCanvas({
  scene,
  trajectories,
  selectedShotId,
  currentCameraPosition,
  currentLookAtPosition,
  currentShotId,
  objectPositionOverrides,
  objectVisibilityOverrides,
  highlightedObjectIds,
  width = 500,
  height = 400,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const W = canvas.width;
    const H = canvas.height;
    const pad = 40;

    // Map scene coords (X, Z) to canvas (x, y)
    const scaleX = (W - 2 * pad) / scene.bounds.width;
    const scaleZ = (H - 2 * pad) / scene.bounds.length;
    const scale = Math.min(scaleX, scaleZ);
    const offsetX = pad + (W - 2 * pad - scene.bounds.width * scale) / 2;
    const offsetZ = pad + (H - 2 * pad - scene.bounds.length * scale) / 2;

    const toCanvas = (x: number, z: number): [number, number] => [
      offsetX + x * scale,
      offsetZ + z * scale,
    ];

    // Clear
    ctx.fillStyle = '#1a1a2e';
    ctx.fillRect(0, 0, W, H);

    // Draw room bounds
    const [rx, rz] = toCanvas(0, 0);
    ctx.strokeStyle = '#444';
    ctx.lineWidth = 2;
    ctx.strokeRect(rx, rz, scene.bounds.width * scale, scene.bounds.length * scale);

    // Draw objects
    const highlighted = new Set(highlightedObjectIds ?? []);
    for (const obj of scene.objects) {
      const position = objectPositionOverrides?.[obj.id] ?? obj.position;
      const [cx, cz] = toCanvas(position[0], position[2]);
      const w = obj.size[0] * scale;
      const d = obj.size[2] * scale;

      const objectColor = resolveObjectColor(obj.category, obj.name, obj.id);
      ctx.fillStyle = objectColor;
      const visible = objectVisibilityOverrides?.[obj.id];
      ctx.globalAlpha = visible === false ? 0.24 : 0.72;
      ctx.fillRect(cx - w / 2, cz - d / 2, w, d);
      ctx.globalAlpha = 1.0;
      ctx.strokeStyle = highlighted.has(obj.id) ? '#58a6ff' : shadeHex(objectColor, -0.28);
      ctx.lineWidth = highlighted.has(obj.id) ? 2 : 1;
      ctx.strokeRect(cx - w / 2, cz - d / 2, w, d);

      if (highlighted.has(obj.id)) {
        ctx.strokeStyle = '#58a6ff';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 3]);
        ctx.strokeRect(cx - w / 2 - 3, cz - d / 2 - 3, w + 6, d + 6);
        ctx.setLineDash([]);
      }

      // Label
      ctx.fillStyle = '#ddd';
      ctx.font = '10px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(obj.id, cx, cz + d / 2 + 12);
    }

    // Draw trajectories
    if (trajectories) {
      trajectories.forEach((traj, idx) => {
        const color = SHOT_COLORS[idx % SHOT_COLORS.length];
        const isSelected = selectedShotId === traj.shot_id || currentShotId === traj.shot_id;
        const alpha = selectedShotId ? (isSelected ? 1.0 : 0.25) : 0.8;

        ctx.globalAlpha = alpha;
        ctx.strokeStyle = color;
        ctx.lineWidth = isSelected ? 3 : 2;

        // Draw path
        if (traj.sampled_points.length > 1) {
          ctx.beginPath();
          const [sx, sz] = toCanvas(traj.sampled_points[0][0], traj.sampled_points[0][2]);
          ctx.moveTo(sx, sz);
          for (let i = 1; i < traj.sampled_points.length; i++) {
            const [px, pz] = toCanvas(traj.sampled_points[i][0], traj.sampled_points[i][2]);
            ctx.lineTo(px, pz);
          }
          ctx.stroke();

          // Start marker
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(sx, sz, 5, 0, Math.PI * 2);
          ctx.fill();

          // End marker (arrow-like)
          const last = traj.sampled_points[traj.sampled_points.length - 1];
          const [ex, ez] = toCanvas(last[0], last[2]);
          ctx.beginPath();
          ctx.arc(ex, ez, 4, 0, Math.PI * 2);
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 1;
          ctx.stroke();
        }

        // Draw look_at target
        const [lx, lz] = toCanvas(traj.look_at_position[0], traj.look_at_position[2]);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        const mid = traj.sampled_points[Math.floor(traj.sampled_points.length / 2)];
        const [mx, mz] = toCanvas(mid[0], mid[2]);
        ctx.beginPath();
        ctx.moveTo(mx, mz);
        ctx.lineTo(lx, lz);
        ctx.stroke();
        ctx.setLineDash([]);

        // Look-at crosshair
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(lx - 5, lz);
        ctx.lineTo(lx + 5, lz);
        ctx.moveTo(lx, lz - 5);
        ctx.lineTo(lx, lz + 5);
        ctx.stroke();

        ctx.globalAlpha = 1.0;
      });
    }

    if (currentCameraPosition) {
      const [cx, cz] = toCanvas(currentCameraPosition[0], currentCameraPosition[2]);
      ctx.globalAlpha = 1;
      ctx.fillStyle = '#ffffff';
      ctx.beginPath();
      ctx.arc(cx, cz, 7, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#111';
      ctx.beginPath();
      ctx.arc(cx, cz, 3, 0, Math.PI * 2);
      ctx.fill();

      if (currentLookAtPosition) {
        const [lx, lz] = toCanvas(currentLookAtPosition[0], currentLookAtPosition[2]);
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(cx, cz);
        ctx.lineTo(lx, lz);
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }

    // Legend
    ctx.fillStyle = '#888';
    ctx.font = '10px monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`${scene.bounds.width}m x ${scene.bounds.length}m`, pad, H - 8);
  }, [
    scene,
    trajectories,
    selectedShotId,
    currentCameraPosition,
    currentLookAtPosition,
    currentShotId,
    objectPositionOverrides,
    objectVisibilityOverrides,
    highlightedObjectIds,
    width,
    height,
  ]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      style={{ border: '1px solid #333', borderRadius: 4, background: '#1a1a2e' }}
    />
  );
}

function getCategoryColor(category: string): string {
  const map: Record<string, string> = {
    furniture: '#5D4E37',
    architectural: '#3D5A80',
    lighting: '#FFD166',
    equipment: '#4A7C59',
    decoration: '#8B5E3C',
    vehicle: '#3FA7FF',
    character: '#FF8A3D',
  };
  return map[category] || '#666';
}

function resolveObjectColor(category: string, name?: string, id?: string): string {
  const key = `${id ?? ''} ${name ?? ''} ${category ?? ''}`.toLowerCase();

  if (key.includes('car_red') || key.includes('red car') || key.includes(' red ')) return '#E53935';
  if (key.includes('car_blue') || key.includes('blue car') || key.includes(' blue ')) return '#1E88E5';
  if (key.includes('green')) return '#43A047';
  if (key.includes('yellow')) return '#FDD835';
  if (key.includes('orange')) return '#FB8C00';
  if (key.includes('purple')) return '#8E24AA';
  if (key.includes('black')) return '#424242';
  if (key.includes('white')) return '#ECEFF1';

  return getCategoryColor((category ?? '').toLowerCase());
}

function shadeHex(hex: string, amount: number): string {
  const normalized = hex.startsWith('#') ? hex.slice(1) : hex;
  if (normalized.length !== 6) return hex;
  const clamp = (v: number) => Math.max(0, Math.min(255, v));
  const factor = 1 + amount;
  const r = clamp(Math.round(parseInt(normalized.slice(0, 2), 16) * factor));
  const g = clamp(Math.round(parseInt(normalized.slice(2, 4), 16) * factor));
  const b = clamp(Math.round(parseInt(normalized.slice(4, 6), 16) * factor));
  return `#${r.toString(16).padStart(2, '0')}${g.toString(16).padStart(2, '0')}${b.toString(16).padStart(2, '0')}`;
}
