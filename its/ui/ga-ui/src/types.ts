export type Locale = "ru" | "en";

export interface Gene {
  id: string;
  title: string;
  description: string;
  group: "pre_selection" | "signal" | "allocation";
  component_path: string | null;
  component_kwargs: Record<string, unknown>;
  asset_universe_arg: string | null;
  wrapper_path: string | null;
  wrapper_kwargs: Record<string, unknown>;
  factory_path: string | null;
  factory_kwargs: Record<string, unknown>;
}

export interface AlphabetGroup {
  id: string;
  title: string;
  count: number;
  items: Gene[];
}

export interface AlphabetResponse {
  groups: AlphabetGroup[];
  search_space: number;
}

export interface GARunSettings {
  test_name: string;
  start_date: string;
  end_date: string;
  interval: string;
  class_code: string;
  test_size: number;
  num_generations: number;
  sol_per_pop: number;
  num_parents_mating: number;
  mutation_probability: number;
  parent_selection_type: string;
  k_tournament: number;
  keep_parents: number;
  keep_elitism: number;
  crossover_type: string;
  mutation_type: string;
  stop_criteria: string;
  random_seed: number;
  cpcv_n_folds: number;
  cpcv_n_test_folds: number;
  wf_train_size: number;
  wf_test_size: number;
  wf_purged_size: number;
  top_n: number;
  materialize_top: boolean;
}

export interface GARun {
  run_id: string;
  status: "queued" | "running" | "completed" | "failed";
  created_at: string;
  updated_at: string;
  settings: GARunSettings & { run_id: string };
  events: GAEvent[];
  result: GAResult | null;
  error: string | null;
}

export interface GAEvent {
  at: string;
  type: string;
  summary?: GenerationSummary;
  population?: CandidateRow[];
}

export interface GenerationSummary {
  generation: number;
  best_total_score: number | null;
  mean_total_score: number | null;
  best_strategy_name: string;
  best_selector: string;
  best_signal: string;
  best_allocation: string;
}

export interface CandidateRow {
  solution_key: number[];
  strategy_name: string;
  selector_name: string;
  signal_name: string;
  allocation_name: string;
  TOTAL_SCORE: number | null;
  TOTAL_SCORE_BASE: number | null;
  TOTAL_PENALTY: number | null;
  WF_Return: number | null;
  WF_Calmar: number | null;
  WF_Max_Drawdown_Abs: number | null;
  WF_Mean_Active_Assets: number | null;
  Robustness_Delta: number | null;
  Sharpe_Stability: number | null;
  evaluation_ok: boolean;
  error: string | null;
}

export interface GAResult {
  metadata: {
    run_id: string;
    test_name: string;
    generated_at: string;
    search_space: number;
    evaluated_count: number;
    price_rows: number;
    asset_count: number;
    train_period: { start: string; end: string; rows: number };
    test_period: { start: string; end: string; rows: number };
  };
  generation_summaries: GenerationSummary[];
  population_scores: Array<{ generation: number; items: CandidateRow[] }>;
  final_population: CandidateRow[];
  all_evaluated: CandidateRow[];
  top_strategies: CandidateRow[];
  materialized: Array<{
    rank: string;
    class_name: string;
    module_name: string;
    file_path: string;
  }>;
  materialization_error: string | null;
}

export interface GARunSummary {
  run_id: string;
  status: string;
  created_at: string;
  updated_at: string;
  test_name: string;
  best_score: number | null;
  best_strategy: string | null;
  materialized_count: number;
  error: string | null;
}
