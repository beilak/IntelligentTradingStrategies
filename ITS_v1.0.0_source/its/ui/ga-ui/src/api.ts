import type { AlphabetResponse, GARun, GARunSettings, GARunSummary } from "./types";

const API_BASE = import.meta.env.VITE_GA_API_BASE ?? "/api/ga";

export async function getAlphabets(): Promise<AlphabetResponse> {
  return request<AlphabetResponse>("/alphabets");
}

export async function listRuns(): Promise<{ items: GARunSummary[] }> {
  return request<{ items: GARunSummary[] }>("/runs");
}

export async function getRun(runId: string): Promise<GARun> {
  return request<GARun>(`/runs/${encodeURIComponent(runId)}`);
}

export async function startRun(settings: GARunSettings): Promise<GARun> {
  return request<GARun>("/runs", {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json" },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}
