from __future__ import annotations

from dataclasses import dataclass
from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Mapping,
    MutableMapping,
    Optional,
    Tuple,
    Union,
)

import numpy as np
import pandas as pd
import vectorbt as vbt


@dataclass(frozen=True)
class BacktestResult:
    portfolio: "vbt.Portfolio"
    weights: pd.DataFrame
    rebalance_dates: pd.Index
    # refit_dates: pd.Index


def backtest_strategies_vectorbt(
    *,
    strategies: Union[Any, Iterable[Any], Mapping[str, Any]],
    prices: pd.DataFrame,
    rebalance_freq: Union[str, int],
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
        weights = _build_weights(
            strat,
            prices,
            rebalance_dates,
            # refit_dates,
            # train_window=train_window,
            trading_start_date=trading_start_date,
        )

        pf = vbt.Portfolio.from_orders(
            prices.loc[trading_start_date:],
            size=weights,
            size_type="targetpercent",
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
            rebalance_dates=rebalance_dates,
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
    last_fit_date: Optional[pd.Timestamp] = None

    for rebalance_date in rebalance_dates:
        if trading_start_date > rebalance_date:
            continue

        train_prices = prices.loc[:rebalance_date].iloc[:-1]
        if train_prices.empty:
            continue

        train_end = train_prices.index[-1]
        _limit_pipeline_price_context(strategy, train_end)
        prices_close_returns_for_fit = train_prices.pct_change(fill_method=None).fillna(0)
        strategy.pipeline.fit(prices_close_returns_for_fit)

        prices_close_returns_for_test = train_prices.pct_change(fill_method=None).fillna(0)
        ptf_stat = strategy.pipeline.predict(prices_close_returns_for_test)
        weights_dict = getattr(ptf_stat, "weights_dict", None)

        row = pd.Series(0.0, index=prices.columns)
        for ticker, weight in weights_dict.items():
            if ticker in row.index:
                row.loc[ticker] = float(weight)
        weights.loc[rebalance_date] = row

    return weights


def _limit_pipeline_price_context(strategy: Any, train_end: pd.Timestamp) -> None:
    pipeline = getattr(strategy, "pipeline", None)
    steps = getattr(pipeline, "steps", [])
    for _, step in steps:
        prices = getattr(step, "asset_universe_prices", None)
        if isinstance(prices, pd.DataFrame) and "time" in prices.columns:
            limited = prices.copy()
            limited["time"] = pd.to_datetime(limited["time"], errors="coerce")
            step.asset_universe_prices = limited.loc[limited["time"] <= train_end].copy()
