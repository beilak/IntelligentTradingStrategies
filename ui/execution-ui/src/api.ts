import type {
  AccountOverview,
  AccountsResponse,
  OrderTicket,
  StopOrderTicket,
  StubResponse,
  User,
} from "./types";

const API_BASE = import.meta.env.VITE_EXECUTION_API_BASE ?? "/api/execution";
const ACCESS_TOKEN_KEY = "its-auth-access-token";
const REFRESH_TOKEN_KEY = "its-auth-refresh-token";

export async function getCurrentUser(): Promise<User | null> {
  const token = await accessTokenForRequest();
  if (!token) return null;

  const response = await fetch("/api/tech/auth/me", {
    headers: { Authorization: `Bearer ${token}` },
  }).catch(() => null);
  if (!response?.ok) return null;
  return (await response.json()) as User;
}

export async function getAccounts(): Promise<AccountsResponse> {
  return request<AccountsResponse>("/accounts");
}

export async function getOverview(
  accountId: string,
  operationsDays = 30,
): Promise<AccountOverview> {
  return request<AccountOverview>(
    `/accounts/${encodeURIComponent(accountId)}/overview`,
    { operations_days: operationsDays },
  );
}

export async function createOrder(
  accountId: string,
  ticket: OrderTicket,
): Promise<StubResponse> {
  return post<StubResponse>(`/accounts/${encodeURIComponent(accountId)}/orders`, ticket);
}

export async function createStopOrder(
  accountId: string,
  ticket: StopOrderTicket,
): Promise<StubResponse> {
  return post<StubResponse>(`/accounts/${encodeURIComponent(accountId)}/stop-orders`, ticket);
}

export function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function request<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  appendParams(url, params ?? {});

  const response = await fetch(url, { headers: await authHeaders() });
  return handleResponse<T>(response);
}

async function post<T>(path: string, payload: unknown): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);

  const response = await fetch(url, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<T>(response);
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (response.status === 401) {
    clearAuthTokens();
    window.location.replace("/tech/auth/?returnTo=/execution/");
    throw new Error("Unauthorized");
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? response.statusText);
  }
  return response.json() as Promise<T>;
}

function appendParams(url: URL, params: Record<string, unknown>) {
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    url.searchParams.set(key, String(value));
  });
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
    const payload = JSON.parse(atob(token.split(".")[1])) as { exp?: number };
    if (!payload.exp) return true;
    return payload.exp * 1000 - Date.now() < 30_000;
  } catch {
    return true;
  }
}
