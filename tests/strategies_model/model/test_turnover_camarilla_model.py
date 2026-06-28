import numpy as np
import pandas as pd

from its.strategies.models import \
    ModelTurnoverCamarillaWithInverseVolatilityBuilder
from its.strategies.testing.backtest.vectorbt_backtest import \
    backtest_strategies_vectorbt


def build_fixture() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates = pd.bdate_range("2024-01-01", periods=25)
    aaa = np.linspace(95.0, 100.0, len(dates))
    bbb = np.linspace(195.0, 200.0, len(dates))
    aaa[7:10] = [100.0, 98.0, 99.0]
    rows = []
    for index, date in enumerate(dates):
        for ticker, close in (("AAA", aaa[index]), ("BBB", bbb[index])):
            is_reference = ticker == "AAA" and index == 7
            rows.append(
                {
                    "time": date,
                    "ticker": ticker,
                    "open": close,
                    "high": 110.0 if is_reference else close + 1.0,
                    "low": 90.0 if is_reference else close - 1.0,
                    "close": close,
                    "volume": 10_000_000.0,
                    "is_complete": True,
                }
            )
    prices = pd.DataFrame({"AAA": aaa, "BBB": bbb}, index=dates)
    return prices, pd.DataFrame(rows)


def test_turnover_camarilla_model_composition() -> None:
    _, context = build_fixture()
    strategy = ModelTurnoverCamarillaWithInverseVolatilityBuilder(
        _asset_universe_prices=context
    ).build()

    assert [name for name, _ in strategy.pipeline.steps] == [
        "turnover_pre_selection",
        "camarilla_support_cross_signal",
        "allocation_window",
        "allocation",
    ]
    signal = strategy.pipeline.named_steps["camarilla_support_cross_signal"]
    assert signal.support_line == "S1"


def test_turnover_camarilla_model_backtest_buys_then_allows_cash() -> None:
    prices, context = build_fixture()
    strategy = ModelTurnoverCamarillaWithInverseVolatilityBuilder(
        _asset_universe_prices=context
    ).build()

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=prices,
        rebalance_freq=5,
        rebalance_on="last",
        trading_start_date=prices.index[10],
        freq="1D",
    )[strategy.name]

    weights = result.weights.dropna(how="all")
    assert not weights.empty
    assert weights.iloc[0]["AAA"] == 1.0
    assert weights.iloc[0]["BBB"] == 0.0
    assert (weights.iloc[1:].sum(axis=1) == 0.0).any()
    assert np.isfinite(weights.to_numpy()).all()
