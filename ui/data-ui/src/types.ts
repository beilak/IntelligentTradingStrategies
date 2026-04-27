export type Locale = "ru" | "en";

export interface Stock {
  figi: string;
  ticker: string;
  name: string;
  class_code: string;
  currency: string;
  exchange: string;
  sector?: string | null;
  country_of_risk?: string | null;
  share_type?: string | null;
}

export interface Candle {
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number | null;
  time: string;
  is_complete?: boolean;
  figi: string;
  ticker?: string | null;
}

export interface StockFilters {
  class_codes: string[];
  exchanges: string[];
  sectors: string[];
  countries: string[];
  intervals: string[];
}

export interface StocksResponse {
  items: Stock[];
  total: number;
  limit: number;
  offset: number;
  filters: StockFilters;
}

export interface PriceSummary {
  ticker: string;
  figi: string;
  last_close: number | null;
  change_pct: number | null;
  candles: number;
  from: string | null;
  to: string | null;
}

export interface PricesResponse {
  items: Candle[];
  meta: {
    figis: string[];
    tickers: string[];
    start_date: string;
    end_date: string;
    interval: string;
    is_complete: boolean;
  };
  summary: PriceSummary[];
}
