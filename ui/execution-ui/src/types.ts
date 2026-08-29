export interface User {
  id: string;
  email: string;
  permissions: string[];
}

export interface MoneyAmount {
  currency?: string | null;
  units?: number | null;
  nano?: number | null;
  value?: number | null;
}

export interface QuotationAmount {
  units?: number | null;
  nano?: number | null;
  value?: number | null;
}

export interface AccountItem {
  id: string;
  name: string;
  broker_name?: string | null;
  type?: string | number | null;
  status?: string | number | null;
  access_level?: string | number | null;
  opened_date?: string | null;
  closed_date?: string | null;
  is_configured: boolean;
  is_available: boolean;
}

export interface AccountsResponse {
  items: AccountItem[];
  total: number;
  broker_accounts_total: number;
  configuration: {
    source: string;
    account_ids: string[];
  };
}

export interface AllocationItem {
  bucket: string;
  amount: MoneyAmount | null;
  value: number | null;
}

export interface PortfolioPosition {
  figi: string;
  instrument_type: string;
  quantity?: QuotationAmount | null;
  quantity_lots?: QuotationAmount | null;
  average_position_price?: MoneyAmount | null;
  current_price?: MoneyAmount | null;
  expected_yield?: QuotationAmount | null;
  daily_yield?: MoneyAmount | null;
  blocked?: boolean | null;
  blocked_lots?: QuotationAmount | null;
  instrument_uid?: string | null;
  position_uid?: string | null;
  ticker?: string | null;
}

export interface SecurityPosition {
  figi: string;
  balance: number;
  blocked: number;
  instrument_type?: string | null;
  ticker?: string | null;
  instrument_uid?: string | null;
  position_uid?: string | null;
  exchange_blocked?: boolean | null;
}

export interface PortfolioSection {
  positions?: PortfolioPosition[];
  total_amount_portfolio?: MoneyAmount | null;
  total_amount_shares?: MoneyAmount | null;
  total_amount_bonds?: MoneyAmount | null;
  total_amount_etf?: MoneyAmount | null;
  total_amount_currencies?: MoneyAmount | null;
  total_amount_futures?: MoneyAmount | null;
  total_amount_options?: MoneyAmount | null;
  expected_yield?: QuotationAmount | null;
  daily_yield?: MoneyAmount | null;
  daily_yield_relative?: QuotationAmount | null;
}

export interface PositionsSection {
  money?: MoneyAmount[];
  blocked?: MoneyAmount[];
  securities?: SecurityPosition[];
  limits_loading_in_progress?: boolean;
}

export interface OperationItem {
  id: string;
  currency?: string | null;
  payment?: MoneyAmount | null;
  price?: MoneyAmount | null;
  state?: string | number | null;
  quantity?: number | null;
  quantity_rest?: number | null;
  figi?: string | null;
  instrument_type?: string | null;
  date?: string | null;
  type?: string | null;
  operation_type?: string | number | null;
}

export interface OrderState {
  order_id: string;
  execution_report_status?: string | number | null;
  lots_requested?: number | null;
  lots_executed?: number | null;
  figi?: string | null;
  direction?: string | number | null;
  order_type?: string | number | null;
  order_date?: string | null;
  total_order_amount?: MoneyAmount | null;
}

export interface StopOrderState {
  stop_order_id: string;
  lots_requested?: number | null;
  figi?: string | null;
  direction?: string | number | null;
  order_type?: string | number | null;
  status?: string | number | null;
  create_date?: string | null;
  expiration_time?: string | null;
  price?: MoneyAmount | null;
  stop_price?: MoneyAmount | null;
  ticker?: string | null;
}

export interface AccountSummary {
  total_amount_portfolio?: MoneyAmount | null;
  expected_yield?: QuotationAmount | null;
  daily_yield?: MoneyAmount | null;
  daily_yield_relative?: QuotationAmount | null;
  portfolio_value?: number | null;
  expected_yield_value?: number | null;
  daily_yield_value?: number | null;
  daily_yield_relative_value?: number | null;
  portfolio_positions_count: number;
  securities_count: number;
  money: MoneyAmount[];
  blocked_money: MoneyAmount[];
  open_orders_count: number;
  stop_orders_count: number;
  operations_count: number;
  allocation: AllocationItem[];
}

export interface AccountOverview {
  account_id: string;
  broker: string;
  as_of: string;
  order_submission_mode: "stub" | "real";
  operations_window: {
    from: string;
    to: string;
    days: number;
  };
  summary: AccountSummary;
  sections: {
    account: AccountItem;
    portfolio?: PortfolioSection | null;
    positions?: PositionsSection | null;
    orders?: { orders?: OrderState[] } | null;
    stop_orders?: { stop_orders?: StopOrderState[] } | null;
    operations?: { operations?: OperationItem[] } | null;
    margin?: Record<string, unknown> | null;
    withdraw_limits?: Record<string, unknown> | null;
    user_info?: Record<string, unknown> | null;
  };
  section_errors: Record<string, string>;
}

export interface PnlEquityPoint {
  date: string;
  nav: number;
  daily_pnl: number;
  cumulative_pnl: number;
  daily_return: number;
  cumulative_return: number;
  drawdown: number;
  external_flow: number;
}

export interface PnlMonthlyReturn {
  month: string;
  return: number;
  pnl: number;
  ending_nav: number;
}

export interface PnlAttributionRow {
  instrument_id: string;
  figi?: string | null;
  ticker: string;
  name: string;
  opening_quantity: number;
  ending_quantity: number;
  opening_value: number;
  ending_value: number;
  pnl_contribution: number;
  contribution_pct?: number | null;
  realized_pnl_broker: number;
  turnover: number;
  trades: number;
}

export interface PnlReport {
  account_id: string;
  account_name: string;
  generated_at: string;
  strategy: {
    name?: string | null;
    attribution_mode: "account" | "dedicated_account_proxy" | "account_context_only";
    is_exact: boolean;
    assigned_strategies: string[];
  };
  period: {
    from: string;
    to: string;
    calendar_days: number;
    observations: number;
  };
  currency: string;
  summary: {
    opening_nav: number;
    ending_nav: number;
    total_pnl: number;
    twr: number;
    mwr?: number | null;
    annualized_return?: number | null;
    realized_pnl_broker: number;
    unrealized_pnl_estimate: number;
    net_external_flow: number;
    inflows: number;
    outflows: number;
    dividends: number;
    coupons: number;
    fees: number;
    taxes: number;
    turnover: number;
    turnover_ratio?: number | null;
    trades: number;
    buys: number;
    sells: number;
  };
  risk: {
    annualized_volatility: number;
    sharpe_ratio?: number | null;
    sortino_ratio?: number | null;
    max_drawdown: number;
    calmar_ratio?: number | null;
    profit_factor?: number | null;
    positive_days: number;
    negative_days: number;
    win_rate?: number | null;
    best_day_pnl: number;
    worst_day_pnl: number;
    average_day_pnl: number;
    historical_var_95_return?: number | null;
    historical_var_95_amount?: number | null;
  };
  components: Array<{ key: string; label: string; value: number }>;
  equity_curve: PnlEquityPoint[];
  monthly_returns: PnlMonthlyReturn[];
  attribution: PnlAttributionRow[];
  data_quality: {
    method: string;
    operations_source: string;
    prices_source: string;
    operations: number;
    priced_instruments: number;
    total_instruments: number;
    price_coverage: number;
    missing_price_instruments: string[];
    reconciliation_difference?: number | null;
    warnings: string[];
  };
}

export interface OrderTicket {
  instrument_id: string;
  figi?: string | null;
  side: "buy" | "sell";
  order_type: "limit" | "market";
  quantity: number;
  price?: number | null;
  price_type?: "currency" | "point" | null;
  time_in_force: "day" | "fill_or_kill" | "fill_and_kill";
  client_order_id?: string | null;
  comment?: string | null;
}

export interface StopOrderTicket {
  instrument_id: string;
  figi?: string | null;
  side: "buy" | "sell";
  stop_order_type: "stop_loss" | "take_profit";
  quantity: number;
  stop_price: number;
  limit_price?: number | null;
  price_type?: "currency" | "point" | null;
  expire_at?: string | null;
  client_order_id?: string | null;
  comment?: string | null;
}

export interface StubResponse {
  id: string;
  broker_order_id?: string | null;
  broker: string;
  account_id: string;
  account_name?: string | null;
  created_at: string;
  status: string;
  submission_mode: "stub" | "real";
  would_submit: boolean;
  submitted?: boolean;
  message: string;
  ticket: OrderTicket | StopOrderTicket;
  broker_response?: Record<string, unknown> | null;
}

export interface TradableInstrument {
  figi: string;
  ticker: string;
  uid?: string | null;
  instrument_uid?: string | null;
  position_uid?: string | null;
  isin?: string | null;
  name: string;
  class_code: string;
  instrument_type: string;
  currency: string;
  exchange?: string | null;
  lot?: number | null;
  trading_status?: string | number | null;
  real_exchange?: string | number | null;
  buy_available_flag?: boolean | null;
  sell_available_flag?: boolean | null;
  api_trade_available_flag?: boolean | null;
}

export interface InstrumentsResponse {
  items: TradableInstrument[];
  total: number;
  limit: number;
  offset: number;
  filters: {
    instrument_types: string[];
    class_codes: string[];
    exchanges: string[];
    currencies: string[];
    intervals: string[];
  };
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
  summary: Array<{
    ticker: string;
    figi: string;
    last_close: number | null;
    change_pct: number | null;
    candles: number;
    from: string | null;
    to: string | null;
  }>;
}

export interface LastPriceResponse {
  figi?: string | null;
  instrument_uid?: string | null;
  instrument_id?: string | null;
  time?: string | null;
  last_price_type?: string | number | null;
  price?: QuotationAmount | null;
  price_value?: number | null;
}

export interface OrderBookLevel {
  price: number | null;
  quantity: number | null;
}

export interface OrderBookSnapshot {
  type: "orderbook";
  instrument_id?: string | null;
  instrument_uid?: string | null;
  figi?: string | null;
  time?: string | null;
  depth?: number | null;
  is_consistent?: boolean | null;
  order_book_type?: string | number | null;
  limit_up?: number | null;
  limit_down?: number | null;
  bids: OrderBookLevel[];
  asks: OrderBookLevel[];
}

export interface TradingStrategyProductionState {
  strategy_name: string | null;
  is_prod_ready: boolean;
  comment: string | null;
  updated_by_user_id: string | null;
  updated_at: string | null;
}

export interface ExecutionStrategyItem {
  name: string;
  module: string;
  description: string;
  source_path?: string | null;
  production_state: TradingStrategyProductionState;
  is_assigned?: boolean;
}

export interface ExecutionStrategyAssignment {
  id: string;
  account_id: string;
  strategy_name: string;
  comment: string | null;
  assigned_by_user_id: string | null;
  created_at: string | null;
  updated_at: string | null;
  strategy: ExecutionStrategyItem;
}

export interface ExecutionStrategiesResponse {
  account_id: string;
  items: ExecutionStrategyAssignment[];
  available: ExecutionStrategyItem[];
  total: number;
}

export interface StrategyRunRequest {
  start_date?: string | null;
  end_date?: string | null;
  interval: string;
  class_code: string;
  order_type: "limit" | "market";
  limit_offset_pct: number;
  min_order_value: number;
  cash_buffer_pct: number;
}

export interface StrategyTargetWeight {
  ticker: string;
  figi?: string | null;
  instrument_id?: string | null;
  name: string;
  sector?: string | null;
  currency: string;
  lot: number;
  last_price: number;
  current_lots: number;
  blocked_lots: number;
  available_lots: number;
  current_quantity: number;
  current_value: number;
  current_weight: number;
  target_weight: number;
  target_value: number;
  one_lot_value: number;
  model_target_lots: number;
  target_lots: number;
  planned_value: number;
  planned_weight: number;
  model_delta_lots: number;
  delta_lots: number;
  delta_value: number;
  target_status: "buy" | "sell" | "keep" | "no_action";
  constraint: "below_one_lot" | "cash_limited" | "below_min_order" | null;
}

export interface StrategyOrderPlanRow {
  ticker: string;
  figi?: string | null;
  instrument_id?: string | null;
  name: string;
  side: "buy" | "sell";
  order_type: "limit" | "market";
  quantity_lots: number;
  lot: number;
  last_price: number;
  limit_price: number | null;
  estimated_amount: number;
  target_weight: number;
  current_weight: number;
}

export interface StrategyStopPlanRow {
  ticker: string;
  figi?: string | null;
  instrument_id?: string | null;
  name: string;
  kind: "stop_loss" | "take_profit";
  side: "sell";
  quantity_lots: number;
  stop_price: number;
  distance_pct: number;
  last_price: number;
}

export interface StrategyRunResult {
  plan_id: string;
  account_id: string;
  strategy_name: string;
  strategy_description: string;
  generated_at: string;
  run_time: string;
  settings: StrategyRunRequest;
  portfolio: {
    value: number;
    currency: string;
  };
  summary: {
    target_positions: number;
    model_target_positions: number;
    planned_target_positions: number;
    below_one_lot_target_positions: number;
    cash_limited_target_positions: number;
    below_min_order_positions: number;
    orders: number;
    buy_orders: number;
    sell_orders: number;
    stop_orders: number;
    gross_buy: number;
    gross_sell: number;
    net_cash_need: number;
    estimated_cash_change: number;
    available_cash: number;
    buying_power_after_sells: number;
    estimated_cash_after_orders: number;
    conservative_cash_after_orders: number;
    minimum_one_lot_cost: number;
    lot_rounding_unallocated_value: number;
  };
  target_weights: StrategyTargetWeight[];
  orders: StrategyOrderPlanRow[];
  stop_orders: StrategyStopPlanRow[];
  execution: {
    ready: boolean;
    blocking_reasons: string[];
    warnings: string[];
    order_type: "market";
    sell_first: boolean;
    stop_orders_included: boolean;
  };
}

export interface StrategyExecutionRequest extends StrategyRunRequest {
  plan_id: string;
  confirmation: "execute_market_orders";
}

export interface StrategyExecutionOrderResult {
  ticker: string;
  figi?: string | null;
  instrument_id?: string | null;
  side: "buy" | "sell";
  quantity_lots: number;
  estimated_amount: number;
  status: "submitted" | "simulated" | "failed" | "skipped";
  client_order_id?: string | null;
  broker_order_id?: string | null;
  response?: StubResponse | null;
  error?: unknown;
}

export interface StrategyExecutionResult {
  execution_id: string;
  plan_id: string;
  account_id: string;
  strategy_name: string;
  requested_by_user_id: string;
  executed_at: string;
  submission_mode: "stub" | "real";
  status: "submitted" | "simulated" | "partial";
  sell_first: boolean;
  stop_orders_submitted: boolean;
  summary: {
    orders: number;
    submitted: number;
    simulated: number;
    failed: number;
    skipped: number;
  };
  results: StrategyExecutionOrderResult[];
}
