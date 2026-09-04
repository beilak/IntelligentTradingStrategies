export type Locale = "ru" | "en";

export interface RegistryItem {
  name: string;
  module: string;
  kind: string;
  status: string;
  description: string;
  signature: string;
  parameters: Array<{
    name: string;
    default: string;
    annotation: string;
    kind: string;
  }>;
  source_path: string;
  production_state?: TradingStrategyProductionState;
}

export interface RegistryGroup {
  id: string;
  title: string;
  module: string;
  role: string;
  items: RegistryItem[];
  count: number;
}

export interface StrategyType {
  name: string;
  module: string;
  description: string;
  fields: Array<{
    name: string;
    type: string;
    default: string;
  }>;
}

export interface RegistryResponse {
  groups: RegistryGroup[];
  models: RegistryItem[];
  trading_strategies: RegistryItem[];
  strategy_type: StrategyType;
}

export interface ModelDetail extends RegistryItem {
  production_state?: TradingStrategyProductionState;
  composition: {
    steps: Array<{
      step: string;
      component: string;
      category: string;
    }>;
    registered_components: RegistryItem[];
    source_excerpt: string;
  };
  component_groups: RegistryGroup[];
  future_reports: Array<{
    id: string;
    title: string;
    status: string;
  }>;
}

export interface TradingStrategyProductionState {
  strategy_name: string | null;
  is_prod_ready: boolean;
  comment: string | null;
  updated_by_user_id: string | null;
  updated_at: string | null;
}

export interface TradingStrategyListItem extends RegistryItem {
  production_state: TradingStrategyProductionState;
}

export interface CpcvSettings {
  test_name: string;
  start_date: string;
  end_date: string;
  interval: string;
  class_code: string;
  n_folds: number;
  n_test_folds: number;
  test_size: number;
  n_jobs: number;
}

export interface CpcvPeriod {
  start: string;
  end: string;
  rows: number;
}

export interface CpcvSavedTest {
  file_name: string;
  test_name: string;
  model_name: string;
  generated_at: string;
  settings: Partial<CpcvSettings>;
  train_period: Partial<CpcvPeriod>;
  test_period: Partial<CpcvPeriod>;
  asset_count: number;
}

export interface CpcvResult {
  metadata: {
    model_name: string;
    strategy_name: string;
    strategy_description: string;
    test_name: string;
    test_type: string;
    generated_at: string;
    source: string;
    settings: CpcvSettings;
    train_period: CpcvPeriod;
    test_period: CpcvPeriod;
    stitch_rule?: string;
    assets: Array<{
      figi: string;
      ticker: string;
      name: string;
      sector?: string | null;
    }>;
    asset_count: number;
  };
  cv_summary: Array<{
    metric: string;
    value: string;
    numeric_value: number | null;
  }>;
  report: Array<{
    metric: string;
    value: string;
    numeric_value: number | null;
  }>;
  paths: Array<{
    name: string;
    final_return: number;
    points: Array<{
      time: string;
      value: number;
    }>;
  }>;
}

export interface WalkForwardSettings {
  test_name: string;
  start_date: string;
  end_date: string;
  interval: string;
  class_code: string;
  test_size: number;
  train_size_months: number;
  freq_months: number;
  wf_test_size: number;
}

export interface WalkForwardSavedTest {
  file_name: string;
  test_name: string;
  model_name: string;
  generated_at: string;
  settings: Partial<WalkForwardSettings>;
  train_period: Partial<CpcvPeriod>;
  test_period: Partial<CpcvPeriod>;
  asset_count: number;
}

export interface WalkForwardResult {
  metadata: {
    model_name: string;
    strategy_name: string;
    strategy_description: string;
    test_name: string;
    test_type: string;
    generated_at: string;
    settings: WalkForwardSettings;
    train_period: CpcvPeriod;
    test_period: CpcvPeriod;
    stitch_rule?: string;
    assets: Array<{
      figi: string;
      ticker: string;
      name: string;
      sector?: string | null;
    }>;
    asset_count: number;
  };
  cv_summary: Array<{
    metric: string;
    value: string;
    numeric_value: number | null;
  }>;
  report: Array<{
    metric: string;
    value: string;
    numeric_value: number | null;
  }>;
  oos_curve?: {
    name: string;
    stitch_rule: string;
    final_return: number | null;
    rows: number;
    duplicates_removed: number;
    segments?: Array<{
      name: string;
      window_index: number;
      final_return: number;
      points: Array<{
        time: string;
        value: number;
      }>;
    }>;
    points: Array<{
      time: string;
      value: number;
    }>;
  };
  windows?: Array<{
    split_id: number;
    train_start: string;
    train_end: string;
    train_rows: number;
    test_start: string;
    test_end: string;
    test_rows: number;
  }>;
  paths: Array<{
    name: string;
    final_return: number;
    points: Array<{
      time: string;
      value: number;
    }>;
  }>;
}

export interface BacktestSettings {
  test_name: string;
  start_date: string;
  end_date: string;
  interval: string;
  class_code: string;
  trading_start_date: string;
  rebalance_freq: string;
  rebalance_on: string;
  init_cash: number;
  fees: number;
  slippage: number;
  freq: string;
  rolling_window: number;
  tax_rate: number;
}

export interface BacktestSavedTest {
  file_name: string;
  test_name: string;
  model_name: string;
  generated_at: string;
  settings: Partial<BacktestSettings>;
  trading_period: Partial<CpcvPeriod>;
  asset_count: number;
}

export interface BacktestResult {
  metadata: {
    model_name: string;
    strategy_name: string;
    strategy_description: string;
    test_name: string;
    test_type: string;
    generated_at: string;
    settings: BacktestSettings;
    price_period: CpcvPeriod;
    trading_period: CpcvPeriod;
    entity_type?: string;
    core_strategy_name?: string;
    core_strategy_description?: string;
    exit_policy?: {
      name: string;
      description: string;
    };
    strategy_metadata?: Record<string, unknown>;
    assets: Array<{
      figi: string;
      ticker: string;
      name: string;
      sector?: string | null;
    }>;
    asset_count: number;
  };
  report: Array<{
    metric: string;
    value: string;
    numeric_value: number | null;
  }>;
  summary: Array<{
    metric: string;
    value: string;
    numeric_value: number | null;
  }>;
  equity_curve: {
    name: string;
    final_value: number | null;
    points: Array<{ time: string; value: number }>;
  };
  drawdown_curve: {
    name: string;
    final_value: number | null;
    points: Array<{ time: string; value: number }>;
  };
  rolling_sharpe: {
    name: string;
    final_value: number | null;
    points: Array<{ time: string; value: number }>;
  };
  pnl_source?: BacktestPnlSource;
  rebalance_weights: Array<{
    time: string;
    total_weight: number;
    asset_count: number;
    weights: Array<{
      ticker: string;
      weight: number;
      sector?: string | null;
    }>;
  }>;
  execution_events: Array<{
    time: string;
    ticker: string;
    reason: string;
    entry_time: string;
    entry_price: number | null;
    execution_price: number | null;
    threshold_price: number | null;
    return_pct: number | null;
    weight: number | null;
  }>;
}

export interface BacktestPnlSource {
  method: string;
  currency: string;
  initial_nav: number;
  external_flows: false;
  taxes_applied: false;
  daily_asset_pnl: Array<{
    time: string;
    contributions: Record<string, number>;
  }>;
  orders: Array<{
    id: number;
    time: string;
    ticker: string;
    side: "buy" | "sell";
    size: number;
    price: number;
    fees: number;
    reference_price: number | null;
    slippage_cost: number;
  }>;
  trades: Array<{
    id: number;
    ticker: string;
    size: number;
    entry_time: string;
    exit_time: string;
    pnl: number | null;
    return: number | null;
    status: "open" | "closed" | string;
  }>;
}

export interface BacktestPnlEquityPoint {
  date: string;
  nav: number;
  daily_pnl: number;
  cumulative_pnl: number;
  daily_return: number;
  cumulative_return: number;
  drawdown: number;
}

export interface BacktestPnlAttributionRow {
  ticker: string;
  name: string;
  opening_quantity: number;
  ending_quantity: number;
  opening_value: number;
  ending_value: number;
  pnl_contribution: number;
  contribution_pct: number | null;
  realized_pnl: number;
  turnover: number;
  orders: number;
}

export interface BacktestPnlReport {
  generated_at: string;
  model_name: string;
  strategy_name: string;
  test_name: string;
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
    mwr: number | null;
    annualized_return: number | null;
    realized_pnl: number;
    unrealized_pnl_estimate: number;
    fees: number;
    slippage: number;
    estimated_tax: number;
    after_tax_pnl_estimate: number;
    turnover: number;
    turnover_ratio: number | null;
    orders: number;
    buys: number;
    sells: number;
  };
  risk: {
    annualized_volatility: number;
    sharpe_ratio: number | null;
    sortino_ratio: number | null;
    max_drawdown: number;
    calmar_ratio: number | null;
    profit_factor: number | null;
    positive_days: number;
    negative_days: number;
    win_rate: number | null;
    best_day_pnl: number;
    worst_day_pnl: number;
    average_day_pnl: number;
    historical_var_95_return: number | null;
    historical_var_95_amount: number | null;
  };
  components: Array<{ key: string; label: string; value: number }>;
  equity_curve: BacktestPnlEquityPoint[];
  monthly_returns: Array<{
    month: string;
    return: number;
    pnl: number;
    ending_nav: number;
  }>;
  attribution: BacktestPnlAttributionRow[];
  methodology: {
    method: string;
    engine: string;
    has_detailed_source: boolean;
    external_flows: false;
    taxes_applied: false;
    warnings: string[];
  };
}

export interface TestRun {
  run_id: string;
  test_type: "cpcv" | "walk_forward" | "backtest";
  subject_name: string;
  test_name: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  error: string | null;
}

export type CpcvRun = TestRun;
export type WalkForwardRun = TestRun;
export type BacktestRun = TestRun;

export interface RiskModelDefinition {
  id: string;
  title: string;
  metric: string;
  engine: string;
}

export interface RiskModelSettings {
  test_name: string;
  start_date: string;
  end_date: string;
  interval: string;
  class_code: string;
  test_size: number;
  portfolio_value: number;
  confidence_level: number;
  horizon_days: number;
  n_simulations: number;
  simulation_method: "historical_bootstrap" | "multivariate_normal";
  random_state: number;
  n_buckets: number;
  qae_iterations: number;
  qae_shots: number;
}

export interface RiskModelSavedTest {
  file_name: string;
  test_name: string;
  model_name: string;
  risk_model: string;
  risk_model_title: string;
  generated_at: string;
  settings: Partial<RiskModelSettings>;
  train_period: Partial<CpcvPeriod>;
  test_period: Partial<CpcvPeriod>;
  asset_count: number;
  scenario_count: number;
}

export interface RiskModelMetricRow {
  metric: string;
  value: string;
  numeric_value: number | null;
}

export interface RiskModelResult {
  metadata: {
    model_name: string;
    strategy_name: string;
    strategy_description: string;
    test_name: string;
    test_type: string;
    risk_model: string;
    risk_model_title: string;
    engine: string;
    generated_at: string;
    settings: RiskModelSettings;
    train_period: CpcvPeriod;
    test_period: CpcvPeriod;
    assets: Array<{
      figi: string;
      ticker: string;
      name: string;
      sector?: string | null;
    }>;
    asset_count: number;
    scenario_count: number;
    confidence_level: number;
    horizon_days: number;
  };
  summary: RiskModelMetricRow[];
  report: RiskModelMetricRow[];
  portfolio_weights: Array<{
    ticker: string;
    weight: number;
    figi?: string | null;
    name?: string | null;
    sector?: string | null;
  }>;
  loss_distribution: {
    name: string;
    var_threshold: number;
    bins: Array<{
      loss: number;
      probability: number;
      count: number;
      cumulative_probability: number;
      is_tail: boolean;
    }>;
  };
  cumulative_distribution: {
    name: string;
    points: Array<{ x: number; y: number }>;
  };
  simulated_paths?: {
    name: string;
    paths: Array<{
      name: string;
      final_value: number;
      points: Array<{ x: number; y: number }>;
    }>;
  };
  historical_portfolio_curve: {
    name: string;
    final_value: number | null;
    points: Array<{ time: string; value: number }>;
  };
  qae_distribution?: {
    bucket_count: number;
    qubits: number;
    buckets: Array<{
      bucket: number;
      loss: number;
      probability: number;
      count: number;
    }>;
  } | null;
  qae?: Record<string, number | string | null> | null;
  reference?: Record<string, number | string | null> | null;
  interpretation: string;
}

export interface StrategyComparisonResult {
  generated_at: string;
  eligible_count: number;
  winner: StrategyComparisonRow | null;
  rows: StrategyComparisonRow[];
  skipped: Array<{
    model_name: string;
    missing_tests: string[];
    missing_metrics?: string[];
  }>;
  backtest_winners: Array<{
    metric: string;
    direction: "higher" | "lower";
    winner: string;
    value: number | null;
  }>;
  explanations: string[];
}

export interface StrategyComparisonRow {
  rank: number;
  model_name: string;
  WF_Return: number | null;
  WF_Calmar: number | null;
  Robustness_Delta: number | null;
  Sharpe_Stability: number | null;
  Daily_Risk_CVaR: number | null;
  WF_Max_Drawdown: number | null;
  Backtest_Total_Return: number | null;
  Backtest_Sharpe: number | null;
  Backtest_Calmar: number | null;
  Backtest_Max_Drawdown: number | null;
  Backtest_Metric_Wins: number | null;
  TOTAL_SCORE: number | null;
  latest_tests: Record<
    string,
    {
      file_name: string;
      test_name: string;
      generated_at: string;
      test_type: string;
      settings: Record<string, unknown>;
    }
  >;
}
