import type {
  CurrenciesResponse,
  CustomGoldBarsResponse,
  DividendsResponse,
  MonteCarloDriftMode,
  MonteCarloResponse,
  PricesResponse,
  RssItemsResponse,
  RssLoadResponse,
  RssSourcesResponse,
  StocksResponse,
} from "./types";

const API_BASE = import.meta.env.VITE_DATA_API_BASE ?? "/api/data";

interface StockParams {
  class_code?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

interface CurrencyParams {
  class_code?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

interface PriceParams {
  figis?: string[];
  tickers?: string[];
  class_code?: string;
  instrument_type?: "stocks" | "currencies";
  start_date?: string;
  end_date?: string;
  interval?: string;
  is_complete?: boolean;
}

interface CustomGoldBarParams extends PriceParams {
  count?: number;
  bar_type?: string;
  gold_ticker?: string;
  gold_class_code?: string;
}

interface MonteCarloParams extends PriceParams {
  train_until_date: string;
  simulation_end_date: string;
  path_count?: number;
  seed?: number | null;
  volatility_scale?: number;
  drift_mode?: MonteCarloDriftMode;
}

interface DividendParams {
  figis?: string[];
  tickers?: string[];
  class_code?: string;
  start_date?: string;
  end_date?: string;
}

interface RssParams {
  pub_date_from?: string;
  pub_date_to?: string;
  title?: string;
  text?: string;
  source?: string;
  limit?: number;
  offset?: number;
}

export async function getStocks(params: StockParams): Promise<StocksResponse> {
  return request<StocksResponse>("/stocks", params);
}

export async function getCurrencies(params: CurrencyParams): Promise<CurrenciesResponse> {
  return request<CurrenciesResponse>("/currencies", params);
}

export async function getPrices(params: PriceParams): Promise<PricesResponse> {
  return request<PricesResponse>("/prices", params);
}

export async function getCustomGoldBars(params: CustomGoldBarParams): Promise<CustomGoldBarsResponse> {
  return request<CustomGoldBarsResponse>("/custom-gold-bars", params);
}

export async function getMonteCarlo(params: MonteCarloParams): Promise<MonteCarloResponse> {
  return request<MonteCarloResponse>("/monte-carlo", params);
}

export async function getDividends(params: DividendParams): Promise<DividendsResponse> {
  return request<DividendsResponse>("/dividends", params);
}

export async function getRssItems(params: RssParams): Promise<RssItemsResponse> {
  return request<RssItemsResponse>("/rss", params);
}

export async function getRssSources(): Promise<RssSourcesResponse> {
  return request<RssSourcesResponse>("/rss/sources", {});
}

export async function loadRssItems(): Promise<RssLoadResponse> {
  return post<RssLoadResponse>("/rss/load");
}

async function request<T>(path: string, params: object): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  appendParams(url, params as Record<string, unknown>);

  const response = await fetch(url);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? response.statusText);
  }

  return response.json() as Promise<T>;
}

async function post<T>(path: string): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);

  const response = await fetch(url, { method: "POST" });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? response.statusText);
  }

  return response.json() as Promise<T>;
}

function appendParams(url: URL, params: Record<string, unknown>) {
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === "") {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((item) => url.searchParams.append(key, String(item)));
      return;
    }

    url.searchParams.set(key, String(value));
  });
}
