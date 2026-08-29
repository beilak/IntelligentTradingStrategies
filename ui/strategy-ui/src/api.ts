import type {
  BacktestResult,
  BacktestRun,
  BacktestSavedTest,
  BacktestSettings,
  CpcvResult,
  CpcvSavedTest,
  CpcvSettings,
  ModelDetail,
  RegistryResponse,
  RiskModelDefinition,
  RiskModelResult,
  RiskModelSavedTest,
  RiskModelSettings,
  TradingStrategyListItem,
  TradingStrategyProductionState,
  StrategyComparisonResult,
  WalkForwardResult,
  WalkForwardSavedTest,
  WalkForwardSettings,
} from "./types";

const API_BASE = import.meta.env.VITE_STRATEGY_API_BASE ?? "/api/strategies";
const ACCESS_TOKEN_KEY = "its-auth-access-token";
const REFRESH_TOKEN_KEY = "its-auth-refresh-token";

export async function getRegistry(): Promise<RegistryResponse> {
  return request<RegistryResponse>("/registry");
}

export async function getLatestStrategyComparison(): Promise<StrategyComparisonResult> {
  return request<StrategyComparisonResult>("/comparison/latest");
}

export async function getModelDetail(modelName: string): Promise<ModelDetail> {
  return request<ModelDetail>(`/models/${encodeURIComponent(modelName)}`);
}

export async function getTradingStrategyDetail(strategyName: string): Promise<ModelDetail> {
  return request<ModelDetail>(`/trading-strategies/${encodeURIComponent(strategyName)}`);
}

export async function listTradingStrategies(): Promise<{ items: TradingStrategyListItem[] }> {
  return request<{ items: TradingStrategyListItem[] }>("/trading-strategies");
}

export async function setTradingStrategyProdReady(
  strategyName: string,
  payload: { is_prod_ready: boolean; comment: string | null },
): Promise<{ item: TradingStrategyProductionState }> {
  return request<{ item: TradingStrategyProductionState }>(
    `/trading-strategies/${encodeURIComponent(strategyName)}/prod-ready`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

export async function listCpcvTests(modelName: string): Promise<{ items: CpcvSavedTest[] }> {
  return request<{ items: CpcvSavedTest[] }>(`/models/${encodeURIComponent(modelName)}/cpcv/tests`);
}

export async function getCpcvTest(modelName: string, testName: string): Promise<CpcvResult> {
  return request<CpcvResult>(
    `/models/${encodeURIComponent(modelName)}/cpcv/tests/${encodeURIComponent(testName)}`,
  );
}

export async function runCpcvTest(modelName: string, settings: CpcvSettings): Promise<CpcvResult> {
  return request<CpcvResult>(`/models/${encodeURIComponent(modelName)}/cpcv/run`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export async function listWalkForwardTests(modelName: string): Promise<{ items: WalkForwardSavedTest[] }> {
  return request<{ items: WalkForwardSavedTest[] }>(
    `/models/${encodeURIComponent(modelName)}/walk-forward/tests`,
  );
}

export async function getWalkForwardTest(modelName: string, testName: string): Promise<WalkForwardResult> {
  return request<WalkForwardResult>(
    `/models/${encodeURIComponent(modelName)}/walk-forward/tests/${encodeURIComponent(testName)}`,
  );
}

export async function runWalkForwardTest(
  modelName: string,
  settings: WalkForwardSettings,
): Promise<WalkForwardResult> {
  return request<WalkForwardResult>(`/models/${encodeURIComponent(modelName)}/walk-forward/run`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export async function listBacktestTests(modelName: string): Promise<{ items: BacktestSavedTest[] }> {
  return request<{ items: BacktestSavedTest[] }>(
    `/models/${encodeURIComponent(modelName)}/backtest/tests`,
  );
}

export async function getBacktestTest(modelName: string, testName: string): Promise<BacktestResult> {
  return request<BacktestResult>(
    `/models/${encodeURIComponent(modelName)}/backtest/tests/${encodeURIComponent(testName)}`,
  );
}

export async function runBacktestTest(
  modelName: string,
  settings: BacktestSettings,
): Promise<BacktestResult> {
  return request<BacktestResult>(`/models/${encodeURIComponent(modelName)}/backtest/run`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export async function startBacktestRun(
  modelName: string,
  settings: BacktestSettings,
): Promise<BacktestRun> {
  return request<BacktestRun>(`/models/${encodeURIComponent(modelName)}/backtest/runs`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export async function getBacktestRun(modelName: string, runId: string): Promise<BacktestRun> {
  return request<BacktestRun>(
    `/models/${encodeURIComponent(modelName)}/backtest/runs/${encodeURIComponent(runId)}`,
  );
}

export async function listAvailableRiskModels(modelName: string): Promise<{ items: RiskModelDefinition[] }> {
  return request<{ items: RiskModelDefinition[] }>(
    `/models/${encodeURIComponent(modelName)}/risk-models/available`,
  );
}

export async function listRiskModelTests(
  modelName: string,
  riskModel: string,
): Promise<{ items: RiskModelSavedTest[] }> {
  return request<{ items: RiskModelSavedTest[] }>(
    `/models/${encodeURIComponent(modelName)}/risk-models/${encodeURIComponent(riskModel)}/tests`,
  );
}

export async function getRiskModelTest(
  modelName: string,
  riskModel: string,
  testName: string,
): Promise<RiskModelResult> {
  return request<RiskModelResult>(
    `/models/${encodeURIComponent(modelName)}/risk-models/${encodeURIComponent(riskModel)}/tests/${encodeURIComponent(testName)}`,
  );
}

export async function runRiskModelTest(
  modelName: string,
  riskModel: string,
  settings: RiskModelSettings,
): Promise<RiskModelResult> {
  return request<RiskModelResult>(
    `/models/${encodeURIComponent(modelName)}/risk-models/${encodeURIComponent(riskModel)}/run`,
    {
      method: "POST",
      body: JSON.stringify(settings),
    },
  );
}

export async function listTradingStrategyBacktestTests(
  strategyName: string,
): Promise<{ items: BacktestSavedTest[] }> {
  return request<{ items: BacktestSavedTest[] }>(
    `/trading-strategies/${encodeURIComponent(strategyName)}/backtest/tests`,
  );
}

export async function getTradingStrategyBacktestTest(
  strategyName: string,
  testName: string,
): Promise<BacktestResult> {
  return request<BacktestResult>(
    `/trading-strategies/${encodeURIComponent(strategyName)}/backtest/tests/${encodeURIComponent(testName)}`,
  );
}

export async function runTradingStrategyBacktestTest(
  strategyName: string,
  settings: BacktestSettings,
): Promise<BacktestResult> {
  return request<BacktestResult>(`/trading-strategies/${encodeURIComponent(strategyName)}/backtest/run`, {
    method: "POST",
    body: JSON.stringify(settings),
  });
}

export async function startTradingStrategyBacktestRun(
  strategyName: string,
  settings: BacktestSettings,
): Promise<BacktestRun> {
  return request<BacktestRun>(
    `/trading-strategies/${encodeURIComponent(strategyName)}/backtest/runs`,
    { method: "POST", body: JSON.stringify(settings) },
  );
}

export async function getTradingStrategyBacktestRun(
  strategyName: string,
  runId: string,
): Promise<BacktestRun> {
  return request<BacktestRun>(
    `/trading-strategies/${encodeURIComponent(strategyName)}/backtest/runs/${encodeURIComponent(runId)}`,
  );
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const auth = await authHeaders();
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...auth, ...init.headers },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(apiErrorMessage(payload?.detail, response.statusText));
  }
  return response.json() as Promise<T>;
}

function apiErrorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail.trim();
  if (!detail || typeof detail !== "object") return fallback;

  if (Array.isArray(detail)) {
    const validationErrors = detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const error = item as { loc?: unknown; msg?: unknown };
        const location = Array.isArray(error.loc) ? error.loc.join(".") : "";
        const message = typeof error.msg === "string" ? error.msg : JSON.stringify(item);
        return location ? `${location}: ${message}` : message;
      })
      .filter(Boolean);
    return validationErrors.length ? validationErrors.join("; ") : fallback;
  }

  const value = detail as {
    message?: unknown;
    error?: unknown;
    required_permissions?: unknown;
    required_roles?: unknown;
  };
  const message =
    typeof value.message === "string" && value.message.trim()
      ? value.message.trim()
      : typeof value.error === "string" && value.error.trim()
        ? value.error.trim()
        : fallback;
  const requiredPermissions = stringList(value.required_permissions);
  const requiredRoles = stringList(value.required_roles);
  const requirements = [
    requiredPermissions.length ? `Требуются права: ${requiredPermissions.join(", ")}.` : "",
    requiredRoles.length ? `Требуются роли: ${requiredRoles.join(", ")}.` : "",
  ].filter(Boolean);
  return requirements.length ? `${message} ${requirements.join(" ")}` : message;
}

function stringList(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string" && Boolean(item))
    : [];
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
