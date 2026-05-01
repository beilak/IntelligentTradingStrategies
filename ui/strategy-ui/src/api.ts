import type {
  BacktestResult,
  BacktestSavedTest,
  BacktestSettings,
  CpcvResult,
  CpcvSavedTest,
  CpcvSettings,
  ModelDetail,
  RegistryResponse,
  StrategyComparisonResult,
  WalkForwardResult,
  WalkForwardSavedTest,
  WalkForwardSettings,
} from "./types";

const API_BASE = import.meta.env.VITE_STRATEGY_API_BASE ?? "/api/strategies";

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
