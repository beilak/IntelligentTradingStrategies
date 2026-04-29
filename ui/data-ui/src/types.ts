export type Locale = "ru" | "en";

export interface Stock {
  figi: string;
  ticker: string;
  uid?: string | null;
  isin?: string | null;
  name: string;
  class_code: string;
  currency: string;
  exchange: string;
  sector?: string | null;
  country_of_risk?: string | null;
  country_of_risk_name?: string | null;
  share_type?: string | null;
  lot?: number | null;
  trading_status?: string | null;
  real_exchange?: string | null;
  buy_available_flag?: boolean | null;
  sell_available_flag?: boolean | null;
  api_trade_available_flag?: boolean | null;
  short_enabled_flag?: boolean | null;
  for_qual_investor_flag?: boolean | null;
}

export interface Currency {
  figi: string;
  ticker: string;
  uid?: string | null;
  position_uid?: string | null;
  iso_currency_name?: string | null;
  name: string;
  class_code: string;
  currency: string;
  exchange: string;
  country_of_risk?: string | null;
  country_of_risk_name?: string | null;
  lot?: number | null;
  trading_status?: string | null;
  real_exchange?: string | null;
  buy_available_flag?: boolean | null;
  sell_available_flag?: boolean | null;
  api_trade_available_flag?: boolean | null;
  for_qual_investor_flag?: boolean | null;
  weekend_flag?: boolean | null;
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

export interface CurrenciesResponse {
  items: Currency[];
  total: number;
  limit: number;
  offset: number;
  filters: Pick<StockFilters, "class_codes" | "exchanges" | "countries" | "intervals">;
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

export interface Dividend {
  dividend_net: number;
  payment_date: string;
  declared_date: string | null;
  last_buy_date: string | null;
  dividend_type: string;
  record_date: string | null;
  regularity: string | null;
  close_price: number | null;
  yield_value: number | null;
  created_at: string | null;
  figi: string;
  ticker: string | null;
}

export interface DividendSummary {
  ticker: string;
  figi: string;
  total_net: number | null;
  count: number;
  last_payment: string | null;
}

export interface DividendsResponse {
  items: Dividend[];
  meta: {
    figis: string[];
    tickers: string[];
    start_date: string;
    end_date: string;
  };
  summary: DividendSummary[];
}
