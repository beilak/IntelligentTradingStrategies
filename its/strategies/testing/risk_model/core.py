from __future__ import annotations

import json
import math
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import HTTPException

from its.strategies.testing.cpcv import (
    build_returns_matrix,
    load_registered_model,
    safe_float,
    safe_name,
    timestamp_to_string,
)

CACHE_DIR = Path(
    os.getenv("STRATEGY_RISK_MODEL_CACHE_DIR", "/app/its/data/strategy_tests/risk_model")
)

RISK_MODEL_DEFINITIONS: dict[str, dict[str, str]] = {
    "monte_carlo": {
        "id": "monte_carlo",
        "title": "Monte Carlo",
        "metric": "VaR/CVaR",
        "engine": "monte_carlo",
    },
    "qae": {
        "id": "qae",
        "title": "QAE (Quantum Amplitude Estimation)",
        "metric": "VaR/CVaR",
        "engine": "qae_style_discrete",
    },
}

RISK_MODEL_ALIASES = {
    "monte_carlo_var": "monte_carlo",
    "monte_carlo_cvar": "monte_carlo",
    "qae_var": "qae",
    "qae_cvar": "qae",
}


def list_risk_models() -> list[dict[str, str]]:
    return list(RISK_MODEL_DEFINITIONS.values())


def generate_risk_model_report(
    model_name: str,
    risk_model: str,
    stocks: list[dict[str, Any]],
    prices: pd.DataFrame,
    settings: dict[str, Any],
    dividends_info: pd.DataFrame | None = None,
) -> dict[str, Any]:
    definition = risk_model_definition(risk_model)
    model_cls = load_registered_model(model_name)
    if prices.empty:
        raise HTTPException(status_code=404, detail="No prices found for Risk Models.")

    returns = build_returns_matrix(prices)
    if len(returns) < 4:
        raise HTTPException(
            status_code=422,
            detail="Not enough price rows for selected Risk Model settings.",
        )

    x_train, x_test = split_returns_for_risk(returns, settings)
    strategy = model_cls(
        prices,
        pd.DataFrame(stocks),
        _dividends_info=dividends_info,
    ).build()
    strategy.pipeline.fit(x_train)

    portfolio = predict_portfolio(strategy.pipeline, x_test)
    weights = extract_portfolio_weights(portfolio, x_test)
    aligned_returns, aligned_weights, weight_records = align_returns_and_weights(
        x_test,
        weights,
        stocks,
    )

    scenario_result = simulate_portfolio_scenarios(
        returns=aligned_returns,
        weights=aligned_weights,
        portfolio_value=float(settings.get("portfolio_value", 1_000_000.0)),
        n_simulations=int(settings.get("n_simulations", 50_000)),
        horizon_days=int(settings.get("horizon_days", 1)),
        method=str(settings.get("simulation_method", "historical_bootstrap")),
        random_state=int(settings.get("random_state", 42)),
        path_count=int(settings.get("path_count", 80)),
    )
    losses = scenario_result["losses"]
    confidence_level = float(settings.get("confidence_level", 0.95))
    metrics = calculate_loss_metrics(
        losses,
        confidence_level=confidence_level,
        portfolio_value=float(settings.get("portfolio_value", 1_000_000.0)),
    )
    qae_metrics: dict[str, Any] | None = None
    qae_distribution: dict[str, Any] | None = None
    if definition["engine"] == "qae_style_discrete":
        qae_distribution = discretize_losses(
            losses,
            n_buckets=int(settings.get("n_buckets", 64)),
        )
        qae_metrics = calculate_qae_style_metrics(
            qae_distribution,
            confidence_level=confidence_level,
            reference_metrics=metrics,
        )

    primary_metrics = qae_metrics if qae_metrics is not None else metrics
    var_threshold = float(primary_metrics["var"])
    cvar_threshold = float(primary_metrics["cvar"])

    return {
        "metadata": {
            "model_name": model_name,
            "strategy_name": strategy.name,
            "strategy_description": strategy.description,
            "test_name": settings.get("test_name", ""),
            "test_type": "RiskModel",
            "risk_model": definition["id"],
            "risk_model_title": definition["title"],
            "engine": definition["engine"],
            "generated_at": datetime.now(UTC).isoformat(),
            "settings": settings,
            "train_period": period_metadata(x_train),
            "test_period": period_metadata(x_test),
            "assets": [
                {
                    "figi": item.get("figi"),
                    "ticker": item.get("ticker"),
                    "name": item.get("name"),
                    "sector": item.get("sector"),
                }
                for item in stocks
                if item.get("ticker") in set(aligned_returns.columns)
            ],
            "asset_count": len(aligned_returns.columns),
            "scenario_count": len(losses),
            "confidence_level": confidence_level,
            "horizon_days": int(settings.get("horizon_days", 1)),
        },
        "summary": build_summary_rows(
            risk_model,
            primary_metrics,
            metrics,
            qae_metrics,
            settings,
        ),
        "report": build_report_rows(primary_metrics, metrics, qae_metrics, settings),
        "portfolio_weights": weight_records,
        "loss_distribution": build_loss_distribution(losses, var_threshold),
        "cumulative_distribution": build_cumulative_distribution(losses),
        "simulated_paths": scenario_result["simulated_paths"],
        "historical_portfolio_curve": build_historical_portfolio_curve(
            aligned_returns,
            aligned_weights,
            float(settings.get("portfolio_value", 1_000_000.0)),
        ),
        "qae_distribution": qae_distribution,
        "qae": qae_metrics,
        "reference": metrics if qae_metrics is not None else None,
        "interpretation": risk_interpretation(
            definition["title"],
            confidence_level,
            var_threshold,
            cvar_threshold,
            float(settings.get("portfolio_value", 1_000_000.0)),
        ),
    }


def risk_model_definition(risk_model: str) -> dict[str, str]:
    risk_model = RISK_MODEL_ALIASES.get(risk_model, risk_model)
    definition = RISK_MODEL_DEFINITIONS.get(risk_model)
    if definition is None:
        raise HTTPException(status_code=404, detail="Risk model is not registered.")
    return definition


def split_returns_for_risk(
    returns: pd.DataFrame, settings: dict[str, Any]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    test_size = float(settings.get("test_size", 0.33))
    split_index = max(1, int(len(returns) * (1 - test_size)))
    if split_index >= len(returns) - 1:
        split_index = max(1, len(returns) - 2)
    if split_index <= 0:
        raise HTTPException(
            status_code=422,
            detail="Not enough rows to build train/test split.",
        )
    x_train = returns.iloc[:split_index]
    x_test = returns.iloc[split_index:].copy()
    if len(x_test) < 2:
        raise HTTPException(
            status_code=422,
            detail="Not enough test rows for Risk Model simulation.",
        )
    return x_train, x_test


def predict_portfolio(pipeline: Any, x_test: pd.DataFrame) -> Any:
    prediction = pipeline.predict(x_test)
    if hasattr(prediction, "weights_dict"):
        return prediction
    try:
        iterator = iter(prediction)
        portfolio = next(iterator)
    except (TypeError, StopIteration) as exc:
        raise HTTPException(
            status_code=422,
            detail="Strategy pipeline did not produce a portfolio with weights.",
        ) from exc
    if not hasattr(portfolio, "weights_dict"):
        raise HTTPException(
            status_code=422,
            detail="Strategy prediction does not expose portfolio weights.",
        )
    return portfolio


def extract_portfolio_weights(portfolio: Any, x_test: pd.DataFrame) -> dict[str, float]:
    weights_dict = getattr(portfolio, "weights_dict", None)
    if isinstance(weights_dict, dict) and weights_dict:
        weights = {
            str(asset): float(weight)
            for asset, weight in weights_dict.items()
            if safe_float(weight) is not None
        }
        if weights:
            return weights

    weights = getattr(portfolio, "weights", None)
    assets = getattr(portfolio, "assets", None)
    if weights is None:
        raise HTTPException(
            status_code=422,
            detail="Portfolio does not expose weights.",
        )
    weights_array = np.asarray(weights, dtype=float).reshape(-1)
    asset_names = list(assets) if assets is not None else list(x_test.columns)
    if len(asset_names) != len(weights_array):
        raise HTTPException(
            status_code=422,
            detail="Portfolio weights cannot be aligned with asset names.",
        )
    return {
        str(asset): float(weight)
        for asset, weight in zip(asset_names, weights_array, strict=True)
        if safe_float(weight) is not None
    }


def align_returns_and_weights(
    returns: pd.DataFrame,
    weights: dict[str, float],
    stocks: list[dict[str, Any]],
) -> tuple[pd.DataFrame, np.ndarray, list[dict[str, Any]]]:
    stock_by_ticker = {
        str(item.get("ticker")): item for item in stocks if item.get("ticker")
    }
    clean_weights = {
        ticker: weight
        for ticker, weight in weights.items()
        if ticker in returns.columns and abs(weight) > 1e-12
    }
    if not clean_weights:
        raise HTTPException(
            status_code=422,
            detail="Risk Model portfolio has no non-zero weights in price data.",
        )

    aligned = returns.loc[:, list(clean_weights)].copy()
    weight_array = np.asarray(list(clean_weights.values()), dtype=float)
    total = weight_array.sum()
    if not np.isfinite(total) or abs(total) < 1e-12:
        total = np.abs(weight_array).sum()
    if not np.isfinite(total) or abs(total) < 1e-12:
        raise HTTPException(
            status_code=422,
            detail="Risk Model portfolio weights cannot be normalized.",
        )
    weight_array = weight_array / total

    records = []
    for ticker, weight in zip(aligned.columns, weight_array, strict=True):
        stock = stock_by_ticker.get(str(ticker), {})
        records.append(
            {
                "ticker": str(ticker),
                "weight": float(weight),
                "figi": stock.get("figi"),
                "name": stock.get("name"),
                "sector": stock.get("sector"),
            }
        )
    records.sort(key=lambda item: abs(item["weight"]), reverse=True)
    return aligned, weight_array, records


def simulate_portfolio_losses(
    *,
    returns: pd.DataFrame,
    weights: np.ndarray,
    portfolio_value: float,
    n_simulations: int,
    horizon_days: int,
    method: str,
    random_state: int,
) -> np.ndarray:
    return simulate_portfolio_scenarios(
        returns=returns,
        weights=weights,
        portfolio_value=portfolio_value,
        n_simulations=n_simulations,
        horizon_days=horizon_days,
        method=method,
        random_state=random_state,
        path_count=0,
    )["losses"]


def simulate_portfolio_scenarios(
    *,
    returns: pd.DataFrame,
    weights: np.ndarray,
    portfolio_value: float,
    n_simulations: int,
    horizon_days: int,
    method: str,
    random_state: int,
    path_count: int = 80,
) -> dict[str, Any]:
    if n_simulations <= 0:
        raise HTTPException(status_code=422, detail="n_simulations must be positive.")
    if horizon_days <= 0:
        raise HTTPException(status_code=422, detail="horizon_days must be positive.")

    values = returns.to_numpy(dtype=float)
    if values.shape[0] < 2:
        raise HTTPException(
            status_code=422,
            detail="At least two return observations are required.",
        )
    rng = np.random.default_rng(random_state)
    if method == "historical_bootstrap":
        sampled = bootstrap_asset_returns(values, n_simulations, horizon_days, rng)
    elif method == "multivariate_normal":
        sampled = normal_asset_returns(values, n_simulations, horizon_days, rng)
    else:
        raise HTTPException(
            status_code=422,
            detail="simulation_method must be historical_bootstrap or multivariate_normal.",
        )

    horizon_asset_returns = np.prod(1 + sampled, axis=1) - 1
    portfolio_returns = horizon_asset_returns @ weights
    losses = -portfolio_returns * portfolio_value
    losses = losses[np.isfinite(losses)]
    if len(losses) == 0:
        raise HTTPException(status_code=422, detail="Risk simulation produced no losses.")
    daily_portfolio_returns = np.matmul(sampled, weights)
    path_values = build_simulated_path_values(
        daily_portfolio_returns,
        portfolio_value,
        max_paths=path_count,
    )
    return {
        "losses": losses,
        "simulated_paths": path_values,
    }


def build_simulated_path_values(
    daily_portfolio_returns: np.ndarray,
    portfolio_value: float,
    *,
    max_paths: int,
) -> dict[str, Any]:
    max_paths = max(0, min(int(max_paths), daily_portfolio_returns.shape[0], 200))
    if max_paths == 0:
        return {"name": "Simulated portfolio paths", "paths": []}

    selected_returns = daily_portfolio_returns[:max_paths]
    cumulative = np.cumprod(1 + selected_returns, axis=1) * portfolio_value
    with_start = np.concatenate(
        [
            np.full((selected_returns.shape[0], 1), portfolio_value, dtype=float),
            cumulative,
        ],
        axis=1,
    )
    paths = []
    for index, values in enumerate(with_start, start=1):
        finite_values = np.nan_to_num(values, nan=portfolio_value)
        paths.append(
            {
                "name": f"Scenario {index}",
                "final_value": float(finite_values[-1]),
                "points": [
                    {"x": int(step), "y": float(value)}
                    for step, value in enumerate(finite_values)
                ],
            }
        )
    return {"name": "Simulated portfolio paths", "paths": paths}


def bootstrap_asset_returns(
    returns: np.ndarray,
    n_simulations: int,
    horizon_days: int,
    rng: np.random.Generator,
) -> np.ndarray:
    indices = rng.integers(
        low=0,
        high=returns.shape[0],
        size=(n_simulations, horizon_days),
    )
    return returns[indices]


def normal_asset_returns(
    returns: np.ndarray,
    n_simulations: int,
    horizon_days: int,
    rng: np.random.Generator,
) -> np.ndarray:
    mean = np.nanmean(returns, axis=0)
    if returns.shape[1] == 1:
        std = float(np.nanstd(returns[:, 0], ddof=1))
        return rng.normal(
            loc=float(mean[0]),
            scale=std if np.isfinite(std) and std > 0 else 0.0,
            size=(n_simulations, horizon_days, 1),
        )
    cov = np.cov(returns.T)
    cov = np.nan_to_num(cov, nan=0.0, posinf=0.0, neginf=0.0)
    cov = cov + np.eye(cov.shape[0]) * 1e-12
    return rng.multivariate_normal(
        mean=mean,
        cov=cov,
        size=(n_simulations, horizon_days),
        check_valid="ignore",
    )


def calculate_loss_metrics(
    losses: np.ndarray,
    *,
    confidence_level: float,
    portfolio_value: float,
) -> dict[str, Any]:
    var = float(np.quantile(losses, confidence_level))
    tail_losses = losses[losses >= var]
    cvar = float(tail_losses.mean()) if len(tail_losses) else var
    return {
        "portfolio_value": portfolio_value,
        "var": var,
        "cvar": cvar,
        "var_pct": var / portfolio_value,
        "cvar_pct": cvar / portfolio_value,
        "expected_loss": float(losses.mean()),
        "loss_std": float(losses.std(ddof=1)) if len(losses) > 1 else 0.0,
        "probability_of_loss": float((losses > 0).mean()),
        "tail_probability": float((losses >= var).mean()),
        "tail_count": int((losses >= var).sum()),
        "worst_loss": float(losses.max()),
        "best_loss": float(losses.min()),
        "scenario_count": int(len(losses)),
    }


def discretize_losses(losses: np.ndarray, *, n_buckets: int) -> dict[str, Any]:
    if n_buckets < 2 or n_buckets & (n_buckets - 1):
        raise HTTPException(
            status_code=422,
            detail="n_buckets must be a power of two.",
        )
    hist, edges = np.histogram(losses, bins=n_buckets)
    total = int(hist.sum())
    if total == 0:
        raise HTTPException(
            status_code=422,
            detail="Loss distribution is empty after discretization.",
        )
    probabilities = hist.astype(float) / total
    bucket_losses = (edges[:-1] + edges[1:]) / 2
    return {
        "bucket_count": int(n_buckets),
        "qubits": int(math.log2(n_buckets)),
        "buckets": [
            {
                "bucket": int(index),
                "loss": float(loss),
                "probability": float(probability),
                "count": int(count),
            }
            for index, (loss, probability, count) in enumerate(
                zip(bucket_losses, probabilities, hist, strict=True)
            )
        ],
    }


def calculate_qae_style_metrics(
    distribution: dict[str, Any],
    *,
    confidence_level: float,
    reference_metrics: dict[str, Any],
) -> dict[str, Any]:
    buckets = distribution["buckets"]
    losses = np.asarray([bucket["loss"] for bucket in buckets], dtype=float)
    probabilities = np.asarray(
        [bucket["probability"] for bucket in buckets], dtype=float
    )
    order = np.argsort(losses)
    sorted_losses = losses[order]
    sorted_probabilities = probabilities[order]
    cdf = np.cumsum(sorted_probabilities)
    index = int(np.searchsorted(cdf, confidence_level, side="left"))
    index = min(index, len(sorted_losses) - 1)
    var = float(sorted_losses[index])
    tail_mask = losses >= var
    tail_probability = float(probabilities[tail_mask].sum())
    if tail_probability <= 0:
        cvar = var
        tail_expectation = var * tail_probability
    else:
        tail_expectation = float((probabilities[tail_mask] * losses[tail_mask]).sum())
        cvar = tail_expectation / tail_probability
    target_tail_probability = 1 - confidence_level
    return {
        "var": var,
        "cvar": float(cvar),
        "portfolio_value": reference_metrics["portfolio_value"],
        "var_pct": var / reference_metrics["portfolio_value"],
        "cvar_pct": cvar / reference_metrics["portfolio_value"],
        "expected_loss": reference_metrics["expected_loss"],
        "loss_std": reference_metrics["loss_std"],
        "probability_of_loss": reference_metrics["probability_of_loss"],
        "tail_probability": tail_probability,
        "target_tail_probability": target_tail_probability,
        "tail_probability_error": tail_probability - target_tail_probability,
        "tail_expectation": tail_expectation,
        "bucket_count": distribution["bucket_count"],
        "qubits": distribution["qubits"],
        "var_discretization_error": var - reference_metrics["var"],
        "cvar_discretization_error": cvar - reference_metrics["cvar"],
        "tail_count": reference_metrics["tail_count"],
        "worst_loss": reference_metrics["worst_loss"],
        "best_loss": reference_metrics["best_loss"],
        "scenario_count": reference_metrics["scenario_count"],
    }


def build_summary_rows(
    risk_model: str,
    primary_metrics: dict[str, Any],
    reference_metrics: dict[str, Any],
    qae_metrics: dict[str, Any] | None,
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        money_row("VaR", primary_metrics["var"]),
        percent_row("VaR % of Portfolio", primary_metrics["var_pct"]),
        money_row("CVaR", primary_metrics["cvar"]),
        percent_row("CVaR % of Portfolio", primary_metrics["cvar_pct"]),
        percent_row("Tail Probability", primary_metrics["tail_probability"]),
        number_row("Scenarios", primary_metrics["scenario_count"]),
    ]
    if qae_metrics is not None:
        rows.extend(
            [
                number_row("QAE Buckets", qae_metrics["bucket_count"]),
                number_row("QAE Qubits", qae_metrics["qubits"]),
                percent_row(
                    "QAE Tail Probability Error",
                    qae_metrics["tail_probability_error"],
                ),
                money_row("MC Reference VaR", reference_metrics["var"]),
                money_row("MC Reference CVaR", reference_metrics["cvar"]),
            ]
        )
    return rows + [
        number_row("Horizon Days", settings.get("horizon_days", 1)),
        number_row("Confidence Level", settings.get("confidence_level", 0.95)),
    ]


def build_report_rows(
    primary_metrics: dict[str, Any],
    reference_metrics: dict[str, Any],
    qae_metrics: dict[str, Any] | None,
    settings: dict[str, Any],
) -> list[dict[str, Any]]:
    rows = [
        money_row("Expected Loss", primary_metrics["expected_loss"]),
        money_row("Loss Standard Deviation", primary_metrics["loss_std"]),
        percent_row("Probability of Loss", primary_metrics["probability_of_loss"]),
        money_row("Worst Scenario Loss", primary_metrics["worst_loss"]),
        money_row("Best Scenario Loss", primary_metrics["best_loss"]),
        number_row("Tail Scenario Count", primary_metrics["tail_count"]),
        number_row("Simulation Method", settings.get("simulation_method", "")),
        number_row("Random State", settings.get("random_state", 42)),
    ]
    if qae_metrics is not None:
        rows.extend(
            [
                number_row("QAE Iterations", settings.get("qae_iterations", "")),
                number_row("QAE Shots", settings.get("qae_shots", "")),
                money_row("QAE Tail Expectation", qae_metrics["tail_expectation"]),
                money_row(
                    "VaR Discretization Error",
                    qae_metrics["var_discretization_error"],
                ),
                money_row(
                    "CVaR Discretization Error",
                    qae_metrics["cvar_discretization_error"],
                ),
            ]
        )
    return rows


def build_loss_distribution(losses: np.ndarray, var_threshold: float) -> dict[str, Any]:
    bin_count = max(16, min(80, int(math.sqrt(len(losses)))))
    hist, edges = np.histogram(losses, bins=bin_count)
    total = hist.sum() or 1
    centers = (edges[:-1] + edges[1:]) / 2
    cumulative = np.cumsum(hist) / total
    return {
        "name": "Loss Distribution",
        "var_threshold": var_threshold,
        "bins": [
            {
                "loss": float(loss),
                "probability": float(count / total),
                "count": int(count),
                "cumulative_probability": float(probability),
                "is_tail": bool(loss >= var_threshold),
            }
            for loss, count, probability in zip(centers, hist, cumulative, strict=True)
        ],
    }


def build_cumulative_distribution(losses: np.ndarray) -> dict[str, Any]:
    sorted_losses = np.sort(losses)
    if len(sorted_losses) > 260:
        indices = np.unique(
            np.linspace(0, len(sorted_losses) - 1, 260).round().astype(int)
        )
        sorted_losses = sorted_losses[indices]
        probabilities = indices / max(1, len(losses) - 1)
    else:
        probabilities = np.arange(len(sorted_losses)) / max(1, len(sorted_losses) - 1)
    return {
        "name": "Cumulative Loss Distribution",
        "points": [
            {"x": float(loss), "y": float(probability)}
            for loss, probability in zip(sorted_losses, probabilities, strict=True)
        ],
    }


def build_historical_portfolio_curve(
    returns: pd.DataFrame,
    weights: np.ndarray,
    portfolio_value: float,
) -> dict[str, Any]:
    portfolio_returns = returns @ weights
    value = (1 + portfolio_returns.fillna(0)).cumprod() * portfolio_value
    return {
        "name": "Historical Portfolio Value",
        "final_value": float(value.iloc[-1]) if not value.empty else None,
        "points": [
            {"time": timestamp_to_string(index), "value": float(item)}
            for index, item in value.items()
        ],
    }


def period_metadata(frame: pd.DataFrame) -> dict[str, Any]:
    return {
        "start": timestamp_to_string(frame.index.min()),
        "end": timestamp_to_string(frame.index.max()),
        "rows": len(frame),
    }


def risk_interpretation(
    title: str,
    confidence_level: float,
    var: float,
    cvar: float,
    portfolio_value: float,
) -> str:
    tail = 1 - confidence_level
    return (
        f"{title}: with confidence {confidence_level:.1%}, horizon loss is not "
        f"expected to exceed {format_money_value(var)}. In the worst {tail:.1%} "
        f"scenarios, average loss is {format_money_value(cvar)} "
        f"({cvar / portfolio_value:.2%} of portfolio value)."
    )


def money_row(metric: str, value: Any) -> dict[str, Any]:
    numeric = safe_float(value)
    return {
        "metric": metric,
        "value": format_money_value(numeric),
        "numeric_value": numeric,
    }


def percent_row(metric: str, value: Any) -> dict[str, Any]:
    numeric = safe_float(value)
    return {
        "metric": metric,
        "value": "" if numeric is None else f"{numeric:.2%}",
        "numeric_value": numeric,
    }


def number_row(metric: str, value: Any) -> dict[str, Any]:
    numeric = safe_float(value)
    if numeric is None:
        return {"metric": metric, "value": str(value), "numeric_value": None}
    if float(numeric).is_integer():
        value_text = f"{int(numeric)}"
    else:
        value_text = f"{numeric:.6g}"
    return {"metric": metric, "value": value_text, "numeric_value": numeric}


def format_money_value(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:,.2f}".replace(",", " ")


def list_test_paths(model_name: str, risk_model: str) -> list[Path]:
    prefix = f"{safe_name(model_name)}_{safe_name(risk_model)}_"
    suffix = "_risk_model.json"
    if not CACHE_DIR.exists():
        return []
    return sorted(
        path for path in CACHE_DIR.glob(f"{prefix}*{suffix}") if path.is_file()
    )


def read_test_summary(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    metadata = payload.get("metadata", {})
    return {
        "file_name": path.name,
        "test_name": metadata.get("test_name", path.stem),
        "model_name": metadata.get("model_name", ""),
        "risk_model": metadata.get("risk_model", ""),
        "risk_model_title": metadata.get("risk_model_title", ""),
        "generated_at": metadata.get("generated_at", ""),
        "settings": metadata.get("settings", {}),
        "train_period": metadata.get("train_period", {}),
        "test_period": metadata.get("test_period", {}),
        "asset_count": metadata.get("asset_count", 0),
        "scenario_count": metadata.get("scenario_count", 0),
    }


def read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=500, detail="Cached Risk Model file is invalid."
        ) from exc


def cache_path(model_name: str, risk_model: str, test_name: str) -> Path:
    return (
        CACHE_DIR
        / f"{safe_name(model_name)}_{safe_name(risk_model)}_{safe_name(test_name)}_risk_model.json"
    )


def safe_risk_model(value: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", value.strip().lower()).strip("_")
