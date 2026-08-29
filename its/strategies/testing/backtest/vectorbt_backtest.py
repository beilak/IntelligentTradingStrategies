from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
import vectorbt as vbt
from pandas.tseries.frequencies import to_offset

from its.strategies_model.core.trading_strategy import PositionContext


@dataclass(frozen=True)
class BacktestResult:
    portfolio: vbt.Portfolio
    weights: pd.DataFrame
    order_prices: pd.DataFrame
    rebalance_dates: pd.Index
    execution_events: pd.DataFrame
    # refit_dates: pd.Index


@dataclass(frozen=True)
class CoreRebalancePlan:
    """Core entry candidates and optional universe membership by rebalance."""

    weights: pd.DataFrame
    universe_eligibility: pd.DataFrame | None = None


@dataclass
class _ManagedPosition:
    entry_time: pd.Timestamp
    entry_price: float
    weight: float
    stop_price: float | None = None


def backtest_strategies_vectorbt(
    *,
    strategies: Any | Iterable[Any] | Mapping[str, Any],
    prices: pd.DataFrame,
    rebalance_freq: str | int,
    open: pd.DataFrame | None = None,
    high: pd.DataFrame | None = None,
    low: pd.DataFrame | None = None,
    trading_start_date: str | pd.Timestamp | None = None,
    # refit_freq: Optional[Union[str, int]] = None,
    # train_window: Optional[Union[str, int]] = None,
    rebalance_on: str = "last",
    # refit_on: str = "last",
    init_cash: float = 100_000.0,
    fees: float = 0.0,
    slippage: float = 0.0,
    freq: str | None,
    seed: int = 42,
) -> dict[str, BacktestResult]:
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

    results: dict[str, BacktestResult] = {}

    for name, strat in strategy_map.items():
        weights, order_prices, execution_events = _build_order_plan(
            strat,
            prices,
            rebalance_dates,
            # refit_dates,
            # train_window=train_window,
            trading_start_date=trading_start_date,
            open=open,
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
    strategies: Any | Iterable[Any] | Mapping[str, Any],
) -> dict[str, Any]:
    if isinstance(strategies, Mapping):
        return dict(strategies)

    if isinstance(strategies, (list, tuple, set)):
        result: dict[str, Any] = {}
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
    open: pd.DataFrame | None = None,
    high: pd.DataFrame | None = None,
    low: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    core_strategy = getattr(strategy, "core", None)
    strategy_for_weights = core_strategy if core_strategy is not None else strategy
    lifecycle = getattr(strategy, "position_lifecycle", None)
    lifecycle_mode = getattr(lifecycle, "mode", "rebalance_target")
    universe_selector_step = (
        getattr(lifecycle, "universe_selector_step", None)
        if lifecycle_mode == "hold_until_exit"
        else None
    )
    core_plan = _build_core_rebalance_plan(
        strategy_for_weights,
        prices,
        rebalance_dates,
        trading_start_date=trading_start_date,
        universe_selector_step=universe_selector_step,
    )
    weights = core_plan.weights

    if core_strategy is None or not hasattr(strategy, "evaluate_position"):
        return weights, prices.copy(), empty_execution_events()

    if lifecycle_mode == "hold_until_exit":
        return _apply_hold_until_exit_lifecycle(
            strategy,
            weights,
            core_plan.universe_eligibility,
            prices,
            rebalance_dates,
            trading_start_date=trading_start_date,
            open=open,
            high=high,
            low=low,
        )

    return _apply_position_exit_policy(
        strategy,
        weights,
        prices,
        rebalance_dates,
        trading_start_date=trading_start_date,
        open=open,
        high=high,
        low=low,
    )


# def _infer_freq(index: pd.Index) -> Optional[str]:
#     if isinstance(index, pd.DatetimeIndex):
#         return pd.infer_freq(index)
#     return None


def _make_schedule(index: pd.Index, freq: str | int | None, on: str) -> pd.Index:
    if freq is None:
        return pd.Index([])
    if index.empty:
        return pd.Index([])

    if isinstance(freq, int):
        if freq <= 0:
            raise ValueError("freq must be a positive integer.")
        return index[::freq]

    if not isinstance(index, (pd.DatetimeIndex, pd.PeriodIndex)):
        raise TypeError("String freq requires a DatetimeIndex or PeriodIndex.")
    if on not in {"first", "last"}:
        raise ValueError("on must be 'first' or 'last'.")

    normalized_freq = freq.upper()
    if on == "first" and normalized_freq.endswith("ME"):
        return _month_end_first_schedule(index, normalized_freq)

    offset = _schedule_offset(freq)
    start = index[0]
    end = index[-1]
    if on == "first":
        schedule = []
        period_start = start + offset
    else:
        schedule = [start]
        period_start = start

    while period_start <= end:
        period_end = period_start + offset
        period_index = index[(index >= period_start) & (index < period_end)]
        if len(period_index) > 0:
            rebalance_date = period_index[-1] if on == "last" else period_index[0]
            if not schedule or rebalance_date != schedule[-1]:
                schedule.append(rebalance_date)
        period_start = period_end

    if schedule and schedule[-1] != end and on == "last":
        schedule.append(end)

    return pd.Index(schedule)


def _month_end_first_schedule(index: pd.Index, freq: str) -> pd.Index:
    """Select the first trading date after each calendar month-end boundary."""
    start = pd.Timestamp(index[0])
    end = pd.Timestamp(index[-1])
    boundaries = pd.date_range(start=start.normalize(), end=end, freq=freq)
    schedule = []
    for boundary in boundaries:
        candidates = index[index > boundary]
        if len(candidates) > 0:
            rebalance_date = candidates[0]
            if not schedule or rebalance_date != schedule[-1]:
                schedule.append(rebalance_date)
    return pd.Index(schedule)


def _schedule_offset(freq: str) -> pd.DateOffset:
    normalized = freq.upper()
    if normalized.endswith("ME"):
        value = normalized.removesuffix("ME")
        months = int(value) if value else 1
        return pd.DateOffset(months=months)
    return to_offset(freq)


def _resolve_train_start(
    index: pd.Index,
    train_window: str | int | None,
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
    return _build_core_rebalance_plan(
        strategy,
        prices,
        rebalance_dates,
        trading_start_date=trading_start_date,
    ).weights


def _build_core_rebalance_plan(
    strategy: Any,
    prices: pd.DataFrame,
    rebalance_dates: pd.Index,
    *,
    trading_start_date: str,
    universe_selector_step: str | None = None,
) -> CoreRebalancePlan:
    weights = pd.DataFrame(
        index=prices.loc[trading_start_date:].index,
        columns=prices.columns,
        data=np.nan,
        dtype=float,
    )
    universe_eligibility = (
        pd.DataFrame(
            index=weights.index,
            columns=prices.columns,
            data=np.nan,
            dtype=float,
        )
        if universe_selector_step
        else None
    )
    if universe_selector_step:
        _require_pipeline_step(strategy.pipeline, universe_selector_step)

    for rebalance_date in rebalance_dates:
        if trading_start_date is not None and trading_start_date > rebalance_date:
            continue

        train_prices = prices.loc[:rebalance_date].iloc[:-1]
        if train_prices.empty:
            continue

        train_prices = _filter_trainable_prices(
            train_prices,
            prices.loc[rebalance_date],
        )
        if train_prices.empty:
            continue

        train_end = train_prices.index[-1]
        _limit_pipeline_price_context(strategy, train_end)
        prices_close_returns_for_fit = _build_train_returns(train_prices)

        try:
            strategy.pipeline.fit(prices_close_returns_for_fit)
        except ValueError:
            if not _pipeline_selected_no_assets(strategy.pipeline):
                raise
            _record_universe_eligibility(
                strategy.pipeline,
                universe_selector_step,
                universe_eligibility,
                rebalance_date,
                prices.columns,
            )
            weights.loc[rebalance_date] = 0.0
            continue

        _record_universe_eligibility(
            strategy.pipeline,
            universe_selector_step,
            universe_eligibility,
            rebalance_date,
            prices.columns,
        )

        ptf_stat = strategy.pipeline.predict(prices_close_returns_for_fit)
        weights_dict = getattr(ptf_stat, "weights_dict", None)
        if not weights_dict:
            continue

        row = pd.Series(0.0, index=prices.columns)
        for ticker, weight in weights_dict.items():
            if ticker in row.index and np.isfinite(weight):
                row.loc[ticker] = float(weight)
        weights.loc[rebalance_date] = row

    return CoreRebalancePlan(
        weights=weights,
        universe_eligibility=universe_eligibility,
    )


def _require_pipeline_step(pipeline: Any, step_name: str) -> None:
    named_steps = getattr(pipeline, "named_steps", {})
    if step_name not in named_steps:
        raise ValueError(f"Pipeline step '{step_name}' was not found.")


def _record_universe_eligibility(
    pipeline: Any,
    step_name: str | None,
    eligibility: pd.DataFrame | None,
    rebalance_date: Any,
    all_assets: pd.Index,
) -> None:
    if not step_name or eligibility is None:
        return

    selector = pipeline.named_steps[step_name]
    asset_names = np.asarray(getattr(selector, "asset_names_", []), dtype=str)
    mask = np.asarray(getattr(selector, "to_keep_", []), dtype=bool)
    if len(asset_names) != len(mask):
        raise ValueError(
            f"Pipeline step '{step_name}' did not expose aligned eligibility."
        )

    row = pd.Series(0.0, index=all_assets, dtype=float)
    for ticker, keep in zip(asset_names, mask, strict=True):
        if ticker in row.index:
            row.loc[ticker] = float(keep)
    eligibility.loc[rebalance_date] = row


def _pipeline_selected_no_assets(pipeline: Any) -> bool:
    """Return True only when a fitted selector produced an empty asset set."""
    for _, step in getattr(pipeline, "steps", [])[:-1]:
        get_mask = getattr(step, "_get_support_mask", None)
        if not callable(get_mask):
            continue
        try:
            mask = np.asarray(get_mask(), dtype=bool)
        except (AttributeError, TypeError, ValueError):
            continue
        if mask.size > 0 and not mask.any():
            return True
    return False


def _filter_trainable_prices(
    train_prices: pd.DataFrame,
    rebalance_prices: pd.Series,
) -> pd.DataFrame:
    tradable = rebalance_prices.replace([np.inf, -np.inf], np.nan).dropna()
    tradable = tradable[tradable > 0]
    filtered = train_prices.loc[:, train_prices.columns.intersection(tradable.index)]
    return filtered.dropna(axis=1, how="all")


def _build_train_returns(train_prices: pd.DataFrame) -> pd.DataFrame:
    returns = train_prices.pct_change(fill_method=None).replace(
        [np.inf, -np.inf], np.nan
    )
    return returns.fillna(0)


def _apply_hold_until_exit_lifecycle(
    strategy: Any,
    entry_weights: pd.DataFrame,
    universe_eligibility: pd.DataFrame | None,
    prices: pd.DataFrame,
    rebalance_dates: pd.Index,
    *,
    trading_start_date: str,
    open: pd.DataFrame | None = None,
    high: pd.DataFrame | None = None,
    low: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    lifecycle = strategy.position_lifecycle
    allocation_pct = float(lifecycle.allocation_pct)
    managed_weights = pd.DataFrame(
        index=entry_weights.index,
        columns=entry_weights.columns,
        data=np.nan,
        dtype=float,
    )
    order_prices = prices.copy()
    events: list[dict[str, Any]] = []
    active: dict[Any, _ManagedPosition] = {}
    trading_index = prices.loc[trading_start_date:].index
    rebalance_set = set(rebalance_dates)
    history_bars = int(getattr(strategy.exit_policy, "required_history_bars", 0) or 0)
    low_history_source = low if low is not None else prices

    for current_date in trading_index:
        exited_this_bar: set[Any] = set()

        for ticker, position in list(active.items()):
            current_price = _matrix_value(prices, current_date, ticker)
            if not _is_finite_positive(current_price):
                continue
            context = PositionContext(
                ticker=str(ticker),
                entry_time=position.entry_time,
                current_time=pd.Timestamp(current_date),
                entry_price=position.entry_price,
                current_price=float(current_price),
                weight=position.weight,
                open_price=_matrix_value(open, current_date, ticker),
                high_price=_matrix_value(high, current_date, ticker),
                low_price=_matrix_value(low, current_date, ticker),
                active_stop_price=position.stop_price,
            )
            decision = strategy.evaluate_position(context)
            if decision is None:
                continue

            managed_weights.loc[current_date, ticker] = 0.0
            order_prices.loc[current_date, ticker] = decision.execution_price
            events.append(
                _execution_event(
                    current_date=current_date,
                    ticker=ticker,
                    position=position,
                    reason=decision.reason,
                    execution_price=decision.execution_price,
                    threshold_price=decision.threshold_price,
                    return_pct=decision.return_pct,
                )
            )
            del active[ticker]
            exited_this_bar.add(ticker)

        if current_date not in rebalance_set:
            continue

        if lifecycle.close_on_universe_removal:
            _close_removed_positions(
                current_date=current_date,
                active=active,
                exited_this_bar=exited_this_bar,
                eligibility=universe_eligibility,
                prices=prices,
                managed_weights=managed_weights,
                events=events,
            )

        entry_row = entry_weights.loc[current_date].fillna(0.0)
        eligibility_row = _eligibility_row(universe_eligibility, current_date)
        for ticker, candidate_weight in entry_row.items():
            if (
                not np.isfinite(candidate_weight)
                or candidate_weight <= 1e-12
                or ticker in active
                or ticker in exited_this_bar
            ):
                continue
            if eligibility_row is not None and not bool(eligibility_row.loc[ticker]):
                continue
            entry_price = _matrix_value(prices, current_date, ticker)
            if not _is_finite_positive(entry_price):
                continue
            active[ticker] = _ManagedPosition(
                entry_time=pd.Timestamp(current_date),
                entry_price=float(entry_price),
                weight=0.0,
            )

        target_row = pd.Series(0.0, index=prices.columns, dtype=float)
        target_weight = allocation_pct / len(active) if active else 0.0
        for ticker, position in active.items():
            position.weight = target_weight
            target_row.loc[ticker] = target_weight
        managed_weights.loc[current_date] = target_row

        if history_bars <= 0:
            continue
        for ticker, position in active.items():
            current_price = _matrix_value(prices, current_date, ticker)
            if not _is_finite_positive(current_price):
                continue
            closed_lows = _matrix_history(
                low_history_source,
                current_date,
                ticker,
                history_bars,
            )
            context = PositionContext(
                ticker=str(ticker),
                entry_time=position.entry_time,
                current_time=pd.Timestamp(current_date),
                entry_price=position.entry_price,
                current_price=float(current_price),
                weight=position.weight,
                open_price=_matrix_value(open, current_date, ticker),
                high_price=_matrix_value(high, current_date, ticker),
                low_price=_matrix_value(low, current_date, ticker),
                active_stop_price=position.stop_price,
                closed_low_history=closed_lows,
            )
            position.stop_price = strategy.refresh_position_stop(
                context,
                position.stop_price,
            )

    if not events:
        return managed_weights, order_prices, empty_execution_events()
    return managed_weights, order_prices, pd.DataFrame(events)


def _close_removed_positions(
    *,
    current_date: Any,
    active: dict[Any, _ManagedPosition],
    exited_this_bar: set[Any],
    eligibility: pd.DataFrame | None,
    prices: pd.DataFrame,
    managed_weights: pd.DataFrame,
    events: list[dict[str, Any]],
) -> None:
    eligibility_row = _eligibility_row(eligibility, current_date)
    if eligibility_row is None:
        return

    for ticker, position in list(active.items()):
        if bool(eligibility_row.loc[ticker]):
            continue
        execution_price = _matrix_value(prices, current_date, ticker)
        if not _is_finite_positive(execution_price):
            continue
        return_pct = float(execution_price) / position.entry_price - 1
        managed_weights.loc[current_date, ticker] = 0.0
        events.append(
            _execution_event(
                current_date=current_date,
                ticker=ticker,
                position=position,
                reason="universe_removed",
                execution_price=float(execution_price),
                threshold_price=float(execution_price),
                return_pct=return_pct,
            )
        )
        del active[ticker]
        exited_this_bar.add(ticker)


def _eligibility_row(
    eligibility: pd.DataFrame | None,
    current_date: Any,
) -> pd.Series | None:
    if eligibility is None or current_date not in eligibility.index:
        return None
    row = eligibility.loc[current_date]
    if not row.notna().all():
        return None
    return row.astype(bool)


def _execution_event(
    *,
    current_date: Any,
    ticker: Any,
    position: _ManagedPosition,
    reason: str,
    execution_price: float,
    threshold_price: float,
    return_pct: float,
) -> dict[str, Any]:
    return {
        "time": current_date,
        "ticker": str(ticker),
        "reason": reason,
        "entry_time": position.entry_time,
        "entry_price": position.entry_price,
        "execution_price": float(execution_price),
        "threshold_price": float(threshold_price),
        "return_pct": float(return_pct),
        "weight": position.weight,
    }


def _apply_position_exit_policy(
    strategy: Any,
    weights: pd.DataFrame,
    prices: pd.DataFrame,
    rebalance_dates: pd.Index,
    *,
    trading_start_date: str,
    open: pd.DataFrame | None = None,
    high: pd.DataFrame | None = None,
    low: pd.DataFrame | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    managed_weights = weights.copy()
    order_prices = prices.copy()
    events: list[dict[str, Any]] = []
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
                    open_price=_matrix_value(open, current_date, ticker),
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
    matrix: pd.DataFrame | None,
    index: Any,
    column: Any,
) -> float | None:
    if matrix is None or column not in matrix.columns or index not in matrix.index:
        return None
    value = matrix.loc[index, column]
    if pd.isna(value):
        return None
    return float(value)


def _matrix_history(
    matrix: pd.DataFrame,
    end: Any,
    column: Any,
    bars: int,
) -> tuple[float, ...]:
    if column not in matrix.columns or end not in matrix.index or bars <= 0:
        return ()
    values = matrix.loc[:end, column].tail(bars).to_numpy(dtype=float)
    return tuple(float(value) for value in values)


def _is_finite_positive(value: float | None) -> bool:
    return value is not None and np.isfinite(value) and value > 0


def _limit_pipeline_price_context(strategy: Any, train_end: pd.Timestamp) -> None:
    pipeline = getattr(strategy, "pipeline", None)
    steps = getattr(pipeline, "steps", [])
    for _, step in steps:
        prices = getattr(step, "asset_universe_prices", None)
        if isinstance(prices, pd.DataFrame) and "time" in prices.columns:
            full_prices = getattr(
                step,
                "_backtest_full_asset_universe_prices",
                None,
            )
            if not isinstance(full_prices, pd.DataFrame):
                full_prices = prices.copy()
                step._backtest_full_asset_universe_prices = full_prices

            limited = full_prices.copy()
            limited["time"] = pd.to_datetime(limited["time"], errors="coerce")
            step.asset_universe_prices = limited.loc[
                limited["time"] <= train_end
            ].copy()
