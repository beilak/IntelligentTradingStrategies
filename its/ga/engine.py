from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any, Callable

import numpy as np
import pandas as pd
import pygad
from fastapi import HTTPException
from skfolio.model_selection import CombinatorialPurgedCV, WalkForward, cross_val_predict

from its.ga.materialization import materialize_top_strategies
from its.ga.registry import ALPHABET_GROUPS, build_component, load_gene_group
from its.strategies.core.types.strategy_types import Pipeline, Strategy
from its.strategies.testing.cpcv import annualized_factor, build_returns_matrix

ProgressCallback = Callable[[dict[str, Any]], None]

METRIC_FALLBACKS = {
    "WF_Return": -1.0,
    "WF_Calmar": -10.0,
    "Robustness_Delta": 1.0,
    "Sharpe_Stability": 1.0,
    "Daily_Risk_CVaR": 1.0,
    "CPCV_AnnRet_Median": -1.0,
    "WF_Max_Drawdown_Abs": 1.0,
    "WF_Mean_Active_Assets": 0.0,
    "WF_Min_Active_Assets": 0.0,
}

DEFAULT_SCORE_CONFIG = {
    "WF_Return": {"weight": 0.30, "direction": "higher", "bad": -0.10, "good": 0.25},
    "WF_Calmar": {"weight": 0.30, "direction": "higher", "bad": 0.00, "good": 1.50},
    "Robustness_Delta": {"weight": 0.20, "direction": "lower", "good": 0.00, "bad": 0.15},
    "Sharpe_Stability": {"weight": 0.20, "direction": "lower", "good": 0.00, "bad": 0.20},
}

DEFAULT_PENALTY_CONFIG = {
    "max_drawdown": {"threshold": 0.20, "hard": 0.35, "max_penalty": 25.0},
    "portfolio_breadth": {"threshold": 4.0, "hard": 1.0, "max_penalty": 15.0},
}


class GASearchRunner:
    def __init__(
        self,
        *,
        prices: pd.DataFrame,
        stocks: list[dict[str, Any]],
        settings: dict[str, Any],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        self.prices = prices
        self.stocks = stocks
        self.settings = settings
        self.progress_callback = progress_callback
        self.assets_info = pd.DataFrame(stocks)
        self.alphabets = {group: load_gene_group(group) for group in ALPHABET_GROUPS}
        self.selector_keys = [gene.id for gene in self.alphabets["pre_selection"]]
        self.signal_keys = [gene.id for gene in self.alphabets["signal"]]
        self.allocation_keys = [gene.id for gene in self.alphabets["allocation"]]
        self.raw_metric_cache: dict[tuple[int, int, int], dict[str, Any]] = {}
        self.generation_summaries: list[dict[str, Any]] = []
        self.population_scores: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        self.validate_alphabets()
        returns = build_returns_matrix(self.prices)
        x_train, x_test = self.split_returns(returns)
        self.x_train = x_train
        self.x_test = x_test

        sol_per_pop = int(self.settings.get("sol_per_pop", 8))
        num_parents_mating = int(self.settings.get("num_parents_mating", 4))
        num_generations = int(self.settings.get("num_generations", 10))
        if num_parents_mating > sol_per_pop:
            raise HTTPException(
                status_code=422,
                detail="num_parents_mating must be lower than or equal to sol_per_pop.",
            )

        ga_instance = pygad.GA(
            num_generations=num_generations,
            num_parents_mating=num_parents_mating,
            fitness_func=self.fitness_func,
            fitness_batch_size=sol_per_pop,
            sol_per_pop=sol_per_pop,
            num_genes=3,
            gene_space=[
                list(range(len(self.selector_keys))),
                list(range(len(self.signal_keys))),
                list(range(len(self.allocation_keys))),
            ],
            gene_type=int,
            parent_selection_type=self.settings.get("parent_selection_type", "tournament"),
            K_tournament=int(self.settings.get("k_tournament", 3)),
            keep_parents=int(self.settings.get("keep_parents", 0)),
            keep_elitism=int(self.settings.get("keep_elitism", 1)),
            crossover_type=self.settings.get("crossover_type", "uniform"),
            mutation_type=self.settings.get("mutation_type", "random"),
            mutation_probability=float(self.settings.get("mutation_probability", 0.25)),
            stop_criteria=self.settings.get("stop_criteria") or None,
            on_generation=self.on_generation,
            random_seed=int(self.settings.get("random_seed", 42)),
            suppress_warnings=True,
        )
        ga_instance.run()

        final_population = self.rank_population(ga_instance.population)
        all_scores = self.rank_all_evaluated()
        top_rows = rows_from_frame(all_scores.head(int(self.settings.get("top_n", 3))))
        materialized = []
        if self.settings.get("materialize_top", True) and top_rows:
            materialized = materialize_top_strategies(
                run_id=str(self.settings.get("run_id", "ga")),
                top_rows=top_rows,
                top_n=int(self.settings.get("top_n", 3)),
            )

        result = {
            "metadata": {
                "run_id": self.settings.get("run_id"),
                "test_name": self.settings.get("test_name", "ga_run"),
                "generated_at": datetime.now(UTC).isoformat(),
                "settings": self.settings,
                "search_space": self.search_space_size(),
                "evaluated_count": len(self.raw_metric_cache),
                "price_rows": len(returns),
                "train_period": period_payload(x_train),
                "test_period": period_payload(x_test),
                "asset_count": len(returns.columns),
                "assets": [
                    {
                        "figi": item.get("figi"),
                        "ticker": item.get("ticker"),
                        "name": item.get("name"),
                    }
                    for item in self.stocks
                    if item.get("ticker") in set(returns.columns)
                ],
            },
            "alphabets": {
                group: [gene.to_dict() for gene in genes]
                for group, genes in self.alphabets.items()
            },
            "generation_summaries": self.generation_summaries,
            "population_scores": self.population_scores,
            "final_population": rows_from_frame(final_population.head(20)),
            "all_evaluated": rows_from_frame(all_scores.head(50)),
            "top_strategies": top_rows,
            "materialized": materialized,
            "score_config": DEFAULT_SCORE_CONFIG,
            "penalty_config": DEFAULT_PENALTY_CONFIG,
        }
        self.emit({"type": "completed", "result": result})
        return result

    def validate_alphabets(self) -> None:
        empty = [group for group, genes in self.alphabets.items() if not genes]
        if empty:
            raise HTTPException(
                status_code=422,
                detail=f"GA alphabets are empty: {', '.join(empty)}.",
            )

    def split_returns(self, returns: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
        test_size = float(self.settings.get("test_size", 0.33))
        split_index = max(1, int(len(returns) * (1 - test_size)))
        min_test_rows = max(
            int(self.settings.get("cpcv_n_folds", 4)) + 1,
            int(self.settings.get("wf_train_size", 63)) + int(self.settings.get("wf_test_size", 21)) + 1,
        )
        if len(returns) - split_index < min_test_rows:
            split_index = max(1, len(returns) - min_test_rows)
        if split_index <= 0 or split_index >= len(returns) - 1:
            raise HTTPException(
                status_code=422,
                detail="Not enough rows to build GA train/test split.",
            )
        return returns.iloc[:split_index], returns.iloc[split_index:].copy()

    def fitness_func(self, ga_instance, solutions, solution_indices):
        scored_population = self.rank_population(ga_instance.population)
        ga_instance.ga_last_scored_population = scored_population.copy()
        batch = np.asarray(solutions, dtype=int)
        if batch.ndim == 1:
            return self.score_for_solution(scored_population, batch)
        return [self.score_for_solution(scored_population, solution) for solution in batch]

    def score_for_solution(self, scored_population: pd.DataFrame, solution) -> float:
        key = solution_key(solution)
        try:
            score = scored_population.at[key, "TOTAL_SCORE"]
        except KeyError:
            return -1.0
        return float(score) if np.isfinite(score) else -1.0

    def on_generation(self, ga_instance) -> None:
        scored_population = getattr(ga_instance, "ga_last_scored_population", None)
        if scored_population is None or scored_population.empty:
            scored_population = self.rank_population(ga_instance.population)

        best_row = scored_population.iloc[0]
        generation = int(ga_instance.generations_completed)
        summary = {
            "generation": generation,
            "best_total_score": safe_float(best_row["TOTAL_SCORE"]),
            "mean_total_score": safe_float(scored_population["TOTAL_SCORE"].mean()),
            "best_strategy_name": best_row["strategy_name"],
            "best_selector": best_row["selector_name"],
            "best_signal": best_row["signal_name"],
            "best_allocation": best_row["allocation_name"],
        }
        self.generation_summaries.append(summary)
        population_rows = rows_from_frame(scored_population.head(20))
        self.population_scores.append(
            {"generation": generation, "items": population_rows}
        )
        self.emit(
            {
                "type": "generation",
                "summary": summary,
                "population": population_rows,
            }
        )

    def rank_population(self, population) -> pd.DataFrame:
        population_array = np.asarray(population, dtype=int)
        if population_array.ndim == 1:
            population_array = population_array.reshape(1, -1)
        unique_keys = list(dict.fromkeys(solution_key(solution) for solution in population_array))
        for key in unique_keys:
            if key not in self.raw_metric_cache:
                self.raw_metric_cache[key] = self.evaluate_solution(key)
        raw_df = pd.DataFrame([self.raw_metric_cache[key] for key in unique_keys]).set_index(
            "solution_key",
            drop=False,
        )
        return compute_total_score(raw_df)

    def rank_all_evaluated(self) -> pd.DataFrame:
        if not self.raw_metric_cache:
            return pd.DataFrame()
        raw_df = pd.DataFrame(self.raw_metric_cache.values()).set_index(
            "solution_key",
            drop=False,
        )
        return compute_total_score(raw_df)

    def evaluate_solution(self, key: tuple[int, int, int]) -> dict[str, Any]:
        decoded = self.decode_solution(key)
        strategy = self.build_strategy(decoded)
        try:
            strategy.pipeline.fit(self.x_train)
            cpcv_population = cross_val_predict(
                strategy.pipeline,
                self.x_test,
                cv=CombinatorialPurgedCV(
                    n_folds=int(self.settings.get("cpcv_n_folds", 4)),
                    n_test_folds=int(self.settings.get("cpcv_n_test_folds", 2)),
                ),
                n_jobs=1,
                portfolio_params={
                    "annualized_factor": annualized_factor(
                        self.settings.get("interval", "CANDLE_INTERVAL_DAY")
                    ),
                    "tag": strategy.name,
                },
            )
            wf_population = cross_val_predict(
                strategy.pipeline,
                self.x_test,
                cv=WalkForward(
                    test_size=int(self.settings.get("wf_test_size", 21)),
                    train_size=int(self.settings.get("wf_train_size", 63)),
                    purged_size=int(self.settings.get("wf_purged_size", 5)),
                ),
                n_jobs=1,
                portfolio_params={
                    "annualized_factor": annualized_factor(
                        self.settings.get("interval", "CANDLE_INTERVAL_DAY")
                    ),
                    "tag": strategy.name,
                },
            )
            raw_metrics = self.extract_raw_metrics(cpcv_population, wf_population)
            return {
                **decoded,
                **raw_metrics,
                "evaluation_ok": True,
                "error": None,
            }
        except Exception as exc:
            return {
                **decoded,
                **METRIC_FALLBACKS,
                "evaluation_ok": False,
                "error": repr(exc),
            }

    def decode_solution(self, solution) -> dict[str, Any]:
        selector_idx, signal_idx, allocation_idx = solution_key(solution)
        selector_name = self.selector_keys[selector_idx]
        signal_name = self.signal_keys[signal_idx]
        allocation_name = self.allocation_keys[allocation_idx]
        strategy_name = f"[GA][{selector_name}][{signal_name}][{allocation_name}]"
        return {
            "solution_key": (selector_idx, signal_idx, allocation_idx),
            "selector_idx": selector_idx,
            "signal_idx": signal_idx,
            "allocation_idx": allocation_idx,
            "selector_name": selector_name,
            "signal_name": signal_name,
            "allocation_name": allocation_name,
            "strategy_name": strategy_name,
        }

    def build_strategy(self, decoded: dict[str, Any]) -> Strategy:
        selector = self.alphabets["pre_selection"][decoded["selector_idx"]]
        signal = self.alphabets["signal"][decoded["signal_idx"]]
        allocation = self.alphabets["allocation"][decoded["allocation_idx"]]
        return Strategy(
            name=decoded["strategy_name"],
            description="GA candidate strategy",
            pipeline=Pipeline(
                steps=[
                    (
                        "ga_pre_selection",
                        build_component(
                            selector,
                            asset_universe_prices=self.prices,
                            runtime_context=self.runtime_context(),
                        ),
                    ),
                    (
                        "ga_signal",
                        build_component(
                            signal,
                            asset_universe_prices=self.prices,
                            runtime_context=self.runtime_context(),
                        ),
                    ),
                    (
                        "ga_allocation",
                        build_component(
                            allocation,
                            asset_universe_prices=self.prices,
                            runtime_context=self.runtime_context(),
                        ),
                    ),
                ]
            ),
        )

    def runtime_context(self) -> dict[str, Any]:
        return {
            "asset_universe_prices": self.prices,
            "assets_info": self.assets_info,
        }

    def extract_raw_metrics(self, cpcv_population, wf_population) -> dict[str, float]:
        cpcv_finals = extract_path_final_returns(cpcv_population)
        wf_summary = summary_to_metrics(wf_population.summary())
        wf_return = metric_value(wf_summary, "Annualized Mean", "Mean")
        if wf_return is None:
            wf_finals = extract_path_final_returns(wf_population)
            wf_return = float(np.mean(wf_finals)) if wf_finals else None
        wf_calmar = metric_value(wf_summary, "Calmar Ratio")
        wf_cvar = metric_value(wf_summary, "CVaR at 95%")
        wf_drawdown = metric_value(wf_summary, "MAX Drawdown", "Max Drawdown")
        cpcv_ret_median = float(np.median(cpcv_finals)) if cpcv_finals else None
        cpcv_sharpe_std = float(np.std(cpcv_finals)) if cpcv_finals else None
        breadth = extract_portfolio_breadth_metrics(wf_population)
        return finalize_raw_metrics(
            {
                "WF_Return": wf_return,
                "WF_Calmar": wf_calmar,
                "Robustness_Delta": abs(cpcv_ret_median - wf_return)
                if cpcv_ret_median is not None and wf_return is not None
                else None,
                "Sharpe_Stability": cpcv_sharpe_std,
                "Daily_Risk_CVaR": wf_cvar,
                "CPCV_AnnRet_Median": cpcv_ret_median,
                "WF_Max_Drawdown_Abs": abs(wf_drawdown) if wf_drawdown is not None else None,
                **breadth,
            }
        )

    def search_space_size(self) -> int:
        return len(self.selector_keys) * len(self.signal_keys) * len(self.allocation_keys)

    def emit(self, payload: dict[str, Any]) -> None:
        if self.progress_callback is not None:
            self.progress_callback(payload)


def compute_total_score(raw_df: pd.DataFrame) -> pd.DataFrame:
    scored = raw_df.copy()
    for metric_name, fallback in METRIC_FALLBACKS.items():
        scored[metric_name] = (
            pd.to_numeric(scored[metric_name], errors="coerce")
            .replace([np.inf, -np.inf], np.nan)
            .fillna(fallback)
        )

    for metric_name, config in DEFAULT_SCORE_CONFIG.items():
        if config["direction"] == "higher":
            scored[f"{metric_name}_score"] = scored[metric_name].apply(
                lambda value: score_higher_better(value, config["bad"], config["good"])
            )
        else:
            scored[f"{metric_name}_score"] = scored[metric_name].apply(
                lambda value: score_lower_better(value, config["good"], config["bad"])
            )

    scored["TOTAL_SCORE_01"] = 0.0
    for metric_name, config in DEFAULT_SCORE_CONFIG.items():
        scored["TOTAL_SCORE_01"] += config["weight"] * scored[f"{metric_name}_score"]

    drawdown_config = DEFAULT_PENALTY_CONFIG["max_drawdown"]
    breadth_config = DEFAULT_PENALTY_CONFIG["portfolio_breadth"]
    scored["DrawdownPenalty"] = scored["WF_Max_Drawdown_Abs"].apply(
        lambda value: penalty_above_threshold(value, **drawdown_config)
    )
    scored["BreadthPenalty"] = scored["WF_Mean_Active_Assets"].apply(
        lambda value: penalty_below_threshold(value, **breadth_config)
    )
    scored["TOTAL_PENALTY"] = scored["DrawdownPenalty"] + scored["BreadthPenalty"]
    scored["TOTAL_SCORE_BASE"] = 100.0 * scored["TOTAL_SCORE_01"]
    scored["TOTAL_SCORE"] = (
        scored["TOTAL_SCORE_BASE"] - scored["TOTAL_PENALTY"]
    ).clip(lower=0.0)
    return scored.sort_values("TOTAL_SCORE", ascending=False)


def run_ga_search(
    *,
    prices: pd.DataFrame,
    stocks: list[dict[str, Any]],
    settings: dict[str, Any],
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    return GASearchRunner(
        prices=prices,
        stocks=stocks,
        settings=settings,
        progress_callback=progress_callback,
    ).run()


def solution_key(solution) -> tuple[int, int, int]:
    return tuple(int(value) for value in np.asarray(solution, dtype=int).tolist())


def finalize_raw_metrics(raw_metrics: dict[str, Any]) -> dict[str, float]:
    safe_metrics = {}
    for metric_name, metric_value in raw_metrics.items():
        value = safe_float(metric_value)
        safe_metrics[metric_name] = (
            METRIC_FALLBACKS.get(metric_name, 0.0) if value is None else value
        )
    return safe_metrics


def score_higher_better(value: float, bad: float, good: float) -> float:
    if not np.isfinite(value):
        return 0.0
    if math.isclose(good, bad):
        return 1.0 if value >= good else 0.0
    return clip_01((value - bad) / (good - bad))


def score_lower_better(value: float, good: float, bad: float) -> float:
    if not np.isfinite(value):
        return 0.0
    if math.isclose(good, bad):
        return 1.0 if value <= good else 0.0
    return clip_01((bad - value) / (bad - good))


def penalty_above_threshold(
    value: float,
    threshold: float,
    hard: float,
    max_penalty: float,
) -> float:
    if not np.isfinite(value):
        return float(max_penalty)
    if value <= threshold:
        return 0.0
    if value >= hard:
        return float(max_penalty)
    return float(max_penalty) * (value - threshold) / (hard - threshold)


def penalty_below_threshold(
    value: float,
    threshold: float,
    hard: float,
    max_penalty: float,
) -> float:
    if not np.isfinite(value):
        return float(max_penalty)
    if value >= threshold:
        return 0.0
    if value <= hard:
        return float(max_penalty)
    return float(max_penalty) * (threshold - value) / (threshold - hard)


def clip_01(value: float) -> float:
    return float(np.clip(value, 0.0, 1.0))


def safe_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def summary_to_metrics(summary: Any) -> dict[str, float | None]:
    if not isinstance(summary, pd.Series):
        summary = pd.Series(summary)
    return {str(index): safe_float(value) for index, value in summary.items()}


def metric_value(metrics: dict[str, float | None], *names: str) -> float | None:
    lower = {key.lower(): value for key, value in metrics.items()}
    for name in names:
        value = lower.get(name.lower())
        if value is not None:
            return value
    return None


def extract_path_final_returns(population: Any) -> list[float]:
    values = []
    for portfolio in population:
        cumulative = getattr(portfolio, "cumulative_returns_df", None)
        if cumulative is None:
            continue
        if callable(cumulative):
            cumulative = cumulative()
        if isinstance(cumulative, pd.DataFrame):
            series = cumulative.iloc[:, 0] if len(cumulative.columns) else pd.Series()
        else:
            series = pd.Series(cumulative)
        if series.empty:
            continue
        value = safe_float(series.dropna().iloc[-1])
        if value is not None:
            values.append(value)
    return values


def extract_portfolio_breadth_metrics(population: Any) -> dict[str, float]:
    try:
        weights = getattr(population, "weights_per_observation", None)
        if weights is None:
            return {"WF_Mean_Active_Assets": 0.0, "WF_Min_Active_Assets": 0.0}
        if not isinstance(weights, pd.DataFrame):
            weights = pd.DataFrame(weights)
        if weights.empty:
            return {"WF_Mean_Active_Assets": 0.0, "WF_Min_Active_Assets": 0.0}
        active_counts = weights.abs().gt(1e-8).sum(axis=1).astype(float)
        if active_counts.empty:
            return {"WF_Mean_Active_Assets": 0.0, "WF_Min_Active_Assets": 0.0}
        return {
            "WF_Mean_Active_Assets": float(active_counts.mean()),
            "WF_Min_Active_Assets": float(active_counts.min()),
        }
    except Exception:
        return {"WF_Mean_Active_Assets": 0.0, "WF_Min_Active_Assets": 0.0}


def rows_from_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows = []
    if frame.empty:
        return rows
    for _, row in frame.reset_index(drop=True).iterrows():
        item = {}
        for key, value in row.items():
            item[str(key)] = json_safe(value)
        rows.append(item)
    return rows


def json_safe(value: Any) -> Any:
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def period_payload(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "start": frame.index.min().isoformat() if len(frame) else "",
        "end": frame.index.max().isoformat() if len(frame) else "",
        "rows": len(frame),
    }
