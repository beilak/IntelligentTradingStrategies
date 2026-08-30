import numpy as np
import pandas as pd
from skfolio.optimization import InverseVolatility as SkfolioInverseVolatility

from its.strategies.core.optimization import EqualWeighted
from its.strategies.models import (
    ModelTurnoverAnomalyWithEQBuilder,
    ModelTurnoverAnomalyWithInverseVolatilityBuilder,
)
from its.strategies.testing.backtest.core import weights_to_records
from its.strategies.testing.backtest.vectorbt_backtest import (
    backtest_strategies_vectorbt,
)


def build_context(close_series: dict[str, np.ndarray]) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-01", periods=len(next(iter(close_series.values()))))
    rows = []
    for index, date in enumerate(dates):
        for ticker, closes in close_series.items():
            close = closes[index]
            rows.append(
                {
                    "time": date,
                    "ticker": ticker,
                    "open": close,
                    "high": close * 1.01,
                    "low": close * 0.99,
                    "close": close,
                    "volume": 10_000_000.0,
                    "is_complete": True,
                }
            )
    return pd.DataFrame(rows)


def make_series(returns: np.ndarray, start: float = 100.0) -> np.ndarray:
    return start * np.concatenate(([1.0], np.cumprod(1.0 + returns)))


def build_spike_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = 90
    rng = np.random.default_rng(11)
    noise = rng.normal(0.0, 0.003, periods)
    spike = rng.normal(0.001, 0.003, periods)
    spike[70] = 0.20

    universe = {
        "SPIKE": make_series(spike),
        "AAA": make_series(noise),
        "BBB": make_series(rng.normal(0.0, 0.004, periods)),
    }
    dates = pd.bdate_range("2024-01-01", periods=len(next(iter(universe.values()))))
    prices = pd.DataFrame(
        {ticker: closes for ticker, closes in universe.items()},
        index=dates,
    )
    return prices, build_context(universe)


def build_flat_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = 90
    universe = {
        ticker: make_series(np.zeros(periods), start=start)
        for ticker, start in (("AAA", 100.0), ("BBB", 200.0))
    }
    dates = pd.bdate_range("2024-01-01", periods=len(next(iter(universe.values()))))
    prices = pd.DataFrame(
        {ticker: closes for ticker, closes in universe.items()},
        index=dates,
    )
    return prices, build_context(universe)


def test_turnover_anomaly_with_eq_composition() -> None:
    _, context = build_spike_fixture()
    strategy = ModelTurnoverAnomalyWithEQBuilder(_asset_universe_prices=context).build()

    assert strategy.name == "Turnover_anomaly_with_EQ"
    assert [name for name, _ in strategy.pipeline.steps] == [
        "turnover_pre_selection",
        "anomaly_signal",
        "allocation",
    ]
    assert isinstance(strategy.pipeline.named_steps["allocation"], EqualWeighted)


def test_turnover_anomaly_with_inverse_volatility_composition() -> None:
    _, context = build_spike_fixture()
    strategy = ModelTurnoverAnomalyWithInverseVolatilityBuilder(
        _asset_universe_prices=context
    ).build()

    assert strategy.name == "Turnover_anomaly_with_inverse_volatility"
    assert [name for name, _ in strategy.pipeline.steps] == [
        "turnover_pre_selection",
        "anomaly_signal",
        "allocation",
    ]
    assert isinstance(
        strategy.pipeline.named_steps["allocation"], SkfolioInverseVolatility
    )


def test_turnover_anomaly_with_eq_backtest_selects_on_spike_then_allows_cash() -> None:
    prices, context = build_spike_fixture()
    strategy = ModelTurnoverAnomalyWithEQBuilder(
        _asset_universe_prices=context
    ).build()

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=prices,
        rebalance_freq=5,
        rebalance_on="last",
        trading_start_date=prices.index[60],
        freq="1D",
    )[strategy.name]

    weights = result.weights.dropna(how="all")
    assert not weights.empty
    assert np.isfinite(weights.to_numpy()).all()
    row_sums = weights.sum(axis=1)
    assert (row_sums >= 0).all()
    assert (row_sums <= 1).all()
    assert (row_sums > 0).any()


def test_turnover_anomaly_with_inverse_volatility_backtest_runs() -> None:
    prices, context = build_spike_fixture()
    strategy = ModelTurnoverAnomalyWithInverseVolatilityBuilder(
        _asset_universe_prices=context
    ).build()

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=prices,
        rebalance_freq=5,
        rebalance_on="last",
        trading_start_date=prices.index[60],
        freq="1D",
    )[strategy.name]

    weights = result.weights.dropna(how="all")
    assert not weights.empty
    assert np.isfinite(weights.to_numpy()).all()
    assert ((weights.sum(axis=1) >= 0) & (weights.sum(axis=1) <= 1)).all()


def test_turnover_anomaly_backtest_stays_in_cash_without_anomaly() -> None:
    prices, context = build_flat_fixture()
    strategy = ModelTurnoverAnomalyWithEQBuilder(_asset_universe_prices=context).build()

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=prices,
        rebalance_freq=5,
        rebalance_on="last",
        trading_start_date=prices.index[60],
        freq="1D",
    )[strategy.name]

    rebalance_weights = result.weights.dropna(how="all")
    assert not rebalance_weights.empty
    assert (rebalance_weights == 0.0).all().all()

    records = weights_to_records(result.weights)
    assert records[0]["total_weight"] == 0.0
    assert records[0]["asset_count"] == 0
    assert records[0]["weights"] == []