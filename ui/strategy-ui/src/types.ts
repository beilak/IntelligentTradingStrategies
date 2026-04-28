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
  asset_limit: number;
  force: boolean;
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
