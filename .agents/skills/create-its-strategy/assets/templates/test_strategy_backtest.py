import pandas as pd

from its.strategies.models import ExampleStrategyBuilder
from its.strategies.testing.backtest.vectorbt_backtest import backtest_strategies_vectorbt


def test_example_strategy_runs_and_allows_cash_rebalance() -> None:
    dates = pd.bdate_range("2024-01-01", periods=80)
    prices = pd.DataFrame({"AAA": range(100, 180), "BBB": range(200, 280)}, index=dates)
    context = pd.DataFrame()  # TODO: construct required long context.
    strategy = ExampleStrategyBuilder(_asset_universe_prices=context).build()
    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=prices,
        rebalance_freq="20D",
        rebalance_on="last",
        trading_start_date=dates[20],
        freq="1D",
    )[strategy.name]
    weights = result.weights.dropna(how="all")
    assert not weights.empty
    assert weights.notna().all().all()
    assert ((weights.sum(axis=1) >= 0) & (weights.sum(axis=1) <= 1)).all()

