import type { AlphabetResponse, GARun, GARunSettings, GARunSummary } from "./types";

const API_BASE = import.meta.env.VITE_GA_API_BASE ?? "/api/ga";
const ACCESS_TOKEN_KEY = "its-auth-access-token";
const REFRESH_TOKEN_KEY = "its-auth-refresh-token";

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
  const auth = await authHeaders();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...auth, ...init.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

async function authHeaders(): Promise<Record<string, string>> {
  const token = await accessTokenForRequest();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function accessTokenForRequest(): Promise<string | null> {
  const accessToken = localStorage.getItem(ACCESS_TOKEN_KEY);
  if (accessToken && !tokenExpiresSoon(accessToken)) {
    return accessToken;
  }

  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) return null;

  const response = await fetch("/api/tech/auth/refresh", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refreshToken }),
  }).catch(() => null);
  if (!response?.ok) return null;

  const payload = (await response.json()) as {
    access_token: string;
    refresh_token: string;
  };
  localStorage.setItem(ACCESS_TOKEN_KEY, payload.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, payload.refresh_token);
  return payload.access_token;
}

function tokenExpiresSoon(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split(".")[1] ?? "")) as { exp?: number };
    return typeof payload.exp !== "number" || payload.exp * 1000 <= Date.now() + 30_000;
  } catch {
    return true;
  }
}
