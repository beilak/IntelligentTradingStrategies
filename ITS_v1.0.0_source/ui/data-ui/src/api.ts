import type {
  CurrenciesResponse,
  CustomGoldBarsResponse,
  DividendsResponse,
  PricesResponse,
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

interface DividendParams {
  figis?: string[];
  tickers?: string[];
  class_code?: string;
  start_date?: string;
  end_date?: string;
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

export async function getDividends(params: DividendParams): Promise<DividendsResponse> {
  return request<DividendsResponse>("/dividends", params);
}

async function request<T>(
  path: string,
  params: StockParams | CurrencyParams | PriceParams | CustomGoldBarParams | DividendParams,
): Promise<T> {
  const url = new URL(`${API_BASE}${path}`, window.location.origin);
  appendParams(url, params as Record<string, unknown>);

  const response = await fetch(url);
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
