from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

import numpy as np
import pandas as pd

DriftMode = Literal["historical", "zero"]

MAX_SIMULATION_STEPS = 1_000


@dataclass(frozen=True)
class MonteCarloResult:
    actual: pd.DataFrame
    training: pd.DataFrame
    paths: pd.DataFrame
    meta: dict[str, object]


def build_close_price_monte_carlo(
    prices_df: pd.DataFrame,
    *,
    train_until: date | datetime | pd.Timestamp,
    simulation_end: date | datetime | pd.Timestamp,
    path_count: int = 100,
    seed: int | None = 42,
    volatility_scale: float = 1.0,
    drift_mode: DriftMode = "historical",
    interval: str | None = None,
) -> MonteCarloResult:
    if path_count < 1:
        raise ValueError("path_count must be at least 1.")
    if volatility_scale < 0:
        raise ValueError("volatility_scale must be greater than or equal to 0.")
    if drift_mode not in {"historical", "zero"}:
        raise ValueError("drift_mode must be historical or zero.")

    prices = prepare_close_prices(prices_df)
    if prices.empty:
        raise ValueError("No close prices found for Monte Carlo simulation.")

    train_until_ts = _coerce_boundary(train_until, end_of_day=True)
    simulation_end_ts = _coerce_boundary(simulation_end, end_of_day=True)
    if train_until_ts >= simulation_end_ts:
        raise ValueError("train_until must be before simulation_end.")

    training = prices.loc[prices["time"] <= train_until_ts].copy()
    if len(training) < 2:
        raise ValueError("At least two training close prices are required.")

    anchor = training.iloc[-1]
    anchor_time = pd.Timestamp(anchor["time"])
    anchor_close = float(anchor["close"])
    if anchor_close <= 0:
        raise ValueError("The last training close price must be greater than 0.")

    returns = np.log(training["close"] / training["close"].shift(1)).dropna()
    returns = returns.replace([np.inf, -np.inf], np.nan).dropna()
    if returns.empty:
        raise ValueError("At least one valid training return is required.")

    mean_return = float(returns.mean())
    volatility = float(returns.std(ddof=1)) if len(returns) > 1 else 0.0
    scaled_volatility = volatility * volatility_scale
    drift = mean_return if drift_mode == "historical" else 0.0

    simulation_times = build_simulation_times(
        prices=prices,
        anchor_time=anchor_time,
        simulation_end=simulation_end_ts,
        interval=interval,
    )
    if not simulation_times:
        raise ValueError("No simulation dates were produced for the requested range.")
    if len(simulation_times) > MAX_SIMULATION_STEPS:
        raise ValueError(
            f"Simulation range produced {len(simulation_times)} steps; "
            f"maximum supported is {MAX_SIMULATION_STEPS}."
        )

    paths = simulate_paths(
        anchor_time=anchor_time,
        anchor_close=anchor_close,
        simulation_times=simulation_times,
        path_count=path_count,
        drift=drift,
        volatility=scaled_volatility,
        seed=seed,
    )

    return MonteCarloResult(
        actual=prices,
        training=training,
        paths=paths,
        meta={
            "model": "close_log_return_monte_carlo",
            "train_until": anchor_time.isoformat(),
            "simulation_end": simulation_times[-1].isoformat(),
            "path_count": path_count,
            "simulation_steps": len(simulation_times),
            "training_points": int(len(training)),
            "anchor_close": anchor_close,
            "mean_log_return": mean_return,
            "volatility": volatility,
            "volatility_scale": volatility_scale,
            "scaled_volatility": scaled_volatility,
            "drift": drift,
            "drift_mode": drift_mode,
            "seed": seed,
        },
    )


def prepare_close_prices(prices_df: pd.DataFrame) -> pd.DataFrame:
    required_columns = {"time", "close"}
    missing_columns = required_columns.difference(prices_df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"prices_df is missing required columns: {missing}.")

    optional_columns = [column for column in ["figi", "ticker"] if column in prices_df]
    prepared = prices_df.loc[:, ["time", "close", *optional_columns]].copy()
    prepared["time"] = pd.to_datetime(prepared["time"], errors="coerce", utc=True)
    prepared["time"] = prepared["time"].dt.tz_convert(None)
    prepared["close"] = pd.to_numeric(prepared["close"], errors="coerce")
    prepared = prepared.dropna(subset=["time", "close"])
    prepared = prepared.loc[prepared["close"] > 0].copy()
    if prepared.empty:
        return pd.DataFrame(columns=["time", "close", *optional_columns])

    return (
        prepared.sort_values("time")
        .drop_duplicates(subset=["time"], keep="last")
        .reset_index(drop=True)
    )


def build_simulation_times(
    *,
    prices: pd.DataFrame,
    anchor_time: pd.Timestamp,
    simulation_end: pd.Timestamp,
    interval: str | None,
) -> list[pd.Timestamp]:
    known_times = prices.loc[
        (prices["time"] > anchor_time) & (prices["time"] <= simulation_end), "time"
    ].tolist()
    simulation_times = [pd.Timestamp(value) for value in known_times]

    last_time = simulation_times[-1] if simulation_times else anchor_time
    if last_time >= simulation_end:
        return simulation_times

    step = infer_time_step(prices["time"], interval)
    current = add_step(last_time, step)
    while current <= simulation_end:
        simulation_times.append(pd.Timestamp(current))
        if len(simulation_times) > MAX_SIMULATION_STEPS:
            break
        current = add_step(pd.Timestamp(current), step)

    return simulation_times


def simulate_paths(
    *,
    anchor_time: pd.Timestamp,
    anchor_close: float,
    simulation_times: list[pd.Timestamp],
    path_count: int,
    drift: float,
    volatility: float,
    seed: int | None,
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    shocks = rng.normal(
        loc=drift,
        scale=volatility,
        size=(path_count, len(simulation_times)),
    )
    cumulative = np.cumprod(np.exp(shocks), axis=1)
    simulated = anchor_close * cumulative

    rows: list[dict[str, object]] = []
    for path_index in range(path_count):
        path_id = path_index + 1
        rows.append(
            {
                "path_id": path_id,
                "time": anchor_time,
                "close": anchor_close,
                "step": 0,
            }
        )
        for step, (timestamp, close) in enumerate(
            zip(simulation_times, simulated[path_index], strict=True),
            start=1,
        ):
            rows.append(
                {
                    "path_id": path_id,
                    "time": timestamp,
                    "close": float(close),
                    "step": step,
                }
            )

    return pd.DataFrame(rows)


def infer_time_step(
    times: pd.Series,
    interval: str | None,
) -> pd.Timedelta | pd.DateOffset:
    normalized_interval = (interval or "").strip().upper()
    if normalized_interval == "CANDLE_INTERVAL_1_MIN":
        return pd.Timedelta(minutes=1)
    if normalized_interval == "CANDLE_INTERVAL_5_MIN":
        return pd.Timedelta(minutes=5)
    if normalized_interval == "CANDLE_INTERVAL_15_MIN":
        return pd.Timedelta(minutes=15)
    if normalized_interval == "CANDLE_INTERVAL_HOUR":
        return pd.Timedelta(hours=1)
    if normalized_interval == "CANDLE_INTERVAL_DAY":
        return pd.offsets.BDay(1)
    if normalized_interval == "CANDLE_INTERVAL_WEEK":
        return pd.DateOffset(weeks=1)
    if normalized_interval == "CANDLE_INTERVAL_MONTH":
        return pd.DateOffset(months=1)

    deltas = times.sort_values().diff().dropna()
    positive_deltas = deltas.loc[deltas > pd.Timedelta(0)]
    if positive_deltas.empty:
        return pd.Timedelta(days=1)

    return positive_deltas.median()


def add_step(
    timestamp: pd.Timestamp,
    step: pd.Timedelta | pd.DateOffset,
) -> pd.Timestamp:
    return pd.Timestamp(timestamp + step)


def _coerce_boundary(
    value: date | datetime | pd.Timestamp,
    *,
    end_of_day: bool,
) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is not None:
        timestamp = timestamp.tz_convert("UTC").tz_localize(None)

    if isinstance(value, date) and not isinstance(value, datetime) and end_of_day:
        return timestamp + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)

    return timestamp
