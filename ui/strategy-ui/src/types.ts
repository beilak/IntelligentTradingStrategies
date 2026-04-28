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
  strategy_type: StrategyType;
}

export interface ModelDetail extends RegistryItem {
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

export interface CpcvSettings {
  test_name: string;
  start_date: string;
  end_date: string;
  interval: string;
  class_code: string;
  n_folds: number;
  n_test_folds: number;
  test_size: number;
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
    assets: Array<{
      figi: string;
      ticker: string;
      name: string;
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
  rebalance_weights: Array<{
    time: string;
    total_weight: number;
    asset_count: number;
    weights: Array<{
      ticker: string;
      weight: number;
    }>;
  }>;
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
