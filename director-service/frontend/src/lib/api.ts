import type { SceneListItem, SceneSummary, GenerateResponse, RunSummary, LlmModelsResponse } from '../types';

const BASE = '/api';

export async function fetchScenes(): Promise<SceneListItem[]> {
  const res = await fetch(`${BASE}/scenes`);
  if (!res.ok) throw new Error(`Failed to fetch scenes: ${res.statusText}`);
  return res.json();
}

export async function fetchScene(sceneId: string): Promise<SceneSummary> {
  const res = await fetch(`${BASE}/scenes/${sceneId}`);
  if (!res.ok) throw new Error(`Failed to fetch scene: ${res.statusText}`);
  return res.json();
}

export async function generatePlan(sceneId: string, intent: string, llmModel: string): Promise<GenerateResponse> {
  const res = await fetch(`${BASE}/generate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scene_id: sceneId, intent, llm_model: llmModel }),
  });
  if (!res.ok) throw new Error(`Failed to generate plan: ${res.statusText}`);
  return res.json();
}

export async function fetchOutputs(): Promise<string[]> {
  const res = await fetch(`${BASE}/outputs`);
  if (!res.ok) throw new Error(`Failed to fetch outputs: ${res.statusText}`);
  return res.json();
}

export async function fetchRuns(): Promise<RunSummary[]> {
  const res = await fetch(`${BASE}/runs`);
  if (!res.ok) throw new Error(`Failed to fetch runs: ${res.statusText}`);
  return res.json();
}

export async function fetchRun(prefix: string): Promise<GenerateResponse> {
  const encodedPrefix = encodeURIComponent(prefix);
  const res = await fetch(`${BASE}/runs/${encodedPrefix}`);
  if (!res.ok) throw new Error(`Failed to fetch run bundle: ${res.statusText}`);
  return res.json();
}

export async function fetchLlmModels(): Promise<LlmModelsResponse> {
  const res = await fetch(`${BASE}/llm/models`);
  if (!res.ok) throw new Error(`Failed to fetch llm models: ${res.statusText}`);
  return res.json();
}
