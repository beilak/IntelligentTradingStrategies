import type {
  AccountOverview,
  AccountsResponse,
  ExecutionStrategiesResponse,
  InstrumentsResponse,
  LastPriceResponse,
  OrderTicket,
  PnlReport,
  PricesResponse,
  StrategyExecutionRequest,
  StrategyExecutionResult,
  StrategyRunRequest,
  StrategyRunResult,
  StopOrderTicket,
  StubResponse,
  User,
} from "./types";

const API_BASE = import.meta.env.VITE_EXECUTION_API_BASE ?? "/api/execution";
const DATA_API_BASE = import.meta.env.VITE_DATA_API_BASE ?? "/api/data";
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

export async function getPnlReport(
  accountId: string,
  params: { from_date: string; to_date: string; strategy_name?: string | null },
): Promise<PnlReport> {
  return request<PnlReport>(
    `/accounts/${encodeURIComponent(accountId)}/pnl-report`,
    params,
  );
}

export async function getExecutionStrategies(
  accountId: string,
): Promise<ExecutionStrategiesResponse> {
  return request<ExecutionStrategiesResponse>(
    `/accounts/${encodeURIComponent(accountId)}/strategies`,
  );
}

export async function assignExecutionStrategy(
  accountId: string,
  strategyName: string,
  payload: { comment: string | null },
): Promise<{ item: ExecutionStrategiesResponse["items"][number] }> {
  return put<{ item: ExecutionStrategiesResponse["items"][number] }>(
    `/accounts/${encodeURIComponent(accountId)}/strategies/${encodeURIComponent(strategyName)}`,
    payload,
  );
}

export async function unassignExecutionStrategy(
  accountId: string,
  strategyName: string,
): Promise<{ status: string }> {
  return deleteRequest<{ status: string }>(
    `/accounts/${encodeURIComponent(accountId)}/strategies/${encodeURIComponent(strategyName)}`,
  );
}

export async function runExecutionStrategy(
  accountId: string,
  strategyName: string,
  payload: StrategyRunRequest,
): Promise<StrategyRunResult> {
  return post<StrategyRunResult>(
    `/accounts/${encodeURIComponent(accountId)}/strategies/${encodeURIComponent(strategyName)}/runs`,
    payload,
  );
}

export async function executeExecutionStrategy(
  accountId: string,
  strategyName: string,
  payload: StrategyExecutionRequest,
): Promise<StrategyExecutionResult> {
  return post<StrategyExecutionResult>(
    `/accounts/${encodeURIComponent(accountId)}/strategies/${encodeURIComponent(strategyName)}/executions`,
    payload,
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

export async function getLastPrice(params: {
  instrument_id?: string | null;
  figi?: string | null;
}): Promise<LastPriceResponse> {
  return request<LastPriceResponse>("/market-data/last-price", params);
}

export async function getTradableInstruments(params: {
  search?: string;
  instrument_types?: string[];
  class_code?: string;
  exchange?: string;
  currency?: string;
  api_trade_available?: boolean;
  limit?: number;
  offset?: number;
}): Promise<InstrumentsResponse> {
  return requestFrom<InstrumentsResponse>(DATA_API_BASE, "/instruments", params);
}

export async function getPrices(params: {
  figis?: string[];
  tickers?: string[];
  class_code?: string | null;
  instrument_type?: string;
  start_date?: string;
  end_date?: string;
  interval?: string;
  is_complete?: boolean;
}): Promise<PricesResponse> {
  return requestFrom<PricesResponse>(DATA_API_BASE, "/prices", params);
}

export async function accessTokenForWebSocket(): Promise<string | null> {
  return accessTokenForRequest();
}

export function clearAuthTokens() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

async function request<T>(path: string, params?: Record<string, unknown>): Promise<T> {
  return requestFrom<T>(API_BASE, path, params);
}

async function requestFrom<T>(
  baseUrl: string,
  path: string,
  params?: Record<string, unknown>,
): Promise<T> {
  const url = new URL(`${baseUrl}${path}`, window.location.origin);
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

async function put<T>(path: string, payload: unknown): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);

  const response = await fetch(url, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
      ...(await authHeaders()),
    },
    body: JSON.stringify(payload),
  });
  return handleResponse<T>(response);
}

async function deleteRequest<T>(path: string): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);

  const response = await fetch(url, {
    method: "DELETE",
    headers: await authHeaders(),
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
    throw new Error(apiErrorMessage(payload?.detail, response.statusText));
  }
  return response.json() as Promise<T>;
}

function apiErrorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail) return detail;
  if (detail && typeof detail === "object") {
    const value = detail as { message?: unknown; blocking_reasons?: unknown };
    const message = typeof value.message === "string" ? value.message : fallback;
    const reasons = Array.isArray(value.blocking_reasons)
      ? value.blocking_reasons.filter((item): item is string => typeof item === "string")
      : [];
    return reasons.length ? `${message} ${reasons.join(" ")}` : message;
  }
  return fallback;
}

function appendParams(url: URL, params: Record<string, unknown>) {
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") return;
    if (Array.isArray(value)) {
      value.forEach((item) => url.searchParams.append(key, String(item)));
      return;
    }
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
