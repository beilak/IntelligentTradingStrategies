import pandas as pd

from its.strategies.models import ModelPullbackWithEQBuilder


def test_pullback_model_handles_empty_signal_before_equal_weight_allocation() -> None:
    dates = pd.bdate_range("2024-01-01", periods=25)
    returns = pd.DataFrame(
        {
            "SBER": [0.0] * len(dates),
            "TRNFP": [0.0] * len(dates),
            "GAZP": [0.0] * len(dates),
        },
        index=dates,
    )
    asset_universe_prices = pd.DataFrame(
        [
            {
                "time": date,
                "ticker": ticker,
                "high": 100.0,
                "close": 99.0,
                "is_complete": True,
            }
            for date in dates
            for ticker in ["SBER", "TRNFP", "GAZP"]
        ]
    )

    strategy = ModelPullbackWithEQBuilder(
        _asset_universe_prices=asset_universe_prices,
    ).build()
    strategy.pipeline.fit(returns)

    signal = strategy.pipeline.named_steps["pullback_signal"]
    allocation = strategy.pipeline.named_steps["allocation"]

    assert signal.empty_selection_ is True
    assert allocation.weights_.tolist() == [0.5, 0.5]
