export const ACCESS_TOKEN_KEY = "its-auth-access-token";
export const REFRESH_TOKEN_KEY = "its-auth-refresh-token";

const API_BASE = "/api/tech";
const EVENT_LOG_API_BASE = "/api/event-log";

export interface EventLogEntry {
  id: number;
  date_time: string;
  service: string;
  user: string;
  http_action: string;
  ip_address: string;
  path: string;
  header: Record<string, string>;
  body: string | null;
}

export interface EventLogResponse {
  columns: string[];
  items: EventLogEntry[];
  total: number;
  limit: number;
  offset: number;
}

export interface EventLogFilterOptions {
  services: string[];
  users: string[];
}

export interface EventLogFilters {
  id?: string;
  date_time_from?: string;
  date_time_to?: string;
  service?: string;
  user?: string;
  http_action?: string;
  ip_address?: string;
  path?: string;
  header?: string;
  body?: string;
  limit?: number;
  offset?: number;
}

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_verified: boolean;
  role_version: number;
  created_at: string;
  last_login_at: string | null;
}

export interface AuthResponse {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function saveAuthSession(response: AuthResponse): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, response.access_token);
  localStorage.setItem(REFRESH_TOKEN_KEY, response.refresh_token);
}

export function clearAuthSession(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function readError(response: Response): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    return "Request failed";
  }
  return "Request failed";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  return (await response.json()) as T;
}

async function authRequest<T>(path: string, token: string): Promise<T> {
  return request<T>(path, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
}

async function authorizedAccessToken(): Promise<string> {
  const accessToken = getAccessToken();
  if (accessToken) return accessToken;
  const refreshed = await refreshSession();
  return refreshed.access_token;
}

async function eventLogRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = await authorizedAccessToken();
  const response = await fetch(`${EVENT_LOG_API_BASE}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      ...init.headers,
    },
  });

  if (response.status === 401) {
    const refreshed = await refreshSession();
    const retry = await fetch(`${EVENT_LOG_API_BASE}${path}`, {
      ...init,
      headers: {
        Authorization: `Bearer ${refreshed.access_token}`,
        ...init.headers,
      },
    });
    if (!retry.ok) {
      throw new ApiError(await readError(retry), retry.status);
    }
    return (await retry.json()) as T;
  }

  if (!response.ok) {
    throw new ApiError(await readError(response), response.status);
  }
  return (await response.json()) as T;
}

export async function register(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  return request<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export async function refreshSession(): Promise<AuthResponse> {
  const refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
  if (!refreshToken) {
    throw new ApiError("Refresh token is missing", 401);
  }
  const response = await request<AuthResponse>("/auth/refresh", {
    method: "POST",
    body: JSON.stringify({ refresh_token: refreshToken }),
  });
  saveAuthSession(response);
  return response;
}

export async function fetchCurrentUser(): Promise<User> {
  const accessToken = getAccessToken();
  if (!accessToken) {
    const refreshed = await refreshSession();
    return refreshed.user;
  }

  try {
    return await authRequest<User>("/auth/me", accessToken);
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      const refreshed = await refreshSession();
      return refreshed.user;
    }
    throw error;
  }
}

export async function logout(): Promise<void> {
  const accessToken = getAccessToken();
  if (accessToken) {
    await authRequest<{ status: string }>("/auth/logout", accessToken).catch(() => undefined);
  }
  clearAuthSession();
}

export async function fetchEventLogs(filters: EventLogFilters): Promise<EventLogResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    if (value !== undefined && value !== null && String(value).trim() !== "") {
      params.set(key, String(value));
    }
  });
  const query = params.toString();
  return eventLogRequest<EventLogResponse>(`/events${query ? `?${query}` : ""}`);
}

export async function fetchEventLogFilterOptions(): Promise<EventLogFilterOptions> {
  return eventLogRequest<EventLogFilterOptions>("/events/filter-options");
}
