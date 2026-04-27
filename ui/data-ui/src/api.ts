import type { PricesResponse, StocksResponse } from "./types";

const API_BASE = import.meta.env.VITE_DATA_API_BASE ?? "/api/data";

interface StockParams {
  class_code?: string;
  search?: string;
  limit?: number;
  offset?: number;
}

interface PriceParams {
  figis?: string[];
  tickers?: string[];
  class_code?: string;
  start_date?: string;
  end_date?: string;
  interval?: string;
  is_complete?: boolean;
}

export async function getStocks(params: StockParams): Promise<StocksResponse> {
  return request<StocksResponse>("/stocks", params);
}

export async function getPrices(params: PriceParams): Promise<PricesResponse> {
  return request<PricesResponse>("/prices", params);
}

async function request<T>(path: string, params: StockParams | PriceParams): Promise<T> {
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
