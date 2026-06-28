import pandas as pd

from its.strategies.models import ModelPullbackWithEQBuilder
from its.strategies.testing.backtest.core import weights_to_records
from its.strategies.testing.backtest.vectorbt_backtest import \
    backtest_strategies_vectorbt


def test_pullback_backtest_uses_zero_weights_when_signal_selects_nothing() -> None:
    dates = pd.bdate_range("2024-01-01", periods=25)
    asset_universe_prices = pd.DataFrame(
        [
            {
                "time": date,
                "ticker": ticker,
                "high": 100.0,
                "close": 99.5,
                "is_complete": True,
            }
            for date in dates
            for ticker in ["SBER", "TRNFP", "GAZP"]
        ]
    )

    strategy = ModelPullbackWithEQBuilder(
        _asset_universe_prices=asset_universe_prices,
    ).build()
    prices = pd.DataFrame(
        {"SBER": 99.5, "TRNFP": 99.5, "GAZP": 99.5},
        index=dates,
    )

    result = backtest_strategies_vectorbt(
        strategies={strategy.name: strategy},
        prices=prices,
        rebalance_freq="5D",
        rebalance_on="last",
        trading_start_date=dates[10],
        freq="1D",
    )[strategy.name]

    rebalance_weights = result.weights.dropna(how="all")
    assert not rebalance_weights.empty
    assert (rebalance_weights == 0.0).all().all()

    records = weights_to_records(result.weights)
    assert records
    assert records[0]["total_weight"] == 0.0
    assert records[0]["asset_count"] == 0
    assert records[0]["weights"] == []
