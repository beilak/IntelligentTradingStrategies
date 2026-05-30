# ## 3. GA Strategy Search

# Новый блок не изменяет старый ручной перебор стратегий. Здесь стратегия собирается как комбинация из 3 дискретных алфавитов:

# - `selector`
# - `signal`
# - `optimizer`

# Для GA используется одна финальная версия `Absolute TOTAL_SCORE`:

# - score не зависит от текущей популяции или номера итерации;
# - score считается по фиксированным шкалам метрик;
# - добавлены штрафы за просадку больше `20%`;
# - добавлены штрафы за слишком узкий портфель, если в среднем бумаг меньше `4`.


import io
from contextlib import redirect_stdout

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pygad
from sklearn.base import BaseEstimator
from sklearn.feature_selection import SelectorMixin

from its.strategies.core.selectors import (
    SafeEmptySelector,
    SectorSelector,
    TrendSelector,
)
from its.strategies.core.types.strategy_types import Strategy


class KeepAllSelector(SelectorMixin, BaseEstimator):
    def fit(self, X, y=None):
        self.to_keep_ = np.ones(X.shape[1], dtype=bool)
        return self

    def _get_support_mask(self):
        return self.to_keep_


def ga_make_meanrisk_optimizer(objective_function, portfolio_name):
    return MeanRisk(
        budget=budget,
        min_budget=min_budget,
        max_budget=max_budget,
        min_weights=min_weights,
        max_weights=max_weights,
        risk_measure=RiskMeasure.VARIANCE,
        objective_function=objective_function,
        prior_estimator=EmpiricalPrior(covariance_estimator=LedoitWolf()),
        portfolio_params=dict(name=portfolio_name),
        raise_on_failure=False,
    )


selected_sectors_it_telecom = ["it", "telecom"]

ga_selector_alphabet = {
    "sector_it_telecom": lambda: SectorSelector(
        assets_info=assets_info,
        sectors=selected_sectors_it_telecom,
    ),
    "sector_it_only": lambda: SectorSelector(
        assets_info=assets_info,
        sectors=["it"],
    ),
    "sector_telecom_only": lambda: SectorSelector(
        assets_info=assets_info,
        sectors=["telecom"],
    ),
}

ga_signal_alphabet = {
    "pass_through": lambda: KeepAllSelector(),
    "trend_20": lambda: SafeEmptySelector(TrendSelector(window=20)),
    "gold_trend_20": lambda: SafeEmptySelector(
        GoldTrendSelector(gold_bar=gold_bars_close, window=20)
    ),
    "momentum_63_q50": lambda: SafeEmptySelector(
        CrossSectionalMomentumSelector(lookback=63, quantile=0.5, min_periods=20)
    ),
    "gold_momentum_63_q50": lambda: SafeEmptySelector(
        GoldCrossSectionalMomentumSelector(
            gold_bar=gold_bars_close,
            lookback=63,
            quantile=0.5,
            min_periods=20,
        )
    ),
    "sma_cross_20_60": lambda: SafeEmptySelector(
        SMACrossSelector(fast=20, slow=60, min_periods=60)
    ),
    "gold_sma_cross_20_60": lambda: SafeEmptySelector(
        GoldSMACrossSelector(
            gold_bar=gold_bars_close,
            fast=20,
            slow=60,
            min_periods=60,
        )
    ),
    "breakout_20": lambda: SafeEmptySelector(BreakoutSelector(lookback=20)),
    "gold_breakout_20": lambda: SafeEmptySelector(
        GoldBreakoutSelector(gold_bar=gold_bars_close, lookback=20)
    ),
    "volatility_regime_63_q70": lambda: SafeEmptySelector(
        VolatilityRegimeSelector(lookback=63, quantile=0.7, min_periods=20)
    ),
    "gold_volatility_regime_63_q70": lambda: SafeEmptySelector(
        GoldVolatilityRegimeSelector(
            gold_bar=gold_bars_close,
            lookback=63,
            quantile=0.7,
            min_periods=20,
        )
    ),
}

ga_optimizer_alphabet = {
    "equal_weighted": lambda: EqualWeighted(),
    "inverse_volatility": lambda: InverseVolatility(raise_on_failure=False),
    "cvar": lambda: CVaR(),
    "max_sharpe": lambda: ga_make_meanrisk_optimizer(
        ObjectiveFunction.MAXIMIZE_RATIO,
        "GA Max Sharpe",
    ),
    "maximize_return": lambda: ga_make_meanrisk_optimizer(
        ObjectiveFunction.MAXIMIZE_RETURN,
        "GA Max Return",
    ),
}

ga_selector_keys = list(ga_selector_alphabet)
ga_signal_keys = list(ga_signal_alphabet)
ga_optimizer_keys = list(ga_optimizer_alphabet)

ga_search_space_overview = pd.DataFrame(
    {
        "group": ["selector", "signal", "optimizer"],
        "count": [
            len(ga_selector_keys),
            len(ga_signal_keys),
            len(ga_optimizer_keys),
        ],
    }
)

display(ga_search_space_overview)
print(
    "GA search space:",
    len(ga_selector_keys) * len(ga_signal_keys) * len(ga_optimizer_keys),
    "combinations",
)


# Пример вывода
# 	group	count
# 0	selector	3
# 1	signal	11
# 2	optimizer	5
# GA search space: 165 combinations
#
#
#


def ga_solution_key(solution):
    solution = np.asarray(solution, dtype=int)
    return tuple(int(x) for x in solution.tolist())


def ga_decode_solution(solution):
    selector_idx, signal_idx, optimizer_idx = ga_solution_key(solution)
    selector_name = ga_selector_keys[selector_idx]
    signal_name = ga_signal_keys[signal_idx]
    optimizer_name = ga_optimizer_keys[optimizer_idx]
    strategy_name = f"[GA][{selector_name}][{signal_name}][{optimizer_name}]"

    return {
        "solution_key": (selector_idx, signal_idx, optimizer_idx),
        "selector_idx": selector_idx,
        "signal_idx": signal_idx,
        "optimizer_idx": optimizer_idx,
        "selector_name": selector_name,
        "signal_name": signal_name,
        "optimizer_name": optimizer_name,
        "strategy_name": strategy_name,
    }


def ga_build_strategy(solution):
    decoded = ga_decode_solution(solution)
    return Strategy(
        name=decoded["strategy_name"],
        pipeline=Pipeline(
            [
                ("selector", ga_selector_alphabet[decoded["selector_name"]]()),
                ("signal", ga_signal_alphabet[decoded["signal_name"]]()),
                ("optimizer", ga_optimizer_alphabet[decoded["optimizer_name"]]()),
            ]
        ),
    )


GA_METRIC_FALLBACKS = {
    "WF_Return": -100.0,
    "WF_Calmar": -10.0,
    "Robustness_Delta": 100.0,
    "Sharpe_Stability": 10.0,
    "Daily_Risk_CVaR": 100.0,
    "CPCV_AnnRet_Median": -100.0,
    "WF_Max_Drawdown_Abs": 100.0,
    "WF_Mean_Active_Assets": 0.0,
    "WF_Min_Active_Assets": 0.0,
}

GA_ABSOLUTE_SCORE_CONFIG = {
    "WF_Return": {
        "weight": 0.30,
        "direction": "higher",
        "bad": -10.0,
        "good": 25.0,
    },
    "WF_Calmar": {
        "weight": 0.30,
        "direction": "higher",
        "bad": 0.0,
        "good": 1.50,
    },
    "Robustness_Delta": {
        "weight": 0.20,
        "direction": "lower",
        "good": 0.0,
        "bad": 15.0,
    },
    "Sharpe_Stability": {
        "weight": 0.20,
        "direction": "lower",
        "good": 0.10,
        "bad": 0.80,
    },
}

GA_ABSOLUTE_PENALTY_CONFIG = {
    "max_drawdown": {
        "threshold": 20.0,
        "hard": 35.0,
        "max_penalty": 25.0,
    },
    "portfolio_breadth": {
        "threshold": 4.0,
        "hard": 1.0,
        "max_penalty": 15.0,
    },
}


def ga_clean_metric_value(value):
    if isinstance(value, str):
        value = value.replace("%", "").strip()

    try:
        value = float(value)
    except (TypeError, ValueError):
        return np.nan

    if not np.isfinite(value):
        return np.nan

    return value


def ga_finalize_raw_metrics(raw_metrics):
    safe_metrics = {}
    for metric_name, metric_value in raw_metrics.items():
        fallback = GA_METRIC_FALLBACKS.get(metric_name, 0.0)
        if pd.isna(metric_value) or not np.isfinite(metric_value):
            safe_metrics[metric_name] = fallback
        else:
            safe_metrics[metric_name] = float(metric_value)
    return safe_metrics


def ga_extract_portfolio_breadth_metrics(wf_result):
    try:
        weights = wf_result.weights_per_observation
        if weights is None:
            return {
                "WF_Mean_Active_Assets": 0.0,
                "WF_Min_Active_Assets": 0.0,
            }

        if not isinstance(weights, pd.DataFrame):
            weights = pd.DataFrame(weights)

        if weights.empty:
            return {
                "WF_Mean_Active_Assets": 0.0,
                "WF_Min_Active_Assets": 0.0,
            }

        active_counts = weights.abs().gt(1e-8).sum(axis=1).astype(float)
        if active_counts.empty:
            return {
                "WF_Mean_Active_Assets": 0.0,
                "WF_Min_Active_Assets": 0.0,
            }

        return {
            "WF_Mean_Active_Assets": float(active_counts.mean()),
            "WF_Min_Active_Assets": float(active_counts.min()),
        }
    except Exception:
        return {
            "WF_Mean_Active_Assets": 0.0,
            "WF_Min_Active_Assets": 0.0,
        }


def ga_extract_raw_metrics(strategy_name, cpcv_result, wf_result):
    cpcv_report = get_cpcv_report({strategy_name: cpcv_result})
    wf_report = get_wf_report({strategy_name: wf_result})

    wf_ret = ga_clean_metric_value(wf_report.loc["Annualized Mean", strategy_name])
    wf_calmar = ga_clean_metric_value(wf_report.loc["Calmar Ratio", strategy_name])
    wf_cvar = ga_clean_metric_value(wf_report.loc["CVaR at 95%", strategy_name])
    wf_max_drawdown_abs = abs(
        ga_clean_metric_value(wf_report.loc["MAX Drawdown", strategy_name])
    )

    cpcv_ret_med = ga_clean_metric_value(
        cpcv_report.loc["Ann. Ret (Median)", strategy_name]
    )
    cpcv_sharpe_std = ga_clean_metric_value(
        cpcv_report.loc["Sharpe Stability (Std)", strategy_name]
    )

    breadth_metrics = ga_extract_portfolio_breadth_metrics(wf_result)

    return ga_finalize_raw_metrics(
        {
            "WF_Return": wf_ret,
            "WF_Calmar": wf_calmar,
            "Robustness_Delta": abs(cpcv_ret_med - wf_ret),
            "Sharpe_Stability": cpcv_sharpe_std,
            "Daily_Risk_CVaR": wf_cvar,
            "CPCV_AnnRet_Median": cpcv_ret_med,
            "WF_Max_Drawdown_Abs": wf_max_drawdown_abs,
            **breadth_metrics,
        }
    )


def ga_evaluate_strategy_raw_metrics(solution):
    decoded = ga_decode_solution(solution)
    strategy = ga_build_strategy(solution)
    print(f"Evaluating {strategy.name}")

    try:
        with redirect_stdout(io.StringIO()):
            cpcv_result = cross_val_predict(
                strategy.pipeline,
                X_test,
                cv=CombinatorialPurgedCV(n_folds=10, n_test_folds=6),
                n_jobs=-1,
                portfolio_params=dict(annualized_factor=252, tag=strategy.name),
            )
            wf_result = cross_val_predict(
                strategy.pipeline,
                X_test_wf,
                cv=WalkForward(test_size=21, train_size=63, purged_size=5),
                n_jobs=-1,
                portfolio_params=dict(annualized_factor=252, tag=strategy.name),
            )
        raw_metrics = ga_extract_raw_metrics(strategy.name, cpcv_result, wf_result)
        return {
            **decoded,
            **raw_metrics,
            "evaluation_ok": True,
            "error": None,
        }
    except Exception as exc:
        penalty_metrics = ga_finalize_raw_metrics(GA_METRIC_FALLBACKS)
        return {
            **decoded,
            **penalty_metrics,
            "evaluation_ok": False,
            "error": repr(exc),
        }


def ga_clip_01(value):
    return float(np.clip(value, 0.0, 1.0))


def ga_score_higher_better(value, bad, good):
    if not np.isfinite(value):
        return 0.0
    if np.isclose(good, bad):
        return 1.0 if value >= good else 0.0
    return ga_clip_01((value - bad) / (good - bad))


def ga_score_lower_better(value, good, bad):
    if not np.isfinite(value):
        return 0.0
    if np.isclose(good, bad):
        return 1.0 if value <= good else 0.0
    return ga_clip_01((bad - value) / (bad - good))


def ga_penalty_above_threshold(value, threshold, hard, max_penalty):
    if not np.isfinite(value):
        return float(max_penalty)
    if value <= threshold:
        return 0.0
    if value >= hard:
        return float(max_penalty)
    return float(max_penalty) * (value - threshold) / (hard - threshold)


def ga_penalty_below_threshold(value, threshold, hard, max_penalty):
    if not np.isfinite(value):
        return float(max_penalty)
    if value >= threshold:
        return 0.0
    if value <= hard:
        return float(max_penalty)
    return float(max_penalty) * (threshold - value) / (threshold - hard)


def ga_compute_total_score(raw_df, score_config=None, penalty_config=None):
    score_config = score_config or GA_ABSOLUTE_SCORE_CONFIG
    penalty_config = penalty_config or GA_ABSOLUTE_PENALTY_CONFIG
    scored = raw_df.copy()

    for metric_name, fallback in GA_METRIC_FALLBACKS.items():
        scored[metric_name] = (
            pd.to_numeric(scored[metric_name], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(fallback)
        )

    for metric_name, metric_cfg in score_config.items():
        score_column = f"{metric_name}_score"
        if metric_cfg["direction"] == "higher":
            scored[score_column] = scored[metric_name].apply(
                lambda x: ga_score_higher_better(
                    x,
                    bad=metric_cfg["bad"],
                    good=metric_cfg["good"],
                )
            )
        else:
            scored[score_column] = scored[metric_name].apply(
                lambda x: ga_score_lower_better(
                    x,
                    good=metric_cfg["good"],
                    bad=metric_cfg["bad"],
                )
            )

    scored["TOTAL_SCORE_01"] = 0.0
    for metric_name, metric_cfg in score_config.items():
        scored["TOTAL_SCORE_01"] += (
            metric_cfg["weight"] * scored[f"{metric_name}_score"]
        )

    dd_cfg = penalty_config["max_drawdown"]
    breadth_cfg = penalty_config["portfolio_breadth"]

    scored["DrawdownPenalty"] = scored["WF_Max_Drawdown_Abs"].apply(
        lambda x: ga_penalty_above_threshold(
            x,
            threshold=dd_cfg["threshold"],
            hard=dd_cfg["hard"],
            max_penalty=dd_cfg["max_penalty"],
        )
    )
    scored["BreadthPenalty"] = scored["WF_Mean_Active_Assets"].apply(
        lambda x: ga_penalty_below_threshold(
            x,
            threshold=breadth_cfg["threshold"],
            hard=breadth_cfg["hard"],
            max_penalty=breadth_cfg["max_penalty"],
        )
    )
    scored["TOTAL_PENALTY"] = scored["DrawdownPenalty"] + scored["BreadthPenalty"]
    scored["TOTAL_SCORE_BASE"] = (100.0 * scored["TOTAL_SCORE_01"]).round(4)
    scored["TOTAL_SCORE"] = (
        (scored["TOTAL_SCORE_BASE"] - scored["TOTAL_PENALTY"]).clip(lower=0.0).round(4)
    )

    return scored.sort_values("TOTAL_SCORE", ascending=False)


GA_SCORE_MODE = "absolute_fixed_thresholds_with_risk_and_breadth_penalties"
GA_SCORE_COMPONENT_COLUMNS = [
    *(f"{metric_name}_score" for metric_name in GA_ABSOLUTE_SCORE_CONFIG),
    "WF_Max_Drawdown_Abs",
    "WF_Mean_Active_Assets",
    "WF_Min_Active_Assets",
    "DrawdownPenalty",
    "BreadthPenalty",
    "TOTAL_PENALTY",
    "TOTAL_SCORE_BASE",
]

ga_raw_metric_cache = {}
ga_generation_summaries = []
ga_generation_population_scores = []


def ga_reset_state():
    ga_raw_metric_cache.clear()
    ga_generation_summaries.clear()
    ga_generation_population_scores.clear()


def ga_rank_population(population):
    population_array = np.asarray(population, dtype=int)
    if population_array.ndim == 1:
        population_array = population_array.reshape(1, -1)

    unique_keys = list(
        dict.fromkeys(ga_solution_key(solution) for solution in population_array)
    )

    for solution_key in unique_keys:
        if solution_key not in ga_raw_metric_cache:
            ga_raw_metric_cache[solution_key] = ga_evaluate_strategy_raw_metrics(
                solution_key
            )

    raw_df = pd.DataFrame(
        [ga_raw_metric_cache[solution_key] for solution_key in unique_keys]
    ).set_index("solution_key")

    return ga_compute_total_score(raw_df)


def ga_rank_all_evaluated_strategies():
    if not ga_raw_metric_cache:
        return pd.DataFrame()

    raw_df = pd.DataFrame(ga_raw_metric_cache.values()).set_index("solution_key")
    return ga_compute_total_score(raw_df)


def ga_fitness_func(ga_instance, solutions, solution_indices):
    scored_population = ga_rank_population(ga_instance.population)
    ga_instance.ga_last_scored_population = scored_population.copy()

    batch = np.asarray(solutions, dtype=int)
    if scored_population.empty:
        if batch.ndim == 1:
            return -1.0
        return [-1.0] * len(batch)

    if batch.ndim == 1:
        score = scored_population.at[ga_solution_key(batch), "TOTAL_SCORE"]
        return float(score) if np.isfinite(score) else -1.0

    batch_scores = []
    for solution in batch:
        score = scored_population.at[ga_solution_key(solution), "TOTAL_SCORE"]
        batch_scores.append(float(score) if np.isfinite(score) else -1.0)
    return batch_scores


def ga_on_generation(ga_instance):
    scored_population = getattr(ga_instance, "ga_last_scored_population", None)
    if scored_population is None or scored_population.empty:
        scored_population = ga_rank_population(ga_instance.population)

    best_row = scored_population.iloc[0]
    generation_snapshot = scored_population.copy()
    generation_snapshot["generation"] = ga_instance.generations_completed

    ga_generation_population_scores.append(generation_snapshot.reset_index())
    ga_generation_summaries.append(
        {
            "generation": ga_instance.generations_completed,
            "best_total_score": float(best_row["TOTAL_SCORE"]),
            "mean_total_score": float(scored_population["TOTAL_SCORE"].mean()),
            "best_strategy_name": best_row["strategy_name"],
            "best_selector": best_row["selector_name"],
            "best_signal": best_row["signal_name"],
            "best_optimizer": best_row["optimizer_name"],
        }
    )

    print(
        f"Generation {ga_instance.generations_completed}: "
        f"best={best_row['strategy_name']} "
        f"TOTAL_SCORE={best_row['TOTAL_SCORE']:.4f}"
    )


display(
    pd.DataFrame(GA_ABSOLUTE_SCORE_CONFIG)
    .T.reset_index()
    .rename(columns={"index": "metric"})
)
display(
    pd.DataFrame(GA_ABSOLUTE_PENALTY_CONFIG)
    .T.reset_index()
    .rename(columns={"index": "penalty"})
)
print("GA score mode:", GA_SCORE_MODE)
print("TOTAL_SCORE scale: 0..100")


# пример вывода
# metric	weight	direction	bad	good
# 0	WF_Return	0.3	higher	-10.0	25.0
# 1	WF_Calmar	0.3	higher	0.0	1.5
# 2	Robustness_Delta	0.2	lower	15.0	0.0
# 3	Sharpe_Stability	0.2	lower	0.8	0.1
# penalty	threshold	hard	max_penalty
# 0	max_drawdown	20.0	35.0	25.0
# 1	portfolio_breadth	4.0	1.0	15.0
# GA score mode: absolute_fixed_thresholds_with_risk_and_breadth_penalties
# TOTAL_SCORE scale: 0..100


GA_NUM_GENERATIONS = 10
GA_SOL_PER_POP = 8
GA_NUM_PARENTS_MATING = 4
GA_MUTATION_PROBABILITY = 0.25
GA_STOP_CRITERIA = "saturate_3"

ga_reset_state()

# Единственная активная версия GA:
# absolute TOTAL_SCORE на фиксированных шкалах
# + штрафы за drawdown > 20%
# + штрафы за слишком узкий портфель (< 4 бумаг в среднем)
ga_instance = pygad.GA(
    num_generations=GA_NUM_GENERATIONS,
    num_parents_mating=GA_NUM_PARENTS_MATING,
    fitness_func=ga_fitness_func,
    fitness_batch_size=GA_SOL_PER_POP,
    sol_per_pop=GA_SOL_PER_POP,
    num_genes=3,
    gene_space=[
        list(range(len(ga_selector_keys))),
        list(range(len(ga_signal_keys))),
        list(range(len(ga_optimizer_keys))),
    ],
    gene_type=int,
    parent_selection_type="tournament",
    K_tournament=3,
    keep_parents=0,
    keep_elitism=0,
    crossover_type="uniform",
    mutation_type="random",
    mutation_probability=GA_MUTATION_PROBABILITY,
    stop_criteria=GA_STOP_CRITERIA,
    on_generation=ga_on_generation,
    random_seed=SEED,
    suppress_warnings=True,
)

ga_instance.run()

ga_generation_report = pd.DataFrame(ga_generation_summaries)
ga_final_population_scores = ga_rank_population(ga_instance.population)
ga_all_evaluated_scores = ga_rank_all_evaluated_strategies()

ga_top3_results = ga_all_evaluated_scores.head(3).copy()
ga_top3_results_display = ga_top3_results[
    [
        "strategy_name",
        "selector_name",
        "signal_name",
        "optimizer_name",
        "TOTAL_SCORE",
        "TOTAL_SCORE_BASE",
        "TOTAL_PENALTY",
        "WF_Return",
        "WF_Calmar",
        "WF_Max_Drawdown_Abs",
        "WF_Mean_Active_Assets",
        "Robustness_Delta",
        "Sharpe_Stability",
        "DrawdownPenalty",
        "BreadthPenalty",
        "evaluation_ok",
        "error",
    ]
]

ga_top3_strategy_objects = [
    ga_build_strategy(solution_key) for solution_key in ga_top3_results.index
]

ga_top3_strategies = ga_top3_strategy_objects

print("TOP-3 strategies discovered by GA")
display(ga_top3_results_display)

print("Final generation ranking")
display(
    ga_final_population_scores[
        [
            "strategy_name",
            "selector_name",
            "signal_name",
            "optimizer_name",
            "TOTAL_SCORE",
            "TOTAL_SCORE_BASE",
            "TOTAL_PENALTY",
            *GA_SCORE_COMPONENT_COLUMNS,
        ]
    ].head(10)
)

if not ga_generation_report.empty:
    display(ga_generation_report)

    plt.figure(figsize=(10, 4))
    plt.plot(
        ga_generation_report["generation"],
        ga_generation_report["best_total_score"],
        marker="o",
        label="Лучший TOTAL_SCORE",
    )
    plt.plot(
        ga_generation_report["generation"],
        ga_generation_report["mean_total_score"],
        marker="o",
        label="Средний TOTAL_SCORE",
    )
    plt.xlabel("Поколение", fontname="Times New Roman", fontsize=12)
    plt.ylabel("TOTAL_SCORE (0..100)", fontname="Times New Roman", fontsize=12)
    plt.title(
        "Эволюция генетического алгоритма по метрике TOTAL_SCORE",
        fontname="Times New Roman",
        fontsize=12,
    )
    plt.xticks(fontname="Times New Roman", fontsize=12)
    plt.yticks(fontname="Times New Roman", fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.legend(prop={"family": "Times New Roman", "size": 12})
    plt.tight_layout()
    plt.show()

print("Top-3 strategy names:")
for idx, strategy in enumerate(ga_top3_strategy_objects, start=1):
    print(f"{idx}. {strategy.name}")
