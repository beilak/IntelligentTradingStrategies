from __future__ import annotations

import importlib
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from its.strategies.testing.backtest import (
    list_test_paths as list_backtest_paths,
    read_json as read_backtest_json,
)
from its.strategies.testing.cpcv import (
    list_test_paths as list_cpcv_paths,
    read_json as read_cpcv_json,
)
from its.strategies.testing.walk_forward import (
    list_test_paths as list_walk_forward_paths,
    read_json as read_walk_forward_json,
)


HIGHER_BETTER_BACKTEST = [
    "Total Return",
    "Sharpe Ratio",
    "Sortino Ratio",
    "Calmar Ratio",
    "Omega Ratio",
    "Win Rate [%]",
    "Profit Factor",
    "Expectancy",
]

LOWER_BETTER_BACKTEST = [
    "Max Drawdown",
    "Total Fees Paid",
]


def compare_latest_strategy_tests() -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    backtest_payloads: dict[str, dict[str, Any]] = {}

    for model_name in registered_model_names():
        latest = {
            "cpcv": latest_payload(model_name, list_cpcv_paths, read_cpcv_json),
            "walk_forward": latest_payload(
                model_name,
                list_walk_forward_paths,
                read_walk_forward_json,
            ),
            "backtesting": latest_payload(
                model_name,
                list_backtest_paths,
                read_backtest_json,
            ),
        }
        missing_tests = [name for name, item in latest.items() if item is None]
        if missing_tests:
            skipped.append({"model_name": model_name, "missing_tests": missing_tests})
            continue

        assert latest["cpcv"] is not None
        assert latest["walk_forward"] is not None
        assert latest["backtesting"] is not None
        row = build_model_row(
            model_name,
            latest["cpcv"]["payload"],
            latest["walk_forward"]["payload"],
            latest["backtesting"]["payload"],
            {
                test_type: latest_item["summary"]
                for test_type, latest_item in latest.items()
                if latest_item is not None
            },
        )
        if row.get("missing_metrics"):
            skipped.append(
                {
                    "model_name": model_name,
                    "missing_tests": [],
                    "missing_metrics": row["missing_metrics"],
                }
            )
            continue
        rows.append(row)
        backtest_payloads[model_name] = latest["backtesting"]["payload"]

    ranking_rows, backtest_winners = score_rows(rows, backtest_payloads)
    winner = ranking_rows[0] if ranking_rows else None
    return {
        "generated_at": datetime.now(UTC).isoformat(),
        "eligible_count": len(ranking_rows),
        "skipped": skipped,
        "winner": winner,
        "rows": ranking_rows,
        "backtest_winners": backtest_winners,
        "explanations": [
            "WF_Return: realized WalkForward return metric from the latest saved WF test.",
            "WF_Calmar: return efficiency relative to drawdown in WalkForward.",
            "Robustness_Delta: absolute gap between CPCV median return estimate and WF return.",
            "Sharpe_Stability: stability proxy from CPCV; lower is better.",
            "Backtest_Metric_Wins: number of VectorBT backtest metrics where the model is best.",
            "TOTAL_SCORE: aggregate rank score; higher is better.",
        ],
    }


def registered_model_names() -> list[str]:
    for name in sorted(sys.modules, reverse=True):
        if name == "its.strategies.models" or name.startswith("its.strategies.models."):
            del sys.modules[name]
    module = importlib.import_module("its.strategies.models")
    return list(getattr(module, "__all__", []))


def latest_payload(
    model_name: str,
    list_paths: Callable[[str], list[Path]],
    read_json: Callable[[Path], dict[str, Any]],
) -> dict[str, Any] | None:
    candidates = []
    for path in list_paths(model_name):
        payload = read_json(path)
        metadata = payload.get("metadata", {})
        generated_at = parse_datetime(metadata.get("generated_at"))
        candidates.append(
            {
                "path": path,
                "payload": payload,
                "generated_at": generated_at,
                "summary": {
                    "file_name": path.name,
                    "test_name": metadata.get("test_name", path.stem),
                    "generated_at": metadata.get("generated_at", ""),
                    "test_type": metadata.get("test_type", ""),
                    "settings": metadata.get("settings", {}),
                },
            }
        )
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            item["generated_at"] or datetime.fromtimestamp(item["path"].stat().st_mtime, UTC)
        ),
    )


def build_model_row(
    model_name: str,
    cpcv: dict[str, Any],
    walk_forward: dict[str, Any],
    backtest: dict[str, Any],
    latest_tests: dict[str, Any],
) -> dict[str, Any]:
    cpcv_metrics = rows_to_metrics(cpcv.get("report", []), cpcv.get("cv_summary", []))
    wf_metrics = rows_to_metrics(
        walk_forward.get("report", []),
        walk_forward.get("cv_summary", []),
    )
    backtest_metrics = rows_to_metrics(
        backtest.get("summary", []),
        backtest.get("report", []),
    )

    wf_return = metric_value(
        wf_metrics,
        "Annualized Mean",
        "Annualized Return",
        "Mean",
    )
    if wf_return is None:
        wf_return = nested_value(walk_forward, "oos_curve", "final_return")

    cpcv_return_median = metric_value(
        cpcv_metrics,
        "Ann. Ret (Median)",
        "Annualized Mean",
        "Annualized Return",
        "Mean",
    )
    if cpcv_return_median is None:
        cpcv_return_median = median_path_final_return(cpcv)

    sharpe_stability = metric_value(
        cpcv_metrics,
        "Sharpe Stability (Std)",
        "Sharpe Ratio Std",
        "Annualized Sharpe Ratio Std",
    )
    if sharpe_stability is None:
        sharpe_stability = std_path_final_return(cpcv)

    wf_calmar = metric_value(wf_metrics, "Calmar Ratio")
    wf_cvar = metric_value(wf_metrics, "CVaR at 95%")
    wf_max_drawdown = metric_value(wf_metrics, "MAX Drawdown", "Max Drawdown")
    backtest_total_return = metric_value(
        backtest_metrics,
        "Total Return",
        "Total Return [%]",
    )
    backtest_sharpe = metric_value(backtest_metrics, "Sharpe Ratio")
    backtest_calmar = metric_value(backtest_metrics, "Calmar Ratio")
    backtest_max_drawdown = metric_value(
        backtest_metrics,
        "Max Drawdown",
        "Max Drawdown [%]",
    )

    values = {
        "WF_Return": wf_return,
        "WF_Calmar": wf_calmar,
        "Robustness_Delta": abs(cpcv_return_median - wf_return)
        if cpcv_return_median is not None and wf_return is not None
        else None,
        "Sharpe_Stability": sharpe_stability,
        "Daily_Risk_CVaR": wf_cvar,
        "WF_Max_Drawdown": wf_max_drawdown,
        "Backtest_Total_Return": backtest_total_return,
        "Backtest_Sharpe": backtest_sharpe,
        "Backtest_Calmar": backtest_calmar,
        "Backtest_Max_Drawdown": backtest_max_drawdown,
    }
    required = ["WF_Return", "WF_Calmar", "Robustness_Delta", "Sharpe_Stability"]
    missing_metrics = [name for name in required if values[name] is None]

    return {
        "model_name": model_name,
        **values,
        "latest_tests": latest_tests,
        "missing_metrics": missing_metrics,
    }


def score_rows(
    rows: list[dict[str, Any]],
    backtest_payloads: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if not rows:
        return [], []
    frame = pd.DataFrame(rows).set_index("model_name")
    n = len(frame)
    frame["Rank_Efficiency"] = frame["WF_Calmar"].rank(ascending=False)
    frame["Rank_WF_Return"] = frame["WF_Return"].rank(ascending=False)
    frame["Rank_Robustness"] = frame["Robustness_Delta"].rank(ascending=True)
    frame["Rank_Stability"] = frame["Sharpe_Stability"].rank(ascending=True)

    backtest_wins, backtest_winners = compare_backtests(backtest_payloads)
    frame["Backtest_Metric_Wins"] = pd.Series(backtest_wins, dtype="float64").reindex(
        frame.index
    ).fillna(0)
    frame["TOTAL_SCORE"] = (
        (n - frame["Rank_Efficiency"] + 1)
        + (n - frame["Rank_WF_Return"] + 1)
        + (n - frame["Rank_Robustness"] + 1)
        + (n - frame["Rank_Stability"] + 1)
        + frame["Backtest_Metric_Wins"]
    )
    frame = frame.sort_values("TOTAL_SCORE", ascending=False)
    result_rows = []
    for rank, (model_name, row) in enumerate(frame.iterrows(), start=1):
        item = rows_by_name(rows)[model_name].copy()
        item.pop("missing_metrics", None)
        item.update(
            {
                "rank": rank,
                "Rank_Efficiency": safe_number(row["Rank_Efficiency"]),
                "Rank_WF_Return": safe_number(row["Rank_WF_Return"]),
                "Rank_Robustness": safe_number(row["Rank_Robustness"]),
                "Rank_Stability": safe_number(row["Rank_Stability"]),
                "Backtest_Metric_Wins": safe_number(row["Backtest_Metric_Wins"]),
                "TOTAL_SCORE": safe_number(row["TOTAL_SCORE"]),
            }
        )
        result_rows.append(item)
    return result_rows, backtest_winners


def compare_backtests(
    payloads: dict[str, dict[str, Any]],
) -> tuple[dict[str, int], list[dict[str, Any]]]:
    wins = {model_name: 0 for model_name in payloads}
    winners = []
    metrics_by_model = {
        model_name: rows_to_metrics(payload.get("summary", []), payload.get("report", []))
        for model_name, payload in payloads.items()
    }

    for metric in HIGHER_BETTER_BACKTEST:
        values = collect_metric_values(metrics_by_model, metric)
        if len(values) < 2:
            continue
        winner = max(values, key=values.get)
        wins[winner] += 1
        winners.append(
            {
                "metric": metric,
                "direction": "higher",
                "winner": winner,
                "value": safe_number(values[winner]),
            }
        )

    for metric in LOWER_BETTER_BACKTEST:
        values = collect_metric_values(metrics_by_model, metric)
        if len(values) < 2:
            continue
        winner = min(values, key=values.get)
        wins[winner] += 1
        winners.append(
            {
                "metric": metric,
                "direction": "lower",
                "winner": winner,
                "value": safe_number(values[winner]),
            }
        )
    return wins, winners


def collect_metric_values(
    metrics_by_model: dict[str, dict[str, float | None]],
    metric: str,
) -> dict[str, float]:
    values = {}
    for model_name, metrics in metrics_by_model.items():
        value = metric_value(metrics, metric)
        if value is not None:
            values[model_name] = value
    return values


def rows_by_name(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {row["model_name"]: row for row in rows}


def rows_to_metrics(*row_groups: list[dict[str, Any]]) -> dict[str, float | None]:
    metrics: dict[str, float | None] = {}
    for rows in row_groups:
        for row in rows:
            metric = row.get("metric")
            if not metric:
                continue
            metrics[str(metric)] = parse_number(
                row.get("numeric_value", row.get("value"))
            )
    return metrics


def metric_value(metrics: dict[str, float | None], *names: str) -> float | None:
    lower_map = {key.lower(): value for key, value in metrics.items()}
    for name in names:
        value = lower_map.get(name.lower())
        if value is not None:
            return value
    return None


def nested_value(payload: dict[str, Any], *keys: str) -> float | None:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return parse_number(value)


def median_path_final_return(payload: dict[str, Any]) -> float | None:
    values = [
        parse_number(path.get("final_return"))
        for path in payload.get("paths", [])
        if parse_number(path.get("final_return")) is not None
    ]
    if not values:
        return None
    return float(pd.Series(values).median())


def std_path_final_return(payload: dict[str, Any]) -> float | None:
    values = [
        parse_number(path.get("final_return"))
        for path in payload.get("paths", [])
        if parse_number(path.get("final_return")) is not None
    ]
    if len(values) < 2:
        return 0.0 if values else None
    return float(pd.Series(values).std())


def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, str):
        value = value.replace("%", "").replace(" ", "").replace(",", ".")
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def safe_number(value: Any) -> float | None:
    number = parse_number(value)
    return None if number is None else float(number)


def parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed
