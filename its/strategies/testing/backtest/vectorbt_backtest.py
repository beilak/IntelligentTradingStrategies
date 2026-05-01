from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    Optional,
    Tuple,
    Union,
)

import numpy as np
import pandas as pd
import vectorbt as vbt

from its.strategies_model.core.trading_strategy import PositionContext


@dataclass(frozen=True)
class BacktestResult:
    portfolio: "vbt.Portfolio"
    weights: pd.DataFrame
    order_prices: pd.DataFrame
    rebalance_dates: pd.Index
    execution_events: pd.DataFrame
    # refit_dates: pd.Index


def backtest_strategies_vectorbt(
    *,
    strategies: Union[Any, Iterable[Any], Mapping[str, Any]],
    prices: pd.DataFrame,
    rebalance_freq: Union[str, int],
    high: Optional[pd.DataFrame] = None,
    low: Optional[pd.DataFrame] = None,
    trading_start_date: str = None,
    # refit_freq: Optional[Union[str, int]] = None,
    # train_window: Optional[Union[str, int]] = None,
    rebalance_on: str = "last",
    # refit_on: str = "last",
    init_cash: float = 100_000.0,
    fees: float = 0.0,
    slippage: float = 0.0,
    freq: Optional[str] = None,
    seed: int = 42,
) -> Dict[str, BacktestResult]:
    """
    Parameters
    ----------
    strategies:
        Strategy object, list/tuple of strategies, or dict name -> strategy.
        Each strategy must have a .pipeline with .fit(X_train) and .predict(X_test)
        that returns an object with .weights_dict.
    prices:
        DataFrame of close prices; index is time, columns are tickers.
    rebalance_freq:
        Rebalancing frequency. Use pandas offset string (e.g., "M", "W", "5D")
        or an integer number of rows.
    refit_freq:
        Refitting frequency. Same format as rebalance_freq. If None, refits once
        before the first rebalance.
    train_window:
        Training window length. Use pandas offset string (e.g., "365D") or
        an integer number of rows. If None, uses expanding window.
    rebalance_on / refit_on:
        "first" or "last" date within each period when using offset strings.
    init_cash, fees, slippage:
        Passed to vectorbt Portfolio.
    freq:
        Optional frequency string for vectorbt. If None, inferred from prices.
    """

    prices = _validate_prices(prices)
    strategy_map = _normalize_strategies(strategies)

    rebalance_dates = _make_schedule(
        prices.loc[trading_start_date:].index, rebalance_freq, rebalance_on
    )
    if rebalance_dates.empty:
        raise ValueError(
            "No rebalance dates could be generated for the given prices and rebalance_freq."
        )

    # refit_dates = (
    #     _make_schedule(prices.loc[trading_start_date:].index, refit_freq, refit_on)
    #     if refit_freq is not None
    #     else pd.Index([rebalance_dates[0]])
    # )

    # if freq is None:
    #     freq = _infer_freq(prices.loc[trading_start_date:].index)

    results: Dict[str, BacktestResult] = {}

    for name, strat in strategy_map.items():
        weights, order_prices, execution_events = _build_order_plan(
            strat,
            prices,
            rebalance_dates,
            # refit_dates,
            # train_window=train_window,
            trading_start_date=trading_start_date,
            high=high,
            low=low,
        )

        pf = vbt.Portfolio.from_orders(
            prices.loc[trading_start_date:],
            size=weights,
            size_type="targetpercent",
            price=order_prices.loc[trading_start_date:],
            init_cash=init_cash,
            fees=fees,
            slippage=slippage,
            cash_sharing=True,
            group_by=True,
            freq=freq,
            seed=seed,
        )

        results[name] = BacktestResult(
            portfolio=pf,
            weights=weights,
            order_prices=order_prices,
            rebalance_dates=rebalance_dates,
            execution_events=execution_events,
            # refit_dates=refit_dates,
        )

    return results


def _normalize_strategies(
    strategies: Union[Any, Iterable[Any], Mapping[str, Any]],
) -> Dict[str, Any]:
    if isinstance(strategies, Mapping):
        return dict(strategies)

    if isinstance(strategies, (list, tuple, set)):
        result: Dict[str, Any] = {}
        for i, strat in enumerate(strategies, start=1):
            name = getattr(strat, "name", None) or f"strategy_{i}"
            result[name] = strat
        return result

    name = getattr(strategies, "name", None) or "strategy"
    return {name: strategies}


def _validate_prices(prices: pd.DataFrame) -> pd.DataFrame:
    if not isinstance(prices, pd.DataFrame):
        raise TypeError("prices must be a pandas DataFrame.")
    if prices.empty:
        raise ValueError("prices is empty.")
    if not prices.index.is_monotonic_increasing:
        prices = prices.sort_index()
    if prices.columns.duplicated().any():
        raise ValueError("prices has duplicated column names.")
    return prices


def _build_order_plan(
    strategy: Any,
    prices: pd.DataFrame,
    rebalance_dates: pd.Index,
    *,
    trading_start_date: str,
    high: Optional[pd.DataFrame] = None,
    low: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    core_strategy = getattr(strategy, "core", None)
    strategy_for_weights = core_strategy if core_strategy is not None else strategy
    weights = _build_weights(
        strategy_for_weights,
        prices,
        rebalance_dates,
        trading_start_date=trading_start_date,
    )

    if core_strategy is None or not hasattr(strategy, "evaluate_position"):
        return weights, prices.copy(), empty_execution_events()

    return _apply_position_exit_policy(
        strategy,
        weights,
        prices,
        rebalance_dates,
        trading_start_date=trading_start_date,
        high=high,
        low=low,
    )


# def _infer_freq(index: pd.Index) -> Optional[str]:
#     if isinstance(index, pd.DatetimeIndex):
#         return pd.infer_freq(index)
#     return None


def _make_schedule(index: pd.Index, freq: Union[str, int, None], on: str) -> pd.Index:
    if freq is None:
        return pd.Index([])

    if isinstance(freq, int):
        if freq <= 0:
            raise ValueError("freq must be a positive integer.")
        return index[::freq]

    if not isinstance(index, (pd.DatetimeIndex, pd.PeriodIndex)):
        raise TypeError("String freq requires a DatetimeIndex or PeriodIndex.")
    if on not in {"first", "last"}:
        raise ValueError("on must be 'first' or 'last'.")

    series = pd.Series(index=index, data=index)
    grouped = series.groupby(pd.Grouper(freq=freq))
    if on == "last":
        schedule = grouped.last()
    else:
        schedule = grouped.first()

    schedule = schedule.dropna()
    return pd.Index(schedule.values)


def _resolve_train_start(
    index: pd.Index,
    train_window: Optional[Union[str, int]],
    train_end: pd.Timestamp,
) -> pd.Timestamp:
    if train_window is None:
        return index[0]

    if isinstance(train_window, int):
        if train_window <= 0:
            raise ValueError("train_window must be a positive integer.")
        pos = index.get_indexer([train_end], method="pad")[0]
        start_pos = max(0, pos - train_window + 1)
        return index[start_pos]

    if not isinstance(index, (pd.DatetimeIndex, pd.PeriodIndex)):
        raise TypeError("String train_window requires a DatetimeIndex or PeriodIndex.")
    if isinstance(train_end, pd.Period):
        train_end = train_end.to_timestamp()
    offset = pd.tseries.frequencies.to_offset(train_window)
    return pd.Timestamp(train_end) - offset


def _build_weights(
    strategy: Any,
    prices: pd.DataFrame,
    rebalance_dates: pd.Index,
    *,
    trading_start_date: str,
) -> pd.DataFrame:
    weights = pd.DataFrame(
        index=prices.loc[trading_start_date:].index,
        columns=prices.columns,
        data=np.nan,
        dtype=float,
    )
    for rebalance_date in rebalance_dates:
        if trading_start_date > rebalance_date:
            continue

        train_prices = prices.loc[:rebalance_date].iloc[:-1]
        if train_prices.empty:
            continue

        train_end = train_prices.index[-1]
        _limit_pipeline_price_context(strategy, train_end)
        prices_close_returns_for_fit = train_prices.pct_change(fill_method=None).fillna(
            0
        )
        strategy.pipeline.fit(prices_close_returns_for_fit)

        prices_close_returns_for_test = train_prices.pct_change(
            fill_method=None
        ).fillna(0)
        ptf_stat = strategy.pipeline.predict(prices_close_returns_for_test)
        weights_dict = getattr(ptf_stat, "weights_dict", None)

        row = pd.Series(0.0, index=prices.columns)
        for ticker, weight in weights_dict.items():
            if ticker in row.index:
                row.loc[ticker] = float(weight)
        weights.loc[rebalance_date] = row

    return weights


def _apply_position_exit_policy(
    strategy: Any,
    weights: pd.DataFrame,
    prices: pd.DataFrame,
    rebalance_dates: pd.Index,
    *,
    trading_start_date: str,
    high: Optional[pd.DataFrame] = None,
    low: Optional[pd.DataFrame] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    managed_weights = weights.copy()
    order_prices = prices.copy()
    events: List[Dict[str, Any]] = []
    trading_index = prices.loc[trading_start_date:].index

    for index, rebalance_date in enumerate(rebalance_dates):
        if rebalance_date not in managed_weights.index:
            continue

        current_weights = managed_weights.loc[rebalance_date].fillna(0.0)
        if current_weights.empty:
            continue

        next_rebalance = (
            rebalance_dates[index + 1] if index + 1 < len(rebalance_dates) else None
        )
        period_index = trading_index[trading_index > rebalance_date]
        if next_rebalance is not None:
            period_index = period_index[period_index < next_rebalance]

        for ticker, weight in current_weights.items():
            if not np.isfinite(weight) or weight <= 1e-12:
                continue
            if ticker not in prices.columns:
                continue

            entry_price = _matrix_value(prices, rebalance_date, ticker)
            if not _is_finite_positive(entry_price):
                continue

            for current_date in period_index:
                current_price = _matrix_value(prices, current_date, ticker)
                if not _is_finite_positive(current_price):
                    continue

                context = PositionContext(
                    ticker=str(ticker),
                    entry_time=pd.Timestamp(rebalance_date),
                    current_time=pd.Timestamp(current_date),
                    entry_price=float(entry_price),
                    current_price=float(current_price),
                    high_price=_matrix_value(high, current_date, ticker),
                    low_price=_matrix_value(low, current_date, ticker),
                    weight=float(weight),
                )
                decision = strategy.evaluate_position(context)
                if decision is None:
                    continue

                managed_weights.loc[current_date, ticker] = 0.0
                order_prices.loc[current_date, ticker] = decision.execution_price
                events.append(
                    {
                        "time": current_date,
                        "ticker": str(ticker),
                        "reason": decision.reason,
                        "entry_time": rebalance_date,
                        "entry_price": float(entry_price),
                        "execution_price": float(decision.execution_price),
                        "threshold_price": float(decision.threshold_price),
                        "return_pct": float(decision.return_pct),
                        "weight": float(weight),
                    }
                )
                break

    if not events:
        return managed_weights, order_prices, empty_execution_events()

    return managed_weights, order_prices, pd.DataFrame(events)


def empty_execution_events() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "time",
            "ticker",
            "reason",
            "entry_time",
            "entry_price",
            "execution_price",
            "threshold_price",
            "return_pct",
            "weight",
        ]
    )


def _matrix_value(
    matrix: Optional[pd.DataFrame],
    index: Any,
    column: Any,
) -> float | None:
    if matrix is None or column not in matrix.columns or index not in matrix.index:
        return None
    value = matrix.loc[index, column]
    if pd.isna(value):
        return None
    return float(value)


def _is_finite_positive(value: float | None) -> bool:
    return value is not None and np.isfinite(value) and value > 0


def _limit_pipeline_price_context(strategy: Any, train_end: pd.Timestamp) -> None:
    pipeline = getattr(strategy, "pipeline", None)
    steps = getattr(pipeline, "steps", [])
    for _, step in steps:
        prices = getattr(step, "asset_universe_prices", None)
        if isinstance(prices, pd.DataFrame) and "time" in prices.columns:
            limited = prices.copy()
            limited["time"] = pd.to_datetime(limited["time"], errors="coerce")
            step.asset_universe_prices = limited.loc[
                limited["time"] <= train_end
            ].copy()
